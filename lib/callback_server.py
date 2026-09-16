"""
FastAPI callback server for SignalHire Person API webhooks.

This server receives callbacks from SignalHire's Person API and processes
the revealed contact information. It supports multiple callback handlers
and provides a simple interface for starting/stopping the server.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from models.person_callback import PersonCallbackData, PersonCallbackItem

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class CallbackServer:
    """FastAPI-based callback server for SignalHire Person API."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.app: FastAPI | None = None
        self.server_thread: threading.Thread | None = None
        self.is_running = False
        self._callback_handlers: dict[str, Callable[[PersonCallbackData], None]] = {}
        self._request_handlers: dict[str, Callable[[str, PersonCallbackData], None]] = (
            {}
        )

    def create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            logger.info("Starting SignalHire callback server")
            yield
            logger.info("Shutting down SignalHire callback server")

        app = FastAPI(
            title="SignalHire Callback Server",
            description="Receives webhooks from SignalHire Person API",
            version="1.0.0",
            lifespan=lifespan,
        )

        @app.post("/signalhire/callback")
        async def handle_callback(
            request: Request, background_tasks: BackgroundTasks
        ) -> JSONResponse:
            """Handle SignalHire Person API callback."""
            try:
                # Extract request ID from headers
                request_id = request.headers.get("Request-Id")
                if not request_id:
                    logger.warning("Callback received without Request-Id header")
                    raise HTTPException(
                        status_code=400, detail="Missing Request-Id header"
                    )

                # Parse callback data
                raw_data = await request.json()
                callback_data = [
                    PersonCallbackItem.model_validate(item) for item in raw_data
                ]

                logger.info(
                    f"Received callback for request {request_id} with {len(callback_data)} items"
                )

                # Process callback in background
                background_tasks.add_task(
                    self._process_callback, request_id, callback_data
                )

                return JSONResponse(
                    status_code=200,
                    content={"status": "accepted", "request_id": request_id},
                )

            except HTTPException:
                raise  # Let FastAPI handle HTTP exceptions directly
            except ValidationError as e:
                logger.error(f"Invalid callback data: {e}")
                raise HTTPException(
                    status_code=422, detail=f"Invalid callback data: {e}"
                ) from e
            except Exception as e:
                logger.error(f"Error processing callback: {e}")
                raise HTTPException(
                    status_code=500, detail="Internal server error"
                ) from e

        @app.get("/health")
        async def health_check() -> dict[str, str]:
            """Health check endpoint."""
            return {"status": "healthy", "service": "signalhire-callback"}

        @app.get("/")
        async def root() -> dict[str, Any]:
            """Root endpoint with basic info."""
            return {
                "service": "SignalHire Callback Server",
                "version": "1.0.0",
                "callback_endpoint": "/signalhire/callback",
                "health_endpoint": "/health",
            }

        self.app = app
        return app

    async def _process_callback(
        self, request_id: str, callback_data: PersonCallbackData
    ) -> None:
        """Process callback data using registered handlers."""
        try:
            # Call request-specific handlers first
            if request_id in self._request_handlers:
                handler = self._request_handlers[request_id]
                await asyncio.create_task(
                    asyncio.to_thread(handler, request_id, callback_data)
                )
                # Remove one-time handler
                del self._request_handlers[request_id]

            # Call global handlers
            for handler_name, handler in self._callback_handlers.items():
                try:
                    await asyncio.create_task(asyncio.to_thread(handler, callback_data))
                    logger.debug(
                        f"Handler {handler_name} processed callback successfully"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Handler {handler_name} failed: {e}")

            # Log callback statistics
            success_count = sum(1 for item in callback_data if item.status == "success")
            failed_count = len(callback_data) - success_count
            logger.info(
                f"Callback {request_id}: {success_count} successful, {failed_count} failed"
            )

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error in callback processing for {request_id}: {e}")

    def register_handler(
        self, name: str, handler: Callable[[PersonCallbackData], None]
    ) -> None:
        """Register a global callback handler."""
        self._callback_handlers[name] = handler
        logger.info(f"Registered global callback handler: {name}")

    def register_request_handler(
        self, request_id: str, handler: Callable[[str, PersonCallbackData], None]
    ) -> None:
        """Register a one-time handler for a specific request ID."""
        self._request_handlers[request_id] = handler
        logger.info(f"Registered request handler for: {request_id}")

    def unregister_handler(self, name: str) -> bool:
        """Unregister a global callback handler."""
        if name in self._callback_handlers:
            del self._callback_handlers[name]
            logger.info(f"Unregistered callback handler: {name}")
            return True
        return False

    def start(self, background: bool = True) -> None:
        """Start the callback server."""
        if self.is_running:
            logger.warning("Server is already running")
            return

        if not self.app:
            self.create_app()

        if background:
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
        else:
            self._run_server()

        self.is_running = True
        logger.info(f"Callback server started on {self.host}:{self.port}")

    def _run_server(self) -> None:
        """Run the FastAPI server with uvicorn."""
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Server error: {e}")
            self.is_running = False

    def stop(self) -> None:
        """Stop the callback server."""
        if not self.is_running:
            logger.warning("Server is not running")
            return

        # Note: uvicorn doesn't provide clean shutdown in thread mode
        # For production, consider using asyncio-based startup
        logger.warning(
            "Server stop requested - restart application to fully stop server"
        )
        self.is_running = False

    def get_callback_url(self, external_host: str | None = None) -> str:
        """Get the callback URL for SignalHire API requests."""
        host = external_host or self.host
        if host == "0.0.0.0":
            host = "localhost"
        return f"http://{host}:{self.port}/signalhire/callback"

    @property
    def status(self) -> dict[str, Any]:
        """Get server status information."""
        return {
            "running": self.is_running,
            "host": self.host,
            "port": self.port,
            "callback_url": self.get_callback_url(),
            "handlers": list(self._callback_handlers.keys()),
            "pending_requests": list(self._request_handlers.keys()),
        }


# Default server instance
_default_server: CallbackServer | None = None


def get_server(host: str = "0.0.0.0", port: int = 8000) -> CallbackServer:
    """Get or create the default callback server instance."""
    global _default_server
    if _default_server is None:
        _default_server = CallbackServer(host=host, port=port)
    return _default_server


def start_server(
    host: str = "0.0.0.0", port: int = 8000, background: bool = True
) -> CallbackServer:
    """Start the default callback server."""
    server = get_server(host, port)
    if not server.is_running:
        server.start(background=background)
    return server


def stop_server() -> None:
    """Stop the default callback server."""
    global _default_server
    if _default_server:
        _default_server.stop()


# Example usage handlers
def log_callback_handler(callback_data: PersonCallbackData) -> None:
    """Example handler that logs callback data."""
    for item in callback_data:
        if item.status == "success" and item.candidate:
            logger.info(f"Received contact for {item.candidate.fullName}")
        else:
            logger.warning(f"Failed to process item {item.item}: {item.status}")


def save_to_csv_handler(callback_data: PersonCallbackData) -> None:
    """Example handler that could save data to CSV."""
    # This would integrate with csv_exporter service
    successful_items = [
        item for item in callback_data if item.status == "success" and item.candidate
    ]
    logger.info(f"Would save {len(successful_items)} contacts to CSV")


if __name__ == "__main__":
    # Example usage
    server = CallbackServer(port=8001)
    server.register_handler("logger", log_callback_handler)
    server.register_handler("csv_saver", save_to_csv_handler)

    print(f"Starting callback server at {server.get_callback_url()}")
    server.start(background=False)
