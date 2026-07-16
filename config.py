"""
Shared configuration reader.
Reads settings from admin/admin.db first, then falls back to environment variables.
Import get_setting() or get_groq_key() in any blueprint instead of reading os.environ directly.
"""
import os
import sqlite3

ADMIN_DB = os.path.join(os.path.dirname(__file__), 'admin', 'admin.db')

# Default values for every known setting key
DEFAULTS = {
    'groq_api_key':             '',
    'audio_tts_lang':           'en',
    'audio_max_chars':          '50000',
    'flashcard_default_count':  '15',
    'flashcard_max_count':      '50',
    'pdf_max_size_mb':          '10',
    'ssh_max_sessions':         '5',
    'email_default_template':   'modern',
    'email_default_accent':     '#ef4444',
    'app_audio_enabled':        '1',
    'app_pdf_enabled':          '1',
    'app_ssh_enabled':          '1',
    'app_email_enabled':        '1',
    'app_flash_enabled':        '1',
}


def get_setting(key: str, default: str | None = None) -> str:
    """Return value from admin DB, falling back to DEFAULTS."""
    if default is None:
        default = DEFAULTS.get(key, '')
    try:
        conn = sqlite3.connect(ADMIN_DB)
        row = conn.execute(
            'SELECT value FROM settings WHERE key = ?', (key,)
        ).fetchone()
        conn.close()
        if row and row[0] is not None and row[0] != '':
            return row[0]
    except Exception:
        pass
    return default


def get_groq_key() -> str:
    """Return Groq API key: admin DB takes priority, then GROQ_API_KEY env var."""
    from_db = get_setting('groq_api_key')
    return from_db or os.environ.get('GROQ_API_KEY', '')


def app_enabled(app_name: str) -> bool:
    """Check if a specific app is enabled (audio/pdf/ssh/email/flash)."""
    return get_setting(f'app_{app_name}_enabled', '1') == '1'
