# -*- coding: utf-8 -*-
"""
Simple HTTP healthcheck endpoint for monitoring.
Returns bot status, uptime, and last alert timestamp.
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional
from aiohttp import web
from loguru import logger


class HealthcheckServer:
    """Simple HTTP server for healthcheck endpoint."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        # Bot status tracking
        self.start_time = datetime.now(timezone.utc)
        self.last_alert_time: Optional[datetime] = None
        self.ws_connected = False
        self.alerts_sent = 0

        # Setup routes
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/status', self.status_handler)
        self.app.router.add_get('/', self.index_handler)

    async def health_handler(self, request: web.Request) -> web.Response:
        """
        Simple health check endpoint.
        Returns 200 OK if bot is running.
        """
        return web.json_response({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def status_handler(self, request: web.Request) -> web.Response:
        """
        Detailed status endpoint with bot metrics.
        """
        now = datetime.now(timezone.utc)
        uptime_seconds = (now - self.start_time).total_seconds()

        # Format uptime
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{days}d {hours}h {minutes}m"

        # Last alert time
        last_alert_str = None
        if self.last_alert_time:
            seconds_ago = (now - self.last_alert_time).total_seconds()
            if seconds_ago < 60:
                last_alert_str = f"{int(seconds_ago)}s ago"
            elif seconds_ago < 3600:
                last_alert_str = f"{int(seconds_ago / 60)}m ago"
            else:
                last_alert_str = f"{int(seconds_ago / 3600)}h ago"

        return web.json_response({
            "status": "running",
            "uptime": uptime_str,
            "uptime_seconds": int(uptime_seconds),
            "start_time": self.start_time.isoformat(),
            "ws_connected": self.ws_connected,
            "alerts_sent": self.alerts_sent,
            "last_alert": last_alert_str,
            "timestamp": now.isoformat()
        })

    async def index_handler(self, request: web.Request) -> web.Response:
        """Simple index page with links."""
        html = """
        <html>
        <head><title>SmartMoney Bot Healthcheck</title></head>
        <body>
            <h1>SmartMoney Bot Healthcheck</h1>
            <p>Endpoints:</p>
            <ul>
                <li><a href="/health">/health</a> - Simple health check (200 OK)</li>
                <li><a href="/status">/status</a> - Detailed bot status</li>
            </ul>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    def update_alert_sent(self):
        """Record that an alert was sent."""
        self.last_alert_time = datetime.now(timezone.utc)
        self.alerts_sent += 1

    def set_ws_status(self, connected: bool):
        """Update WebSocket connection status."""
        self.ws_connected = connected

    async def start(self):
        """Start the healthcheck server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            logger.info(f"Healthcheck server started on http://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start healthcheck server: {e}")

    async def stop(self):
        """Stop the healthcheck server."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Healthcheck server stopped")

    async def run(self):
        """Run healthcheck server (keeps running until cancelled)."""
        await self.start()
        try:
            # Keep running until cancelled
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await self.stop()
            raise


# Global instance
_healthcheck_instance: Optional[HealthcheckServer] = None


def get_healthcheck() -> HealthcheckServer:
    """Get global healthcheck server instance (singleton)."""
    global _healthcheck_instance
    if _healthcheck_instance is None:
        _healthcheck_instance = HealthcheckServer()
    return _healthcheck_instance
