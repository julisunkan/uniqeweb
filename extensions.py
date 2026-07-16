"""Shared Flask extensions (instantiated once, init_app() called in app factory)."""
from flask_socketio import SocketIO

socketio = SocketIO()
