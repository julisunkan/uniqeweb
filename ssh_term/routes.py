"""SSH Terminal Blueprint + SocketIO event handlers."""
import threading
import time

import paramiko
from flask import Blueprint, render_template, request
from flask_socketio import emit

from extensions import socketio

bp = Blueprint('ssh_term', __name__, template_folder='templates')

# ── Session store ────────────────────────────────────────────────────────────
_sessions = {}   # { sid: {'client': paramiko.SSHClient, 'channel': paramiko.Channel} }
_lock = threading.Lock()


# ── Routes ───────────────────────────────────────────────────────────────────

@bp.route('/')
def index():
    return render_template('ssh_term/index.html')


@bp.route('/terminal')
def terminal():
    host = request.args.get('host', '')
    port = request.args.get('port', '22')
    user = request.args.get('user', '')
    return render_template('ssh_term/terminal.html', host=host, port=port, user=user)


# ── Background reader thread ──────────────────────────────────────────────────

def _read_ssh(sid, channel, app):
    with app.app_context():
        while True:
            try:
                if channel.exit_status_ready():
                    socketio.emit('ssh_output',
                                  {'data': '\r\nConnection closed.\r\n'},
                                  room=sid)
                    break
                if channel.recv_ready():
                    data = channel.recv(4096).decode('utf-8', errors='replace')
                    socketio.emit('ssh_output', {'data': data}, room=sid)
                else:
                    time.sleep(0.05)
            except Exception:
                socketio.emit('ssh_output',
                              {'data': '\r\nConnection lost.\r\n'},
                              room=sid)
                break

        # Clean up
        with _lock:
            session = _sessions.pop(sid, None)
        if session:
            try:
                session['channel'].close()
            except Exception:
                pass
            try:
                session['client'].close()
            except Exception:
                pass


# ── SocketIO events ───────────────────────────────────────────────────────────

@socketio.on('ssh_connect')
def handle_ssh_connect(data):
    from flask import current_app
    sid = request.sid
    host = data.get('host', '')
    port = data.get('port', 22)
    username = data.get('username', '')
    password = data.get('password', '')

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=int(port), username=username,
                       password=password, timeout=10)

        transport = client.get_transport()
        channel = transport.open_session()
        channel.get_pty(term='xterm-256color', width=220, height=50)
        channel.invoke_shell()

        with _lock:
            _sessions[sid] = {'client': client, 'channel': channel}

        app = current_app._get_current_object()
        threading.Thread(
            target=_read_ssh,
            args=(sid, channel, app),
            daemon=True
        ).start()

        emit('ssh_connected', {'host': host, 'username': username})

    except Exception as e:
        emit('ssh_error', {'message': str(e)})


@socketio.on('ssh_input')
def handle_ssh_input(data):
    sid = request.sid
    with _lock:
        session = _sessions.get(sid)
    if session:
        try:
            session['channel'].send(data.get('input', ''))
        except Exception:
            pass


@socketio.on('ssh_resize')
def handle_ssh_resize(data):
    sid = request.sid
    with _lock:
        session = _sessions.get(sid)
    if session:
        try:
            session['channel'].resize_pty(
                width=int(data.get('cols', 80)),
                height=int(data.get('rows', 24))
            )
        except Exception:
            pass


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    with _lock:
        session = _sessions.pop(sid, None)
    if session:
        try:
            session['channel'].close()
        except Exception:
            pass
        try:
            session['client'].close()
        except Exception:
            pass
