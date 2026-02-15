"""Daemon entry point for the scheduler."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from scheduler.config import PID_FILE, LOG_FILE, DEFAULT_MCP_HOST, DEFAULT_MCP_PORT
from scheduler.core import Scheduler
from scheduler.executor import TaskExecutor
from scheduler.storage import TaskStorage


def setup_logging() -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
        ],
    )


def write_pid() -> None:
    """Write PID to file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def remove_pid() -> None:
    """Remove PID file."""
    PID_FILE.unlink(missing_ok=True)


class SchedulerDaemon:
    """Scheduler daemon with optional MCP server."""
    
    def __init__(
        self,
        enable_mcp: bool = False,
        mcp_host: str = DEFAULT_MCP_HOST,
        mcp_port: int = DEFAULT_MCP_PORT,
    ) -> None:
        self.enable_mcp = enable_mcp
        self.mcp_host = mcp_host
        self.mcp_port = mcp_port
        
        self.storage = TaskStorage()
        self.scheduler = Scheduler(self.storage)
        self.mcp_server = None
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Start the daemon."""
        setup_logging()
        write_pid()
        
        logger = logging.getLogger(__name__)
        logger.info("Starting scheduler daemon...")
        
        # Setup signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: asyncio.create_task(self.shutdown())
            )
        
        tasks = [asyncio.create_task(self.scheduler.start())]
        
        # Start MCP server if enabled
        if self.enable_mcp:
            logger.info(f"Starting MCP server on {self.mcp_host}:{self.mcp_port}")
            from scheduler.mcp_server import create_mcp_app
            import uvicorn
            
            config = uvicorn.Config(
                create_mcp_app(self.storage, self.scheduler),
                host=self.mcp_host,
                port=self.mcp_port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            tasks.append(asyncio.create_task(server.serve()))
        
        logger.info("Scheduler daemon started")
        
        # Wait for shutdown
        await self._shutdown_event.wait()
    
    async def shutdown(self) -> None:
        """Shutdown the daemon."""
        logger = logging.getLogger(__name__)
        logger.info("Shutting down scheduler daemon...")
        
        self.scheduler.stop()
        remove_pid()
        
        self._shutdown_event.set()


def main() -> None:
    """Entry point for daemon."""
    parser = argparse.ArgumentParser(description="Cron Scheduler Daemon")
    parser.add_argument("--mcp", action="store_true", help="Enable MCP server")
    parser.add_argument("--mcp-host", default=DEFAULT_MCP_HOST, help="MCP server host")
    parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT, help="MCP server port")
    
    args = parser.parse_args()
    
    daemon = SchedulerDaemon(
        enable_mcp=args.mcp,
        mcp_host=args.mcp_host,
        mcp_port=args.mcp_port,
    )
    
    asyncio.run(daemon.start())


if __name__ == "__main__":
    main()
