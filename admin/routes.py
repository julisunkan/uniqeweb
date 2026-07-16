"""Admin panel blueprint — /julisunkan"""
import json
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('admin', __name__, template_folder='templates')

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
ADMIN_DB = os.path.join(BASE_DIR, 'admin.db')

DEFAULT_PASSWORD = 'admin123'

# ── Known settings with labels/descriptions ───────────────────────────────────
SETTINGS_META = [
    # (key, label, description, input_type, options)
    ('groq_api_key',            'Groq API Key',
     'Used for AI flashcard generation and email taglines.',
     'password', None),
    ('audio_tts_lang',          'TTS Voice',
     'edge-tts voice name (e.g. en-US-AriaNeural, es-ES-AlvaroNeural) '
     'or bare language code (en, es, fr, de, ja, zh, pt, it, ko, ar).',
     'text', None),
    ('audio_max_chars',         'TTS Max Characters',
     'Maximum characters sent to edge-tts per job.',
     'number', None),
    ('flashcard_default_count', 'Default Flashcard Count',
     'Pre-filled card count when creating a new deck.',
     'number', None),
    ('flashcard_max_count',     'Max Flashcard Count',
     'Hard upper limit for cards per deck.',
     'number', None),
    ('pdf_max_size_mb',         'PDF Max Upload Size (MB)',
     'Reject PDFs larger than this.',
     'number', None),
    ('ssh_max_sessions',        'SSH Max Concurrent Sessions',
     'Maximum simultaneous SSH connections allowed.',
     'number', None),
    ('email_default_template',  'Default Email Template',
     'Template used when page loads.',
     'select', ['modern', 'classic', 'minimal']),
    ('email_default_accent',    'Default Accent Colour',
     'Hex colour pre-selected for new signatures.',
     'color', None),
    ('app_audio_enabled',       'Audio App Enabled',
     'Show/hide the Audiobooks app.',
     'toggle', None),
    ('app_pdf_enabled',         'PDF Filler App Enabled',
     'Show/hide the PDF Form Filler app.',
     'toggle', None),
    ('app_ssh_enabled',         'SSH Terminal App Enabled',
     'Show/hide the SSH Terminal app.',
     'toggle', None),
    ('app_email_enabled',       'Email Signature App Enabled',
     'Show/hide the Email Signature app.',
     'toggle', None),
    ('app_flash_enabled',       'Flashcard App Enabled',
     'Show/hide the AI Flashcard app.',
     'toggle', None),
]

# ── DB helpers ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(ADMIN_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS admin_users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT NOT NULL,
            detail     TEXT,
            ip         TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Insert default admin if not present
    existing = conn.execute(
        "SELECT id FROM admin_users WHERE username='admin'"
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
            ('admin', generate_password_hash(DEFAULT_PASSWORD))
        )
    # Seed default settings
    from config import DEFAULTS
    for key, val in DEFAULTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, val)
        )
    conn.commit()
    conn.close()


init_db()


def audit(action, detail=''):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_log (action, detail, ip) VALUES (?, ?, ?)",
            (action, detail, request.remote_addr)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Auth decorator ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


# ── Stat helpers ──────────────────────────────────────────────────────────────
def collect_stats():
    stats = {}
    app_dbs = {
        'audio':    os.path.join(BASE_DIR, '..', 'audio', 'audio.db'),
        'pdf':      os.path.join(BASE_DIR, '..', 'pdf_filler', 'pdf.db'),
        'flashcard':os.path.join(BASE_DIR, '..', 'flashcard', 'flashcard.db'),
    }

    # Audio jobs
    try:
        c = sqlite3.connect(app_dbs['audio'])
        row = c.execute("SELECT COUNT(*), SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) FROM jobs").fetchone()
        stats['audio_total']    = row[0] or 0
        stats['audio_done']     = row[1] or 0
        c.close()
    except Exception:
        stats['audio_total'] = stats['audio_done'] = 0

    # PDF uploads
    try:
        c = sqlite3.connect(app_dbs['pdf'])
        row = c.execute("SELECT COUNT(*) FROM uploads").fetchone()
        stats['pdf_total'] = row[0] or 0
        c.close()
    except Exception:
        stats['pdf_total'] = 0

    # Flashcard decks + cards
    try:
        c = sqlite3.connect(app_dbs['flashcard'])
        r1 = c.execute("SELECT COUNT(*) FROM decks").fetchone()
        r2 = c.execute("SELECT COUNT(*) FROM cards").fetchone()
        stats['flash_decks'] = r1[0] or 0
        stats['flash_cards'] = r2[0] or 0
        c.close()
    except Exception:
        stats['flash_decks'] = stats['flash_cards'] = 0

    # Disk usage for output dirs
    def dir_size_mb(path):
        total = 0
        try:
            for f in os.scandir(path):
                if f.is_file():
                    total += f.stat().st_size
        except Exception:
            pass
        return round(total / (1024 * 1024), 2)

    stats['audio_mb'] = dir_size_mb(
        os.path.join(BASE_DIR, '..', 'audio', 'outputs'))
    stats['pdf_mb']   = dir_size_mb(
        os.path.join(BASE_DIR, '..', 'pdf_filler', 'outputs'))

    return stats


