import threading
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Jarvis - Multi-Agent Assistant</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; height: 100vh; display: flex; flex-direction: column; }
        header { background: #161b22; padding: 16px 24px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 12px; }
        header h1 { font-size: 18px; color: #58a6ff; }
        .status { margin-left: auto; font-size: 13px; color: #8b949e; }
        .status.online { color: #3fb950; }
        #chat { flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 12px; }
        .msg { max-width: 85%; padding: 10px 14px; border-radius: 8px; line-height: 1.5; font-size: 14px; }
        .msg p { margin: 4px 0; }
        .msg code { background: #1c2128; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
        .user { background: #1f6feb; align-self: flex-end; }
        .assistant { background: #21262d; align-self: flex-start; border: 1px solid #30363d; }
        .route { align-self: center; font-size: 11px; color: #58a6ff; background: #0d1117; padding: 2px 10px; border-radius: 10px; border: 1px solid #30363d; }
        #input-area { padding: 12px 24px; border-top: 1px solid #30363d; display: flex; gap: 8px; background: #161b22; }
        #input { flex: 1; background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 10px 12px; font-size: 14px; outline: none; }
        #input:focus { border-color: #58a6ff; }
        button { background: #238636; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 14px; cursor: pointer; }
        button:hover { background: #2ea043; }
        button.secondary { background: #21262d; border: 1px solid #30363d; }
        button.secondary:hover { background: #30363d; }
    </style>
</head>
<body>
    <header>
        <h1>Jarvis</h1>
        <span class="status online">Online</span>
        <button class="secondary" onclick="resetChat()" style="margin-left:auto">Reset</button>
    </header>
    <div id="chat"></div>
    <div id="input-area">
        <input id="input" type="text" placeholder="Type a message..." autofocus />
        <button onclick="sendMsg()">Send</button>
    </div>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <script>
        const socket = io();
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');

        socket.on('connect', () => console.log('connected'));
        socket.on('route', (data) => {
            const div = document.createElement('div');
            div.className = 'route';
            div.textContent = 'Agent: ' + data.agent;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        });
        socket.on('chunk', (data) => {
            let el = document.getElementById('stream-msg');
            if (!el) {
                el = document.createElement('div');
                el.id = 'stream-msg';
                el.className = 'msg assistant';
                chat.appendChild(el);
            }
            el.innerHTML += data;
            chat.scrollTop = chat.scrollHeight;
        });
        socket.on('complete', () => {
            const el = document.getElementById('stream-msg');
            if (el) el.removeAttribute('id');
        });
        socket.on('transcript', (data) => {
            const div = document.createElement('div');
            div.className = 'msg user';
            div.textContent = data.text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        });

        function sendMsg() {
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            const div = document.createElement('div');
            div.className = 'msg user';
            div.textContent = text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
            socket.emit('message', { text });
        }

        input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMsg(); });

        function resetChat() {
            chat.innerHTML = '';
            socket.emit('reset');
        }
    </script>
</body>
</html>"""


class GUI:
    def __init__(self, daemon=None, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.daemon = daemon
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self._register_routes()

    def _register_routes(self):
        @self.app.route("/")
        def index():
            return render_template_string(HTML)

        @self.socketio.on("message")
        def handle_message(data):
            text = data["text"]
            emit("transcript", {"text": text})

            agent = self.daemon.get_service("agent") if self.daemon else None
            if not agent:
                emit("chunk", "Agent system not available.")
                emit("complete")
                return

            from core.session import session_manager
            session = session_manager.get_or_create("gui_session", user_id="gui_user")
            session.add_message("user", text)

            emit("route", {"agent": "AgentExecutor"})

            import asyncio

            async def run_agent():
                full = ""
                async for chunk in agent.execute_stream(text, session):
                    full += chunk
                    emit("chunk", chunk.replace("\n", "<br>"))
                if full:
                    session.add_message("assistant", full)
                emit("complete")

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(run_agent())
            except Exception as e:
                emit("chunk", f"Error: {e}")
                emit("complete")
            finally:
                loop.close()

        @self.socketio.on("reset")
        def handle_reset():
            from core.session import session_manager
            session = session_manager.get_session("gui_session")
            if session:
                session.messages.clear()

    def run(self):
        print(f"Jarvis GUI running at http://{self.host}:{self.port}")
        self.socketio.run(self.app, host=self.host, port=self.port, debug=False, allow_unsafe_werkzeug=True)
