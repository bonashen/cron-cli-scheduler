"""Task executor with subprocess management."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scheduler.models import Task, TaskRun, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int | None
    stdout: str
    stderr: str


def execute_command(
    command: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> ExecutionResult:
    """Execute a shell command with optional working directory and environment."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout if timeout else None,
        )
        
        return ExecutionResult(
            success=result.returncode == 0,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=str(e),
        )


class TaskExecutor:
    """Executes tasks with retry support."""
    
    def __init__(self) -> None:
        self._running: dict[str, TaskRun] = {}
    
    async def execute(self, task: Task, run: TaskRun) -> ExecutionResult:
        """Execute a task with retry support."""
        env = task.get_environment_decoded()
        workdir = task.working_dir
        timeout = task.timeout if task.timeout and task.timeout > 0 else None
        
        max_attempts = task.retry.max_attempts if task.retry else 1
        delay = task.retry.delay if task.retry else 0
        
        last_result = ExecutionResult(success=False, exit_code=-1, stdout="", stderr="")
        
        for attempt in range(1, max_attempts + 1):
            run.attempt = attempt
            
            loop = asyncio.get_event_loop()
            
            def run_with_timeout() -> ExecutionResult:
                return execute_command(task.command, workdir, env, timeout)
            
            last_result = await loop.run_in_executor(None, run_with_timeout)
            
            if last_result.success:
                run.status = TaskStatus.SUCCESS
                run.exit_code = last_result.exit_code
                run.stdout = last_result.stdout
                run.stderr = last_result.stderr
                run.finished_at = datetime.now()
                
                self._send_webhook(task, run)
                
                return last_result
            
            if attempt < max_attempts and delay > 0:
                await asyncio.sleep(delay)
        
        run.status = TaskStatus.FAILED
        run.exit_code = last_result.exit_code
        run.stdout = last_result.stdout
        run.stderr = last_result.stderr
        run.finished_at = datetime.now()
        
        self._send_webhook(task, run)
        
        return last_result
    
    def _send_webhook(self, task: Task, run: TaskRun) -> None:
        webhook = task.webhook
        if not webhook.is_enabled():
            return
        
        should_send = (run.status == TaskStatus.SUCCESS and webhook.on_success) or \
                      (run.status == TaskStatus.FAILED and webhook.on_failure)
        if not should_send:
            return
        
        payload = {
            "task": task.name,
            "status": run.status.value,
            "exit_code": run.exit_code,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "stdout": run.stdout,
            "stderr": run.stderr,
            "command": task.command,
            "cron": task.cron,
        }
        
        run.webhook_called = True
        run.webhook_url = webhook.url
        
        env = os.environ.copy()
        env["WEBHOOK_URL"] = webhook.url
        if webhook.token:
            env["WEBHOOK_TOKEN"] = webhook.token
        env["WEBHOOK_PAYLOAD"] = json.dumps(payload)
        
        try:
            subprocess.Popen(
                [sys.executable, "-m", "scheduler.webhook_runner"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            run.webhook_status = "triggered"
            logger.info(f"Webhook triggered for task {task.name}")
        except Exception as e:
            run.webhook_status = "failed"
            logger.warning(f"Failed to trigger webhook for task {task.name}: {e}")
