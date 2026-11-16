import asyncio
import json
import logging
from core.event_bus import event_bus, EVENTS

logger = logging.getLogger('jarvis.api.websocket')

try:
    from fastapi import WebSocket, WebSocketDisconnect
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    WebSocket = object


class ChatWebSocket:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def handle(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("Chat WS connected")
        try:
            daemon = getattr(websocket.app.state, "daemon", None)
            agent = daemon.get_service("agent") if daemon else None
            
            while True:
                data = await websocket.receive_json()
                message = data.get("text", "")
                session_id = data.get("session_id", "default")
                
                if agent:
                    await self._stream_response(websocket, message, session_id, agent)
                else:
                    await websocket.send_json({"type": "chunk", "data": f"Echo: {message}"})
                    await websocket.send_json({"type": "complete", "full": f"Echo: {message}"})
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Chat WS error: {e}")
        finally:
            self._connections.discard(websocket)

    async def _stream_response(self, ws: WebSocket, message: str, session_id: str, agent):
        try:
            from core.session import session_manager
            session = session_manager.get_or_create(session_id, user_id="ws_user")
            session.add_message("user", message)
            
            await ws.send_json({"type": "route", "agent": "AgentExecutor"})
            
            full = ""
            async for chunk in agent.execute_stream(message, session):
                full += chunk
                await ws.send_json({"type": "chunk", "data": chunk})
                await asyncio.sleep(0)
            
            if full:
                session.add_message("assistant", full)
            await ws.send_json({"type": "complete", "full": full})
        except Exception as e:
            await ws.send_json({"type": "error", "detail": str(e)})

    async def broadcast(self, event: str, data: dict):
        payload = json.dumps({"type": event, **data})
        for ws in self._connections.copy():
            try:
                await ws.send_text(payload)
            except Exception:
                self._connections.discard(ws)

    def disconnect_all(self):
        self._connections.clear()


class EventWebSocket:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def handle(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("Events WS connected")

        queue = asyncio.Queue()

        def make_handler(evt_name):
            async def h(**data):
                serializable_data = {}
                for k, v in data.items():
                    try:
                        json.dumps(v)
                        serializable_data[k] = v
                    except Exception:
                        serializable_data[k] = str(v)
                await queue.put({"event": evt_name, "data": serializable_data})
            return h

        handlers = {}
        for key, val in EVENTS.items():
            h = make_handler(val)
            handlers[val] = h
            event_bus.on_async(val, h)

        async def send_worker():
            try:
                while True:
                    evt = await queue.get()
                    await websocket.send_json(evt)
                    queue.task_done()
            except Exception:
                pass

        worker_task = asyncio.create_task(send_worker())

        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping" or data == '{"type":"ping"}':
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Events WS error: {e}")
        finally:
            worker_task.cancel()
            self._connections.discard(websocket)
            for val, h in handlers.items():
                event_bus.off(val, h)

    async def broadcast_event(self, event: str, data: dict):
        payload = json.dumps({"event": event, "data": data})
        for ws in self._connections.copy():
            try:
                await ws.send_text(payload)
            except Exception:
                self._connections.discard(ws)

    def disconnect_all(self):
        self._connections.clear()


chat_ws = ChatWebSocket()
event_ws = EventWebSocket()
