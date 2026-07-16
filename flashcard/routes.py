"""Flashcard blueprint — AI-powered flashcard generator."""
import os
import json
import sqlite3
import tempfile
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from groq import Groq
from config import get_groq_key, get_setting
from translations import get_t

bp = Blueprint('flashcard', __name__, template_folder='templates')

DB_PATH = os.path.join(os.path.dirname(__file__), 'flashcard.db')


# ── Database helpers ──────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            card_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


init_db()


# ── Text extraction helpers ───────────────────────────────────────────────────

def extract_text_from_file(file_storage):
    filename = file_storage.filename.lower()
    if filename.endswith('.pdf'):
        import fitz
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            file_storage.save(tmp.name)
            doc = fitz.open(tmp.name)
            text = ' '.join(page.get_text() for page in doc)
            doc.close()
        os.unlink(tmp.name)
        return text
    elif filename.endswith('.docx'):
        from docx import Document
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            file_storage.save(tmp.name)
            doc = Document(tmp.name)
            text = ' '.join(p.text for p in doc.paragraphs)
        os.unlink(tmp.name)
        return text
    else:
        # Plain text
        return file_storage.read().decode('utf-8', errors='replace')


# ── Routes ────────────────────────────────────────────────────────────────────

@bp.route('/')
def index():
    conn = get_db()
    decks = conn.execute(
        'SELECT * FROM decks ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('flashcard/index.html', decks=decks)


@bp.route('/generate', methods=['POST'])
def generate():
    title = request.form.get('title', '').strip()
    card_count = int(request.form.get('card_count', int(get_setting('flashcard_default_count', '15'))))
    max_count  = int(get_setting('flashcard_max_count', '50'))
    card_count = max(5, min(max_count, card_count))

    if not title:
        flash(get_t()['flash_no_title'], 'error')
        return redirect(url_for('flashcard.index'))

    # Extract text
    text = ''
    uploaded_file = request.files.get('file')
    if uploaded_file and uploaded_file.filename:
        try:
            text = extract_text_from_file(uploaded_file)
        except Exception as e:
            flash(f"{get_t()['flash_file_error']}: {e}", 'error')
            return redirect(url_for('flashcard.index'))
    else:
        text = request.form.get('text', '').strip()

    if not text:
        flash(get_t()['flash_no_content'], 'error')
        return redirect(url_for('flashcard.index'))

    # Call Groq
    groq_key = get_groq_key()
    if not groq_key:
        flash(get_t()['flash_no_groq'], 'error')
        return redirect(url_for('flashcard.index'))

    try:
        client = Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {
                    'role': 'system',
                    'content': 'You are an expert educator. Generate concise, clear flashcards from the given text.'
                },
                {
                    'role': 'user',
                    'content': (
                        f'Create exactly {card_count} flashcards from this text.\n'
                        'Return ONLY a JSON array, no other text, no markdown fences:\n'
                        '[\n'
                        '  {"q": "Question here?", "a": "Answer here."},\n'
                        '  ...\n'
                        ']\n'
                        f'Text to study:\n{text[:8000]}'
                    )
                }
            ],
            temperature=0.7,
        )
        response_text = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        if response_text.startswith('```'):
            lines = response_text.splitlines()
            response_text = '\n'.join(
                line for line in lines
                if not line.strip().startswith('```')
            )

        cards_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        flash(f"{get_t()['flash_parse_error']} ({e})", 'error')
        return redirect(url_for('flashcard.index'))
    except Exception as e:
        flash(f"{get_t()['flash_gen_error']}: {e}", 'error')
        return redirect(url_for('flashcard.index'))

    if not cards_data:
        flash(get_t()['flash_no_cards'], 'error')
        return redirect(url_for('flashcard.index'))

    # Save to DB
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO decks (title, card_count) VALUES (?, ?)',
            (title, len(cards_data))
        )
        deck_id = cur.lastrowid
        for card in cards_data:
            q = card.get('q', '').strip()
            a = card.get('a', '').strip()
            if q and a:
                conn.execute(
                    'INSERT INTO cards (deck_id, question, answer) VALUES (?, ?, ?)',
                    (deck_id, q, a)
                )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('flashcard.study', deck_id=deck_id))


@bp.route('/study/<int:deck_id>')
def study(deck_id):
    conn = get_db()
    deck = conn.execute('SELECT * FROM decks WHERE id = ?', (deck_id,)).fetchone()
    if not deck:
        conn.close()
        flash(get_t()['flash_deck_not_found'], 'error')
        return redirect(url_for('flashcard.index'))
    cards = conn.execute(
        'SELECT * FROM cards WHERE deck_id = ? ORDER BY id', (deck_id,)
    ).fetchall()
    conn.close()
    return render_template('flashcard/study.html', deck=deck, cards=cards)


@bp.route('/delete/<int:deck_id>', methods=['POST'])
def delete(deck_id):
    conn = get_db()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('DELETE FROM decks WHERE id = ?', (deck_id,))
    conn.commit()
    conn.close()
    flash(get_t()['flash_deck_deleted'], 'success')
    return redirect(url_for('flashcard.index'))


@bp.route('/api/cards/<int:deck_id>')
def api_cards(deck_id):
    conn = get_db()
    cards = conn.execute(
        'SELECT id, question, answer FROM cards WHERE deck_id = ? ORDER BY id',
        (deck_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(c) for c in cards])
