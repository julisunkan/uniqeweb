"""Shared helper for content reports — all data stored in admin/admin.db."""
import os
import sqlite3

ADMIN_DB = os.path.join(os.path.dirname(__file__), 'admin', 'admin.db')


def _get_db():
    conn = sqlite3.connect(ADMIN_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_reports_table():
    """Create the reports table if it doesn't exist yet."""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            app             TEXT NOT NULL,
            content_ref     TEXT DEFAULT '',
            content_preview TEXT DEFAULT '',
            reason          TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            admin_note      TEXT DEFAULT '',
            ip              TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at     TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def submit_report(app, content_ref, content_preview, reason, ip=None):
    init_reports_table()
    conn = _get_db()
    conn.execute(
        """INSERT INTO reports (app, content_ref, content_preview, reason, ip)
           VALUES (?, ?, ?, ?, ?)""",
        (app, content_ref or '', (content_preview or '')[:500], reason, ip or '')
    )
    conn.commit()
    conn.close()


def get_all_reports():
    init_reports_table()
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM reports ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_count():
    init_reports_table()
    conn = _get_db()
    row = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status='pending'"
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def resolve_report(report_id, status, admin_note=''):
    init_reports_table()
    conn = _get_db()
    conn.execute(
        """UPDATE reports SET status=?, admin_note=?, resolved_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (status, admin_note or '', report_id)
    )
    conn.commit()
    conn.close()
