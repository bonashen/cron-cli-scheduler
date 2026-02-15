"""Configuration and constants for the scheduler."""

from pathlib import Path

DATA_DIR = Path.home() / ".cron-cli-scheduler"
TASKS_DIR = DATA_DIR / "tasks"
PID_FILE = DATA_DIR / "scheduler.pid"
LOG_FILE = DATA_DIR / "scheduler.log"

DEFAULT_MCP_HOST = "0.0.0.0"
DEFAULT_MCP_PORT = 8000
DEFAULT_CHECK_INTERVAL = 1
DEFAULT_MAX_HISTORY = 50
