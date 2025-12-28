"""FastAPI application for LMServer - OpenAI-compatible local LLM gateway."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from .config import settings
from .dns import register_dns, deregister_dns
from .proxy import proxy, get_semaphore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    # Startup
    logger.info(f"Starting LMServer v0.1.0")
    logger.info(f"Backend: {settings.llama_server_url}")
    logger.info(f"Max concurrent requests: {settings.max_concurrent_requests}")

    # Initialize semaphore
    get_semaphore()

    # Register with DNS
    await register_dns()

    yield

    # Shutdown
    logger.info("Shutting down LMServer")
    await deregister_dns()


app = FastAPI(
    title="LMServer",
    description="OpenAI-compatible local LLM gateway for Tailscale networks",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Health endpoints ---


@app.get("/health")
async def health():
    """Health check endpoint."""
    backend_health = await proxy.health_check()
    return {
        "status": "ok",
        "backend": backend_health,
        "config": {
            "max_concurrent_requests": settings.max_concurrent_requests,
            "default_model": settings.default_model,
        },
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "lmserver",
        "version": "0.1.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/health",
        },
    }


# --- OpenAI-compatible endpoints ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False

    class Config:
        extra = "allow"  # Allow additional OpenAI params


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    Proxies to llama-server with concurrency limiting.
    """
    # Build request body, preserving extra fields
    request_body = request.model_dump(exclude_none=True)

    # Set default model if not specified
    if not request_body.get("model"):
        request_body["model"] = settings.default_model

    try:
        if request.stream:
            # Streaming response
            return StreamingResponse(
                proxy.chat_completions_stream(request_body),
                media_type="text/event-stream",
            )
        else:
            # Non-streaming response
            result = await proxy.chat_completions(request_body)
            return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=502, detail=f"Backend error: {str(e)}")


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    return await proxy.list_models()


# --- Queue status endpoint (for merkle batch monitoring) ---


@app.get("/v1/queue/status")
async def queue_status():
    """
    Get current queue status for monitoring batch jobs.

    Useful for merkle project to understand backpressure.
    """
    sem = get_semaphore()
    # Semaphore doesn't expose waiters count directly, but we can infer availability
    available = sem._value if hasattr(sem, "_value") else "unknown"

    return {
        "max_concurrent": settings.max_concurrent_requests,
        "available_slots": available,
        "backend_url": settings.llama_server_url,
    }


# --- Convenience: raw proxy for other llama-server endpoints ---


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def proxy_fallback(path: str, request: Request):
    """
    Fallback proxy for other llama-server v1 endpoints.

    Passes through requests like /v1/embeddings, /v1/completions, etc.
    """
    import httpx

    try:
        body = await request.body()
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.request(
                method=request.method,
                url=f"{settings.llama_server_url}/v1/{path}",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "lmserver.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

