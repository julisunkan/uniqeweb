# Mobile App Suite

Five independent mobile-first web apps running under a single Flask server.

## Stack
- **Backend**: Python / Flask 3 + Flask-SocketIO (eventlet)
- **Database**: SQLite (each app has its own `.db` file in its module directory)
- **AI**: Groq API (`llama-3.3-70b-versatile`) — Email Sig & Flashcard apps
- **TTS**: gTTS (Google Text-to-Speech) — Audiobook app
- **PDF**: PyMuPDF (text extraction), pypdf (form fields), reportlab (overlay)
- **SSH**: paramiko + xterm.js

## Run
```
python app.py
```
Serves on port 5000.

## Routes

| App | URL | Description |
|-----|-----|-------------|
| Home | `/` | Landing page with all 5 app cards |
| Audiobooks | `/audio` | Text/PDF/DOCX → MP3 audiobook |
| PDF Filler | `/pdf` | Upload PDF → fill form fields → export |
| SSH Terminal | `/ssh` | Browser SSH client via WebSocket |
| Email Signature | `/email` | Visual builder → copy/download HTML sig |
| AI Flashcards | `/flash` | Paste/upload → Groq generates study cards |

## Directory Structure
```
app.py               # Main factory — registers all blueprints
extensions.py        # socketio = SocketIO() singleton
requirements.txt
static/
  css/mobile.css     # Shared design system
  js/mobile.js       # Shared utilities (toast, upload, tabs)
templates/
  base.html          # Mobile shell base template
  index.html         # Landing page

audio/               # Audiobooks Generator
  routes.py          # Blueprint 'audio'
  audio.db
  outputs/           # Generated MP3s

pdf_filler/          # PDF Form Filler
  routes.py          # Blueprint 'pdf_filler'
  pdf.db
  uploads/ outputs/

ssh_term/            # SSH Terminal
  routes.py          # Blueprint 'ssh_term' + socketio events

email_sig/           # Email Signature Generator
  routes.py          # Blueprint 'email_sig'

flashcard/           # AI Flashcard Generator
  routes.py          # Blueprint 'flashcard'
  flashcard.db
```

## Environment Variables / Secrets
| Key | Used by | Notes |
|-----|---------|-------|
| `SESSION_SECRET` | All | Flask session secret |
| `GROQ_API_KEY` | Email Sig, Flashcards | Required for AI features |

Set `GROQ_API_KEY` in Replit Secrets to enable AI tagline generation and flashcard creation.

## User Preferences
- Mobile-first design; apps must look like native mobile apps
- Keep Flask/SQLite stack — do not migrate
- Each app is independent in its own directory
