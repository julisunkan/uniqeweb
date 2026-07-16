---
name: Mobile App Suite architecture
description: Five-blueprint Flask app structure, naming conventions, and socketio wiring
---

## Blueprint naming (must match app.py registrations)
| Module dir   | Blueprint name | url_prefix |
|-------------|---------------|------------|
| audio/       | audio         | /audio     |
| pdf_filler/  | pdf_filler    | /pdf       |
| ssh_term/    | ssh_term      | /ssh       |
| email_sig/   | email_sig     | /email     |
| flashcard/   | flashcard     | /flash     |

## socketio singleton
- Defined in `extensions.py` as `socketio = SocketIO()`
- `app.py` calls `socketio.init_app(app, async_mode='eventlet', ...)`
- `ssh_term/routes.py` imports: `from extensions import socketio`
- Never import directly from flask_socketio in sub-modules (breaks singleton pattern)

## Template structure
- All extend `templates/base.html` (app-level, not module-level)
- Each module's template folder: `<module>/templates/<module>/<file>.html`
- Body class sets per-app accent: app-audio / app-pdf / app-ssh / app-email / app-flash

## Per-app databases
- Each module opens its own SQLite file via `sqlite3.connect(DB_PATH)` directly
- Background threads (TTS, SSH reader) use direct sqlite3 connections, NOT flask g

**Why:** Independent directories + separate DBs means each app is fully self-contained and can be moved/removed without affecting others.
