"""Main application factory — registers all five app blueprints + admin panel."""
import os
from flask import Flask, render_template
from extensions import socketio


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-change-me')

    # ── i18n context processor ────────────────────────────────────────────────
    from translations import get_t, get_locale, TRANSLATIONS

    @app.context_processor
    def inject_translations():
        return {'t': get_t(), 'lang': get_locale()}

    # ── Language switcher route ───────────────────────────────────────────────
    from flask import session as flask_session, request as flask_request, redirect

    @app.route('/set-lang/<lang>')
    def set_lang(lang):
        if lang in TRANSLATIONS:
            flask_session['lang'] = lang
        return redirect(flask_request.referrer or '/')

    # ── Register blueprints ───────────────────────────────────────────────────
    from audio.routes import bp as audio_bp
    from pdf_filler.routes import bp as pdf_bp
    from ssh_term.routes import bp as ssh_bp
    from email_sig.routes import bp as email_bp
    from flashcard.routes import bp as flash_bp
    from admin.routes import bp as admin_bp

    app.register_blueprint(audio_bp,  url_prefix='/audio')
    app.register_blueprint(pdf_bp,    url_prefix='/pdf')
    app.register_blueprint(ssh_bp,    url_prefix='/ssh')
    app.register_blueprint(email_bp,  url_prefix='/email')
    app.register_blueprint(flash_bp,  url_prefix='/flash')
    app.register_blueprint(admin_bp,  url_prefix='/julisunkan')

    # ── SocketIO (used by SSH terminal) ───────────────────────────────────────
    socketio.init_app(app, cors_allowed_origins='*', async_mode='gevent',
                      logger=False, engineio_logger=False)

    # ── Home / landing page ───────────────────────────────────────────────────
    @app.route('/')
    def index():
        return render_template('index.html')

    # ── Service Worker — must be served from root for full-app scope ──────────
    import mimetypes
    from flask import send_from_directory
    @app.route('/sw.js')
    def service_worker():
        response = send_from_directory(
            os.path.join(app.root_path, 'static'),
            'sw.js',
            mimetype='application/javascript'
        )
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache'
        return response

    return app


app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
