"""PDF Form Filler — Blueprint routes."""
import io
import json
import logging
import os
import sqlite3
import time
import uuid
from typing import Optional

import pypdf
from flask import (Blueprint, redirect, render_template, request,
                   send_file, url_for, flash, Response)
from translations import get_t
from werkzeug.utils import secure_filename

bp = Blueprint('pdf_filler', __name__, template_folder='templates')

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(__file__)
DB_PATH     = os.path.join(BASE_DIR, 'pdf.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
MAX_BYTES   = 50 * 1024 * 1024  # 50 MB

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

logger = logging.getLogger('pdf_filler')


# ── DB ─────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY,
                original_name TEXT,
                has_fields INTEGER DEFAULT 0,
                field_names TEXT,
                field_metadata TEXT,
                output_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        for col, defn in [('field_metadata', 'TEXT'), ('output_name', 'TEXT')]:
            try:
                conn.execute(f'ALTER TABLE uploads ADD COLUMN {col} {defn}')
            except Exception:
                pass
        conn.commit()


init_db()


# ── Field helpers ──────────────────────────────────────────────────────────────
def _field_type(info: dict) -> str:
    """Map a pypdf field info dict to a UI type string."""
    ft = info.get('/FT', '')
    ff = int(info.get('/Ff', 0))
    if ft == '/Tx':
        return 'multiline' if (ff & 4096) else 'text'
    if ft == '/Btn':
        if ff & 65536:
            return 'pushbutton'   # navigation / submit — skip
        if ff & 32768:
            return 'radio'
        return 'checkbox'
    if ft == '/Ch':
        return 'select' if (ff & 131072) else 'listbox'
    return 'text'


def _build_field_meta(all_fields: dict) -> list[dict]:
    """Return a list of fillable field metadata dicts, skipping push-buttons."""
    result = []
    for name, info in all_fields.items():
        ftype = _field_type(info)
        if ftype == 'pushbutton':
            continue

        # Options for radio / select / listbox
        options: list[str] = []
        opt_raw = info.get('/Opt')
        if opt_raw:
            for o in opt_raw:
                if isinstance(o, (list, tuple)):
                    options.append(str(o[1]) if len(o) > 1 else str(o[0]))
                else:
                    options.append(str(o))
        elif ftype == 'radio':
            states = info.get('/_States_', []) or []
            options = [s.lstrip('/') for s in states if s not in ('/Off', '')]

        # On-state for checkbox (e.g. '/Yes', '/Red', '/Blue')
        on_state = '/Yes'
        if ftype == 'checkbox':
            states = info.get('/_States_', []) or []
            for s in states:
                if s != '/Off':
                    on_state = s
                    break

        # Current / default value
        raw_v = info.get('/V', info.get('/DV', ''))
        default = raw_v.lstrip('/') if isinstance(raw_v, str) else ''

        result.append({
            'name':     name,
            'type':     ftype,
            'options':  options,
            'default':  default,
            'on_state': on_state,
        })
    return result


# ── Routes ─────────────────────────────────────────────────────────────────────
@bp.route('/')
def index():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM uploads ORDER BY created_at DESC LIMIT 30'
        ).fetchall()
    return render_template('pdf_filler/index.html', uploads=rows)


@bp.route('/upload', methods=['POST'])
def upload():
    t = get_t()
    f = request.files.get('pdf_file')
    if not f or not f.filename:
        flash(t['pdf_only'], 'error')
        return redirect(url_for('pdf_filler.index'))

    if not f.filename.lower().endswith('.pdf'):
        flash(t['pdf_only'], 'error')
        return redirect(url_for('pdf_filler.index'))

    # Size check
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > MAX_BYTES:
        flash(t['pdf_too_large'], 'error')
        return redirect(url_for('pdf_filler.index'))

    file_id  = str(uuid.uuid4())
    safe_name = secure_filename(f.filename)
    save_path = os.path.join(UPLOADS_DIR, f'{file_id}.pdf')
    f.save(save_path)
    logger.info('Uploaded %s → %s (%d bytes)', safe_name, file_id, size)

    # Detect fields
    t0 = time.time()
    try:
        reader      = pypdf.PdfReader(save_path)
        all_fields  = reader.get_fields() or {}
        field_meta  = _build_field_meta(all_fields)
        field_names = [m['name'] for m in field_meta]
        has_fields  = 1 if field_names else 0
    except Exception as exc:
        logger.error('Field detection failed for %s: %s', file_id, exc)
        field_meta, field_names, has_fields = [], [], 0

    logger.info('Detected %d fields in %.2fs', len(field_names), time.time() - t0)

    with get_db() as conn:
        conn.execute(
            'INSERT INTO uploads (id, original_name, has_fields, field_names, field_metadata) '
            'VALUES (?, ?, ?, ?, ?)',
            (file_id, safe_name, has_fields,
             json.dumps(field_names), json.dumps(field_meta))
        )
        conn.commit()

    return redirect(url_for('pdf_filler.fill', file_id=file_id))


