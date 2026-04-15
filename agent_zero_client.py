"""HTTP client for communicating with Agent Zero API."""
import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class AgentZeroClient:
    """Async HTTP client for the Agent Zero REST API."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.context_id: str = ""
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if Agent Zero is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/api/health",
                headers=self._get_headers(),
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def create_context(self) -> str:
        """Create a new chat context and return its ID."""
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/api/chat_create",
                headers=self._get_headers(),
                json={},
            )
            resp.raise_for_status()
            data = resp.json()
            ctx_id = data.get("context", data.get("id", ""))
            self.context_id = ctx_id
            logger.info(f"Created context: {ctx_id}")
            return ctx_id
        except Exception as e:
            logger.error(f"Failed to create context: {e}")
            return ""

    async def send_message(
        self,
        text: str,
        screenshot_path: Optional[str] = None,
        context_id: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Send a message to Agent Zero and return the response.
        Uses async polling to stream progress updates.
        """
        ctx = context_id or self.context_id

        # Ensure we have a context
        if not ctx:
            ctx = await self.create_context()
            self.context_id = ctx

        client = await self._get_client()

        # Build request - use multipart if screenshot attached
        if screenshot_path and Path(screenshot_path).exists():
            response = await self._send_with_attachment(
                client, text, screenshot_path, ctx
            )
        else:
            response = await self._send_json(client, text, ctx)

        return response

    async def _send_json(self, client: httpx.AsyncClient, text: str, ctx: str) -> str:
        """Send a plain text message via JSON."""
        try:
            # Send async message first
            resp = await client.post(
                f"{self.base_url}/api/message_async",
                headers=self._get_headers(),
                json={"text": text, "context": ctx},
            )
            resp.raise_for_status()
            data = resp.json()
            # Update context id if returned
            if "context" in data:
                self.context_id = data["context"]
                ctx = self.context_id

            # Poll for response
            return await self._poll_response(client, ctx)
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            raise

    async def _send_with_attachment(
        self,
        client: httpx.AsyncClient,
        text: str,
        screenshot_path: str,
        ctx: str,
    ) -> str:
        """Send message with screenshot attachment via multipart."""
        try:
            with open(screenshot_path, "rb") as f:
                img_data = f.read()

            files = {
                "text": (None, text),
                "context": (None, ctx),
                "attachments": ("screenshot.png", img_data, "image/png"),
            }
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            resp = await client.post(
                f"{self.base_url}/api/message_async",
                headers=headers,
                files=files,
            )
            resp.raise_for_status()
            data = resp.json()
            if "context" in data:
                self.context_id = data["context"]
                ctx = self.context_id

            return await self._poll_response(client, ctx)
        except Exception as e:
            logger.error(f"Send with attachment failed: {e}")
            raise

    async def _poll_response(
        self,
        client: httpx.AsyncClient,
        ctx: str,
        max_wait: float = 120.0,
        poll_interval: float = 0.8,
    ) -> str:
        """Poll Agent Zero until the agent produces a final response."""
        log_from = 0
        start = time.monotonic()
        last_response = ""

        while time.monotonic() - start < max_wait:
            await asyncio.sleep(poll_interval)
            try:
                resp = await client.post(
                    f"{self.base_url}/api/poll",
                    headers=self._get_headers(),
                    json={"context": ctx, "log_from": log_from},
                )
                resp.raise_for_status()
                data = resp.json()

                # Extract log entries
                logs = data.get("logs", [])
                if logs:
                    log_from = data.get("log_guid", log_from)

                # Look for final response in logs
                for entry in logs:
                    if entry.get("type") == "response":
                        content = entry.get("content", "")
                        if content:
                            last_response = content

                # Check if agent is done (not running)
                agent_state = data.get("agent", {})
                is_running = agent_state.get("running", True)

                if not is_running and last_response:
                    return last_response

                # Also check messages array for response
                messages = data.get("messages", [])
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if content and not is_running:
                            return content

            except Exception as e:
                logger.warning(f"Poll error: {e}")
                await asyncio.sleep(poll_interval)

        return last_response or "[Timeout: No response received]"

    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file using Agent Zero's transcribe endpoint."""
        try:
            client = await self._get_client()
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            resp = await client.post(
                f"{self.base_url}/api/transcribe",
                headers=headers,
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("text", "")
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    def reset_context(self):
        """Clear the stored context ID to start a fresh conversation."""
        self.context_id = ""