# ── Routes ────────────────────────────────────────────────────────────────────
@bp.route('/')
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/login.html')


@bp.route('/login', methods=['POST'])
def do_login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM admin_users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['admin_logged_in'] = True
        session['admin_user'] = username
        audit('login', f'User {username} logged in')
        return redirect(url_for('admin.dashboard'))

    audit('login_fail', f'Failed attempt for {username}')
    flash('Invalid username or password.', 'error')
    return redirect(url_for('admin.login'))


@bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_user', None)
    return redirect(url_for('admin.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    settings_rows = conn.execute("SELECT key, value FROM settings").fetchall()
    audit_rows    = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()

    settings = {r['key']: r['value'] for r in settings_rows}
    stats    = collect_stats()

    return render_template(
        'admin/dashboard.html',
        settings=settings,
        settings_meta=SETTINGS_META,
        stats=stats,
        audit_log=audit_rows,
        admin_user=session.get('admin_user', 'admin'),
    )


@bp.route('/save-settings', methods=['POST'])
@login_required
def save_settings():
    conn = get_db()
    changed = []
    for key, _, _, input_type, _ in SETTINGS_META:
        if input_type == 'toggle':
            val = '1' if request.form.get(key) else '0'
        else:
            val = request.form.get(key, '').strip()
            if key == 'groq_api_key' and not val:
                # Keep existing if blank submitted
                existing = conn.execute(
                    "SELECT value FROM settings WHERE key=?", (key,)
                ).fetchone()
                if existing:
                    continue
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (key, val)
        )
        changed.append(key)
    conn.commit()
    conn.close()
    audit('save_settings', f'Updated: {", ".join(changed)}')
    flash('Settings saved successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current  = request.form.get('current_password', '')
    new_pw   = request.form.get('new_password', '')
    confirm  = request.form.get('confirm_password', '')

    if new_pw != confirm:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('admin.dashboard') + '#security')

    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin.dashboard') + '#security')

    conn = get_db()
    username = session.get('admin_user', 'admin')
    user = conn.execute(
        "SELECT * FROM admin_users WHERE username=?", (username,)
    ).fetchone()

    if not user or not check_password_hash(user['password_hash'], current):
        conn.close()
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('admin.dashboard') + '#security')

    conn.execute(
        "UPDATE admin_users SET password_hash=? WHERE username=?",
        (generate_password_hash(new_pw), username)
    )
    conn.commit()
    conn.close()
    audit('change_password', f'Password changed for {username}')
    flash('Password changed successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/clear-data/<app_name>', methods=['POST'])
@login_required
def clear_data(app_name):
    allowed = {'audio', 'pdf', 'flashcard', 'audit'}
    if app_name not in allowed:
        flash('Unknown app.', 'error')
        return redirect(url_for('admin.dashboard'))

    try:
        if app_name == 'audio':
            db = os.path.join(BASE_DIR, '..', 'audio', 'audio.db')
            out = os.path.join(BASE_DIR, '..', 'audio', 'outputs')
            c = sqlite3.connect(db)
            c.execute("DELETE FROM jobs")
            c.commit(); c.close()
            for f in os.scandir(out):
                if f.is_file():
                    os.remove(f.path)
            flash('Audio jobs and MP3 files cleared.', 'success')

        elif app_name == 'pdf':
            db  = os.path.join(BASE_DIR, '..', 'pdf_filler', 'pdf.db')
            upl = os.path.join(BASE_DIR, '..', 'pdf_filler', 'uploads')
            out = os.path.join(BASE_DIR, '..', 'pdf_filler', 'outputs')
            c = sqlite3.connect(db)
            c.execute("DELETE FROM uploads")
            c.commit(); c.close()
            for d in (upl, out):
                for f in os.scandir(d):
                    if f.is_file():
                        os.remove(f.path)
            flash('PDF uploads and filled files cleared.', 'success')

        elif app_name == 'flashcard':
            db = os.path.join(BASE_DIR, '..', 'flashcard', 'flashcard.db')
            c = sqlite3.connect(db)
            c.execute("PRAGMA foreign_keys = ON")
            c.execute("DELETE FROM decks")
            c.commit(); c.close()
            flash('All flashcard decks and cards deleted.', 'success')

        elif app_name == 'audit':
            conn = get_db()
            conn.execute("DELETE FROM audit_log")
            conn.commit(); conn.close()
            flash('Audit log cleared.', 'success')

        audit('clear_data', f'Cleared {app_name}')
    except Exception as exc:
        flash(f'Error clearing data: {exc}', 'error')

    return redirect(url_for('admin.dashboard'))


@bp.route('/test-groq', methods=['POST'])
@login_required
def test_groq():
    from config import get_groq_key
    key = get_groq_key()
    if not key:
        return jsonify({'ok': False, 'msg': 'No API key configured.'})
    try:
        from groq import Groq
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': 'Say "OK" only.'}],
            max_tokens=5,
        )
        return jsonify({'ok': True, 'msg': 'API key is valid ✓'})
    except Exception as exc:
        return jsonify({'ok': False, 'msg': str(exc)})


@bp.route('/stats-api')
@login_required
def stats_api():
    return jsonify(collect_stats())