@bp.route('/fill/<file_id>', methods=['GET'])
def fill(file_id: str):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    if row is None:
        flash(get_t()['pdf_not_found'], 'error')
        return redirect(url_for('pdf_filler.index'))

    field_meta = json.loads(row['field_metadata'] or '[]')
    # Back-compat: rebuild meta from field_names if metadata is empty
    if not field_meta and row['field_names']:
        field_meta = [{'name': n, 'type': 'text', 'options': [],
                       'default': '', 'on_state': '/Yes'}
                      for n in json.loads(row['field_names'])]

    return render_template(
        'pdf_filler/fill.html',
        upload=row,
        file_id=file_id,
        original_name=row['original_name'],
        fields=field_meta,
        has_fields=bool(field_meta),
    )


def _collect_field_values(field_meta: list, form) -> dict:
    """Build a {field_name: value} dict from submitted form data."""
    values: dict[str, str] = {}
    for meta in field_meta:
        fname = meta['name']
        ftype = meta['type']
        key   = f'f_{fname}'
        if ftype in ('text', 'multiline'):
            values[fname] = form.get(key, '')
        elif ftype == 'checkbox':
            checked = form.get(key) == 'on'
            values[fname] = meta.get('on_state', '/Yes') if checked else '/Off'
        elif ftype == 'radio':
            val = form.get(key, '')
            values[fname] = f'/{val}' if val and not val.startswith('/') else val
        elif ftype in ('select', 'listbox'):
            values[fname] = form.get(key, '')
    return values


def _write_pdf(src_path: str, field_meta: list, form,
               flatten: bool = False, annotation: str = '') -> io.BytesIO:
    """Fill a PDF in memory and return a BytesIO of the result."""
    reader = pypdf.PdfReader(src_path)
    writer = pypdf.PdfWriter()
    writer.append(reader)

    if field_meta:
        field_values = _collect_field_values(field_meta, form)
        for page in writer.pages:
            writer.update_page_form_field_values(page, field_values)
    elif annotation:
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import letter
            packet = io.BytesIO()
            c = rl_canvas.Canvas(packet, pagesize=letter)
            c.setFont('Helvetica', 12)
            c.drawString(72, 700, annotation[:200])
            c.save()
            packet.seek(0)
            overlay_r = pypdf.PdfReader(packet)
            writer.pages[0].merge_page(overlay_r.pages[0])
        except Exception as exc:
            logger.warning('Annotation overlay failed: %s', exc)

    if flatten:
        for page in writer.pages:
            annots = page.get('/Annots')
            if annots:
                keep = [ref for ref in list(annots)
                        if ref.get_object().get('/Subtype') != '/Widget']
                if keep:
                    page[pypdf.generic.NameObject('/Annots')] = pypdf.generic.ArrayObject(keep)
                else:
                    del page['/Annots']

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf


@bp.route('/fill/<file_id>', methods=['POST'])
def fill_submit(file_id: str):
    t = get_t()
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    if row is None:
        flash(t['pdf_not_found'], 'error')
        return redirect(url_for('pdf_filler.index'))

    field_meta = json.loads(row['field_metadata'] or '[]')
    if not field_meta and row['field_names']:
        field_meta = [{'name': n, 'type': 'text', 'options': [],
                       'default': '', 'on_state': '/Yes'}
                      for n in json.loads(row['field_names'])]

    src_path  = os.path.join(UPLOADS_DIR, f'{file_id}.pdf')
    base_name = os.path.splitext(row['original_name'])[0]
    out_name  = f'{base_name}_Filled.pdf'
    out_path  = os.path.join(OUTPUTS_DIR, f'{file_id}_filled.pdf')
    flatten   = request.form.get('flatten') == '1'
    annotation = request.form.get('annotation', '').strip()

    t0 = time.time()
    try:
        buf = _write_pdf(src_path, field_meta, request.form,
                         flatten=flatten, annotation=annotation)
        with open(out_path, 'wb') as fh:
            fh.write(buf.read())
        logger.info('Filled %s in %.2fs (flatten=%s)', file_id, time.time() - t0, flatten)
    except Exception as exc:
        logger.error('Fill failed for %s: %s', file_id, exc)
        flash(f"{t['pdf_fill_error']}: {exc}", 'error')
        return redirect(url_for('pdf_filler.fill', file_id=file_id))

    with get_db() as conn:
        conn.execute('UPDATE uploads SET output_name = ? WHERE id = ?',
                     (out_name, file_id))
        conn.commit()

    if request.form.get('action') == 'download':
        return send_file(out_path, as_attachment=True, download_name=out_name,
                         mimetype='application/pdf')

    return redirect(url_for('pdf_filler.preview', file_id=file_id))


