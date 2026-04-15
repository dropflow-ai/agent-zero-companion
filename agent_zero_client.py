"""HTTP client for communicating with Agent Zero API.

Supports session-based authentication (login with username/password)
and API key authentication (X-API-KEY header).
"""
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

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        username: str = "",
        password: str = "",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = timeout
        self.context_id: str = ""
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Use a cookie jar to maintain session cookies across requests
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,  # Don't follow redirects - detect auth failures
            )
            self._authenticated = False
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._authenticated = False

    async def login(self) -> bool:
        """Authenticate with Agent Zero using username/password.

        POSTs form data to /login endpoint. On success, the session
        cookie is stored in the httpx client's cookie jar.

        Returns True if login succeeded or no login is required.
        """
        if not self.username:
            logger.info("No username configured, skipping login")
            return True

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
                follow_redirects=False,
            )

            # Successful login returns 302 redirect to / (index)
            if resp.status_code in (302, 303):
                location = resp.headers.get("location", "")
                if "/login" not in location:
                    self._authenticated = True
                    logger.info("Login successful")
                    return True
                else:
                    logger.error("Login failed: redirected back to login (bad credentials)")
                    return False
            elif resp.status_code == 200:
                # Some setups return 200 on success
                text = resp.text
                if "Invalid Credentials" in text or "login" in text.lower()[:200]:
                    logger.error("Login failed: invalid credentials")
                    return False
                self._authenticated = True
                logger.info("Login successful (200)")
                return True
            else:
                logger.error(f"Login failed: HTTP {resp.status_code}")
                return False

        except Exception as e:
            logger.error(f"Login request failed: {e}")
            return False

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have an active session. Login if needed."""
        if self._authenticated:
            return True
        if self.username:
            return await self.login()
        return True  # No auth configured

    async def _api_request(
        self,
        method: str,
        path: str,
        json_data: dict = None,
        headers: dict = None,
        files: dict = None,
        timeout: float = None,
    ) -> httpx.Response:
        """Make an authenticated API request.

        Handles 302 redirects to /login by re-authenticating and retrying.
        """
        client = await self._get_client()
        await self._ensure_authenticated()

        url = f"{self.base_url}{path}"
        req_headers = headers or self._get_headers()
        req_timeout = timeout or self.timeout

        for attempt in range(2):  # Try twice: once normally, once after re-login
            if files:
                # Multipart upload - don't set Content-Type
                h = {k: v for k, v in req_headers.items() if k != "Content-Type"}
                resp = await client.post(url, headers=h, files=files, timeout=req_timeout)
            elif method.upper() == "GET":
                resp = await client.get(url, headers=req_headers, timeout=req_timeout)
            else:
                resp = await client.post(url, headers=req_headers, json=json_data, timeout=req_timeout)

            # Check for auth redirect (302 to /login)
            if resp.status_code in (302, 303):
                location = resp.headers.get("location", "")
                if "/login" in location:
                    if attempt == 0 and self.username:
                        logger.warning("Session expired, re-authenticating...")
                        self._authenticated = False
                        if await self.login():
                            continue  # Retry the request
                    raise AuthenticationError(
                        "Authentication required. Please check your login credentials."
                    )

            return resp

        raise AuthenticationError("Failed to authenticate after retry")

    async def health_check(self) -> bool:
        """Check if Agent Zero is reachable."""
        try:
            client = await self._get_client()
            # Health endpoint typically doesn't require auth
            resp = await client.get(
                f"{self.base_url}/api/health",
                headers=self._get_headers(),
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def check_auth_required(self) -> bool:
        """Check if the Agent Zero instance requires authentication.

        Returns True if login is required, False if open access.
        """
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/",
                follow_redirects=False,
                timeout=5.0,
            )
            # If we get redirected to /login, auth is required
            if resp.status_code in (302, 303):
                location = resp.headers.get("location", "")
                return "/login" in location
            return False
        except Exception:
            return False

    async def create_context(self) -> str:
        """Create a new chat context and return its ID."""
        try:
            resp = await self._api_request("POST", "/api/chat_create", json_data={})
            resp.raise_for_status()
            data = resp.json()
            ctx_id = data.get("ctxid", data.get("context", data.get("id", "")))
            self.context_id = ctx_id
            logger.info(f"Created context: {ctx_id}")
            return ctx_id
        except AuthenticationError:
            raise
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

        # Build request - use multipart if screenshot attached
        if screenshot_path and Path(screenshot_path).exists():
            response = await self._send_with_attachment(text, screenshot_path, ctx)
        else:
            response = await self._send_json(text, ctx)

        return response

    async def _send_json(self, text: str, ctx: str) -> str:
        """Send a plain text message via JSON."""
        try:
            resp = await self._api_request(
                "POST", "/api/message_async",
                json_data={"text": text, "context": ctx},
            )
            resp.raise_for_status()
            data = resp.json()
            if "context" in data:
                self.context_id = data["context"]
                ctx = self.context_id

            return await self._poll_response(ctx)
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            raise

    async def _send_with_attachment(
        self,
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
            headers = self._get_headers()

            resp = await self._api_request(
                "POST", "/api/message_async",
                files=files, headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if "context" in data:
                self.context_id = data["context"]
                ctx = self.context_id

            return await self._poll_response(ctx)
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Send with attachment failed: {e}")
            raise

    async def _poll_response(
        self,
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
                resp = await self._api_request(
                    "POST", "/api/poll",
                    json_data={"context": ctx, "log_from": log_from},
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

            except AuthenticationError:
                raise
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                await asyncio.sleep(poll_interval)

        return last_response or "[Timeout: No response received]"

    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file using Agent Zero's transcribe endpoint."""
        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            headers = self._get_headers()
            resp = await self._api_request(
                "POST", "/api/transcribe",
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
                headers=headers,
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


class AuthenticationError(Exception):
    """Raised when API requests fail due to authentication issues."""
    pass
