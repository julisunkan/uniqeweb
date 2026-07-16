"""Audio Books Generator — Blueprint routes."""
import os
import sqlite3
import threading
import uuid
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, send_file)
from config import get_setting

bp = Blueprint('audio', __name__, template_folder='templates')

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DB_PATH  = os.path.join(BASE_DIR, 'audio.db')
OUTPUTS  = os.path.join(BASE_DIR, 'outputs')
os.makedirs(OUTPUTS, exist_ok=True)

# ── DB helpers ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            source     TEXT DEFAULT 'paste',
            status     TEXT DEFAULT 'pending',
            filename   TEXT,
            error      TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

init_db()

# ── Background TTS worker ─────────────────────────────────────────────────────
def _run_tts(job_id, text, title):
    """Runs in a background thread.
    Uses edge-tts (Microsoft Edge neural TTS) via a subprocess so gevent's
    monkey-patching never interferes with asyncio/aiohttp networking.
    Accepts full edge-tts voice names (e.g. 'en-US-AriaNeural') or bare
    BCP-47 language codes ('en', 'es', …).
    """
    import sys
    import subprocess
    import tempfile

    _LANG_TO_VOICE = {
        'en': 'en-US-AriaNeural',
        'es': 'es-ES-AlvaroNeural',
        'fr': 'fr-FR-DeniseNeural',
        'de': 'de-DE-KatjaNeural',
        'ja': 'ja-JP-NanamiNeural',
        'zh': 'zh-CN-XiaoxiaoNeural',
        'pt': 'pt-BR-FranciscaNeural',
        'it': 'it-IT-ElsaNeural',
        'ko': 'ko-KR-SunHiNeural',
        'ar': 'ar-EG-SalmaNeural',
    }

    # Inline script executed by a fresh Python interpreter — no gevent patches
    _TTS_SCRIPT = (
        "import asyncio, edge_tts, sys\n"
        "text  = open(sys.argv[1], encoding='utf-8').read()\n"
        "voice = sys.argv[2]\n"
        "out   = sys.argv[3]\n"
        "asyncio.run(edge_tts.Communicate(text, voice).save(out))\n"
    )

    db = sqlite3.connect(DB_PATH)
    try:
        max_chars = int(get_setting('audio_max_chars', '50000'))
        voice     = (get_setting('audio_tts_lang', 'en-US-AriaNeural') or
                     'en-US-AriaNeural').strip()
        voice     = _LANG_TO_VOICE.get(voice.lower(), voice)

        capped = text[:max_chars]
        fname  = f"{job_id}.mp3"
        fpath  = os.path.join(OUTPUTS, fname)

        # Write text to a temp file to avoid command-line length limits
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                         delete=False, encoding='utf-8') as f:
            f.write(capped)
            tmppath = f.name

        try:
            result = subprocess.run(
                [sys.executable, '-c', _TTS_SCRIPT, tmppath, voice, fpath],
                timeout=120, capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or 'edge-tts failed')
        finally:
            try:
                os.unlink(tmppath)
            except OSError:
                pass

        db.execute(
            "UPDATE jobs SET status='done', filename=? WHERE id=?",
            (fname, job_id)
        )
        db.commit()
    except Exception as exc:
        db.execute(
            "UPDATE jobs SET status='error', error=? WHERE id=?",
            (str(exc), job_id)
        )
        db.commit()
    finally:
        db.close()

# ── Text extraction helpers ───────────────────────────────────────────────────
def _extract_text(file_storage):
    """Extract plain text from an uploaded file object."""
    filename = file_storage.filename.lower()
    data = file_storage.read()

    if filename.endswith('.txt'):
        return data.decode('utf-8', errors='replace')

    if filename.endswith('.pdf'):
        import fitz  # PyMuPDF
        import io
        doc = fitz.open(stream=data, filetype='pdf')
        pages = [page.get_text() for page in doc]
        doc.close()
        return '\n'.join(pages)

    if filename.endswith('.docx'):
        from docx import Document
        import io
        doc = Document(io.BytesIO(data))
        return '\n'.join(p.text for p in doc.paragraphs)

    return data.decode('utf-8', errors='replace')

# ── Routes ────────────────────────────────────────────────────────────────────
@bp.route('/')
def index():
    db = get_db()
    jobs = db.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    return render_template('audio/index.html', jobs=jobs)


@bp.route('/process', methods=['POST'])
def process():
    title  = request.form.get('title', '').strip() or 'Untitled'
    source = 'paste'
    text   = ''

    uploaded = request.files.get('file')
    if uploaded and uploaded.filename:
        source = 'upload'
        try:
            text = _extract_text(uploaded)
        except Exception as exc:
            flash(f'Could not read file: {exc}', 'error')
            return redirect(url_for('audio.index'))
    else:
        text = request.form.get('text', '').strip()

    if not text:
        flash('Please provide some text or upload a file.', 'error')
        return redirect(url_for('audio.index'))

    job_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO jobs (id, title, source, status) VALUES (?, ?, ?, 'pending')",
        (job_id, title, source)
    )
    db.commit()
    db.close()

    t = threading.Thread(target=_run_tts, args=(job_id, text, title), daemon=True)
    t.start()

    flash(f'job:{job_id}', 'info')
    return redirect(url_for('audio.index'))


@bp.route('/status/<job_id>')
def status(job_id):
    db = get_db()
    row = db.execute(
        "SELECT status, filename, error FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    db.close()
    if row is None:
        return jsonify({'status': 'not_found'}), 404
    return jsonify({
        'status':   row['status'],
        'filename': row['filename'],
        'error':    row['error'],
    })


@bp.route('/download/<filename>')
def download(filename):
    safe = os.path.basename(filename)
    path = os.path.join(OUTPUTS, safe)
    if not os.path.exists(path):
        flash('File not found.', 'error')
        return redirect(url_for('audio.index'))
    mime = 'audio/wav' if safe.endswith('.wav') else 'audio/mpeg'
    return send_file(path, mimetype=mime,
                     as_attachment=True, download_name=safe)


@bp.route('/delete/<job_id>', methods=['POST'])
def delete(job_id):
    db = get_db()
    row = db.execute(
        "SELECT filename FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    if row:
        if row['filename']:
            fpath = os.path.join(OUTPUTS, row['filename'])
            if os.path.exists(fpath):
                os.remove(fpath)
        db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        db.commit()
    db.close()
    flash('Audiobook deleted.', 'info')
    return redirect(url_for('audio.index'))