@bp.route('/live/<file_id>', methods=['POST'])
def live_preview(file_id: str):
    """Return an in-memory filled PDF for the live preview panel (no DB write)."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    if row is None:
        return Response('Not found', status=404)

    field_meta = json.loads(row['field_metadata'] or '[]')
    if not field_meta and row['field_names']:
        field_meta = [{'name': n, 'type': 'text', 'options': [],
                       'default': '', 'on_state': '/Yes'}
                      for n in json.loads(row['field_names'])]

    src_path   = os.path.join(UPLOADS_DIR, f'{file_id}.pdf')
    annotation = request.form.get('annotation', '').strip()
    try:
        buf = _write_pdf(src_path, field_meta, request.form, annotation=annotation)
    except Exception as exc:
        logger.warning('Live preview failed for %s: %s', file_id, exc)
        return Response('Error', status=500)

    return Response(buf.read(), mimetype='application/pdf',
                    headers={'Cache-Control': 'no-store'})


@bp.route('/original/<file_id>')
def original_pdf(file_id: str):
    """Serve the original (unfilled) PDF inline for the preview panel."""
    src_path = os.path.join(UPLOADS_DIR, f'{file_id}.pdf')
    if not os.path.exists(src_path):
        return Response('Not found', status=404)
    return send_file(src_path, mimetype='application/pdf',
                     as_attachment=False)


@bp.route('/preview/<file_id>')
def preview(file_id: str):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    if row is None:
        flash(get_t()['pdf_not_found'], 'error')
        return redirect(url_for('pdf_filler.index'))

    out_path = os.path.join(OUTPUTS_DIR, f'{file_id}_filled.pdf')
    if not os.path.exists(out_path):
        flash(get_t()['pdf_not_found'], 'error')
        return redirect(url_for('pdf_filler.fill', file_id=file_id))

    base_name = os.path.splitext(row['original_name'])[0]
    out_name  = row['output_name'] or f'{base_name}_Filled.pdf'
    return render_template('pdf_filler/preview.html',
                           file_id=file_id,
                           out_name=out_name,
                           original_name=row['original_name'])


@bp.route('/preview/<file_id>/pdf')
def preview_pdf(file_id: str):
    """Serve the filled PDF inline for the preview iframe."""
    out_path = os.path.join(OUTPUTS_DIR, f'{file_id}_filled.pdf')
    if not os.path.exists(out_path):
        return Response('Not found', status=404)
    with get_db() as conn:
        row = conn.execute(
            'SELECT output_name FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    out_name = (row['output_name'] if row else None) or f'{file_id}_Filled.pdf'
    return send_file(out_path, mimetype='application/pdf',
                     as_attachment=False, download_name=out_name)


@bp.route('/download/<file_id>')
def download(file_id: str):
    """Direct download of the filled PDF."""
    out_path = os.path.join(OUTPUTS_DIR, f'{file_id}_filled.pdf')
    if not os.path.exists(out_path):
        flash(get_t()['pdf_not_found'], 'error')
        return redirect(url_for('pdf_filler.index'))
    with get_db() as conn:
        row = conn.execute(
            'SELECT original_name, output_name FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    if row:
        out_name = row['output_name'] or f"{os.path.splitext(row['original_name'])[0]}_Filled.pdf"
    else:
        out_name = f'{file_id}_Filled.pdf'
    return send_file(out_path, as_attachment=True, download_name=out_name,
                     mimetype='application/pdf')


@bp.route('/delete/<file_id>', methods=['POST'])
def delete(file_id: str):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()
    if row:
        for path in [
            os.path.join(UPLOADS_DIR, f'{file_id}.pdf'),
            os.path.join(OUTPUTS_DIR, f'{file_id}_filled.pdf'),
        ]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        with get_db() as conn:
            conn.execute('DELETE FROM uploads WHERE id = ?', (file_id,))
            conn.commit()
        logger.info('Deleted upload %s', file_id)
    return redirect(url_for('pdf_filler.index'))
