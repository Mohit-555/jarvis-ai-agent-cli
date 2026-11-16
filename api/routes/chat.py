import logging

logger = logging.getLogger('jarvis.api.chat')

try:
    from fastapi import APIRouter, HTTPException, Request
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    APIRouter = object
    BaseModel = object
    Request = object

if HAS_FASTAPI:
    router = APIRouter()

    class ChatRequest(BaseModel):
        message: str
        session_id: str = "default"
        mode: str = "auto"
        stream: bool = False
        options: dict = {}

    class ChatResponse(BaseModel):
        response: str
        session_id: str
        agent: str = ""

    @router.post("/chat", response_model=ChatResponse)
    async def send_message(req: ChatRequest, request: Request):
        try:
            daemon = getattr(request.app.state, "daemon", None)
            if not daemon:
                raise HTTPException(status_code=500, detail="Daemon not initialized")
            agent = daemon.get_service("agent")
            if not agent:
                raise HTTPException(status_code=500, detail="Agent executor not initialized")

            from core.session import session_manager
            session = session_manager.get_or_create(req.session_id, user_id="api_user")

            if req.stream:
                return _handle_stream(agent, session, req)

            session.add_message("user", req.message)
            result = await agent.execute(req.message, session)
            session.add_message("assistant", result)
            return ChatResponse(response=result, session_id=session.session_id, agent="AgentExecutor")
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def _handle_stream(agent, session, req):
        from fastapi.responses import StreamingResponse
        import asyncio

        async def generate():
            session.add_message("user", req.message)
            full_response = ""
            async for chunk in agent.execute_stream(req.message, session):
                full_response += chunk
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0)
            if full_response:
                session.add_message("assistant", full_response)
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
else:
    router = None
