"""Task executor with subprocess management."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
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
    timeout: int = 0,
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
            timeout=timeout if timeout > 0 else None,
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
        timeout = task.timeout if task.timeout > 0 else None
        
        max_attempts = task.retry.max_attempts if task.retry else 1
        delay = task.retry.delay if task.retry else 0
        
        last_result = ExecutionResult(success=False, exit_code=-1, stdout="", stderr="")
        
        for attempt in range(1, max_attempts + 1):
            run.attempt = attempt
            
            loop = asyncio.get_event_loop()
            last_result = await loop.run_in_executor(
                None,
                execute_command,
                task.command,
                workdir,
                env,
                timeout,
            )
            
            if last_result.success:
                run.status = TaskStatus.SUCCESS
                run.exit_code = last_result.exit_code
                run.stdout = last_result.stdout
                run.stderr = last_result.stderr
                run.finished_at = datetime.now()
                return last_result
            
            if attempt < max_attempts and delay > 0:
                await asyncio.sleep(delay)
        
        run.status = TaskStatus.FAILED
        run.exit_code = last_result.exit_code
        run.stdout = last_result.stdout
        run.stderr = last_result.stderr
        run.finished_at = datetime.now()
        
        return last_result
