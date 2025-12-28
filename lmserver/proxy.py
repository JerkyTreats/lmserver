"""Proxy layer to llama-server with concurrency control."""

import asyncio
import logging
import time
from typing import AsyncIterator

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# Semaphore for concurrency limiting
_inference_semaphore: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:
    """Get or create the inference semaphore."""
    global _inference_semaphore
    if _inference_semaphore is None:
        _inference_semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        logger.info(f"Initialized inference semaphore with max_concurrent={settings.max_concurrent_requests}")
    return _inference_semaphore


class LlamaServerProxy:
    """Async proxy to llama-server backend."""

    def __init__(self):
        self.base_url = settings.llama_server_url
        self.timeout = settings.request_timeout

    async def health_check(self) -> dict:
        """Check if llama-server is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return {"status": "ok", "llama_server": response.json()}
        except httpx.RequestError as e:
            return {"status": "error", "error": str(e)}

    async def chat_completions(self, request_body: dict) -> dict:
        """
        Proxy a chat completion request to llama-server.

        Uses semaphore to limit concurrent requests.
        """
        semaphore = get_semaphore()

        # Track queue position for observability
        queue_start = time.monotonic()

        async with semaphore:
            queue_time = time.monotonic() - queue_start
            if queue_time > 0.1:  # Log if we had to wait
                logger.info(f"Request queued for {queue_time:.2f}s before processing")

            inference_start = time.monotonic()

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        json=request_body,
                    )
                    response.raise_for_status()

                    inference_time = time.monotonic() - inference_start
                    logger.debug(f"Inference completed in {inference_time:.2f}s")

                    return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"llama-server error: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"llama-server connection error: {e}")
                raise

    async def chat_completions_stream(self, request_body: dict) -> AsyncIterator[bytes]:
        """
        Proxy a streaming chat completion request to llama-server.

        Yields SSE chunks as they arrive.
        """
        semaphore = get_semaphore()

        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/v1/chat/completions",
                        json=request_body,
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            yield chunk

            except httpx.HTTPStatusError as e:
                logger.error(f"llama-server stream error: {e.response.status_code}")
                raise
            except httpx.RequestError as e:
                logger.error(f"llama-server stream connection error: {e}")
                raise

    async def list_models(self) -> dict:
        """Get list of available models from llama-server."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                return response.json()
        except httpx.RequestError:
            # Fallback: return configured default model
            return {
                "object": "list",
                "data": [
                    {
                        "id": settings.default_model,
                        "object": "model",
                        "owned_by": "local",
                    }
                ],
            }


# Singleton proxy instance
proxy = LlamaServerProxy()

