"""PDF Form Filler — Blueprint routes."""
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime

import pypdf
from flask import (Blueprint, redirect, render_template, request,
                   send_file, url_for, flash)

bp = Blueprint('pdf_filler', __name__, template_folder='templates')

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'pdf.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


# ── DB helpers ────────────────────────────────────────────────────────────────
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


init_db()


# ── Routes ────────────────────────────────────────────────────────────────────
@bp.route('/')
def index():
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM uploads ORDER BY created_at DESC LIMIT 20'
        ).fetchall()
    return render_template('pdf_filler/index.html', uploads=rows)


@bp.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('pdf_file')
    if not f or not f.filename:
        flash('Please select a PDF file.', 'error')
        return redirect(url_for('pdf_filler.index'))

    if not f.filename.lower().endswith('.pdf'):
        flash('Only PDF files are supported.', 'error')
        return redirect(url_for('pdf_filler.index'))

    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOADS_DIR, f'{file_id}.pdf')
    f.save(save_path)

    # Detect form fields
    try:
        reader = pypdf.PdfReader(save_path)
        text_fields = reader.get_form_text_fields() or {}
        all_fields = reader.get_fields() or {}
        # Merge both sets
        combined = {**all_fields, **text_fields}
        field_names = list(combined.keys())
        has_fields = 1 if field_names else 0
    except Exception:
        field_names = []
        has_fields = 0

    with get_db() as conn:
        conn.execute(
            'INSERT INTO uploads (id, original_name, has_fields, field_names) VALUES (?, ?, ?, ?)',
            (file_id, f.filename, has_fields, json.dumps(field_names))
        )
        conn.commit()

    return redirect(url_for('pdf_filler.fill', file_id=file_id))


@bp.route('/fill/<file_id>', methods=['GET'])
def fill(file_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()

    if row is None:
        flash('File not found.', 'error')
        return redirect(url_for('pdf_filler.index'))

    field_names = json.loads(row['field_names']) if row['field_names'] else []
    return render_template(
        'pdf_filler/fill.html',
        upload=row,
        field_names=field_names
    )


@bp.route('/fill/<file_id>', methods=['POST'])
def fill_submit(file_id):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM uploads WHERE id = ?', (file_id,)
        ).fetchone()

    if row is None:
        flash('File not found.', 'error')
        return redirect(url_for('pdf_filler.index'))

    original_path = os.path.join(UPLOADS_DIR, f'{file_id}.pdf')
    out_path = os.path.join(OUTPUTS_DIR, f'{file_id}_filled.pdf')
    field_names = json.loads(row['field_names']) if row['field_names'] else []

    if row['has_fields'] and field_names:
        # Build field values dict from form POST
        field_values = {}
        for name in field_names:
            val = request.form.get(f'field_{name}', '')
            field_values[name] = val

        try:
            reader = pypdf.PdfReader(original_path)
            writer = pypdf.PdfWriter()
            writer.append(reader)
            for page in writer.pages:
                try:
                    writer.update_page_form_field_values(page, field_values)
                except Exception:
                    pass
            with open(out_path, 'wb') as fh:
                writer.write(fh)
        except Exception as e:
            flash(f'Error filling PDF: {e}', 'error')
            return redirect(url_for('pdf_filler.fill', file_id=file_id))

    else:
        # No form fields — use annotation text overlay with reportlab
        annotation_text = request.form.get('annotation', '').strip()
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter

            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)
            c.setFont("Helvetica", 12)
            c.drawString(72, 700, annotation_text[:200])
            c.save()
            packet.seek(0)

            overlay_reader = pypdf.PdfReader(packet)
            original_reader = pypdf.PdfReader(original_path)
            writer = pypdf.PdfWriter()

            page = original_reader.pages[0]
            page.merge_page(overlay_reader.pages[0])
            writer.add_page(page)
            for i in range(1, len(original_reader.pages)):
                writer.add_page(original_reader.pages[i])

            with open(out_path, 'wb') as fh:
                writer.write(fh)
        except Exception as e:
            flash(f'Error creating annotated PDF: {e}', 'error')
            return redirect(url_for('pdf_filler.fill', file_id=file_id))

    original_name = row['original_name'] or 'filled'
    base_name = os.path.splitext(original_name)[0]
    download_name = f'{base_name}_filled.pdf'

    return send_file(out_path, as_attachment=True, download_name=download_name)
