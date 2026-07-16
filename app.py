"""Main application factory — registers all five app blueprints + admin panel."""
import os
from flask import Flask, render_template
from extensions import socketio


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-change-me')

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

    return app


app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
