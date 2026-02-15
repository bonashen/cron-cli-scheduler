"""Scheduler core with cron-based task execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable

from croniter import croniter

from scheduler.config import DEFAULT_CHECK_INTERVAL
from scheduler.executor import TaskExecutor
from scheduler.models import Task, TaskRun, TaskStatus
from scheduler.storage import TaskStorage

logger = logging.getLogger(__name__)


class Scheduler:
    """Cron-based task scheduler."""
    
    def __init__(
        self,
        storage: TaskStorage,
        executor: TaskExecutor | None = None,
        on_task_run: Callable[[Task, TaskRun], None] | None = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
    ) -> None:
        self.storage = storage
        self.executor = executor or TaskExecutor()
        self.on_task_run = on_task_run
        self.check_interval = check_interval
        
        self._running = False
        self._paused = False
        self._tasks: dict[str, asyncio.Task] = {}
        self._started_at: datetime | None = None
        self._run_count = 0
        self._reboot_tasks_executed: set[str] = set()
    
    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        
        self._running = True
        self._started_at = datetime.now()
        
        logger.info("Scheduler started")
        
        # Execute @reboot tasks
        await self._execute_reboot_tasks()
        
        while self._running:
            if not self._paused:
                try:
                    await self._check_and_run_tasks()
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("Scheduler stopped")
    
    def pause(self) -> None:
        """Pause the scheduler (stop executing new tasks)."""
        self._paused = True
        logger.info("Scheduler paused")
    
    def resume(self) -> None:
        """Resume the scheduler."""
        self._paused = False
        logger.info("Scheduler resumed")
    
    async def _execute_reboot_tasks(self) -> None:
        """Execute @reboot tasks once."""
        tasks = self.storage.list_enabled()
        
        for task in tasks:
            if task.cron == "@reboot" and task.name not in self._reboot_tasks_executed:
                logger.info(f"Executing @reboot task: {task.name}")
                await self._run_task(task)
                self._reboot_tasks_executed.add(task.name)
    
    async def _check_and_run_tasks(self) -> None:
        """Check for tasks that need to run."""
        now = datetime.now()
        tasks = self.storage.list_enabled()
        
        for task in tasks:
            if task.cron == "@reboot":
                continue
            
            if self._should_run_task(task, now):
                logger.info(f"Task '{task.name}' scheduled to run")
                
                if task.name not in self._tasks or self._tasks[task.name].done():
                    self._tasks[task.name] = asyncio.create_task(
                        self._run_task(task)
                    )
    
    def _should_run_task(self, task: Task, now: datetime) -> bool:
        """Check if a task should run."""
        special = {
            "@yearly": "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *",
            "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *",
            "@midnight": "0 0 * * *",
            "@hourly": "0 * * * *",
        }
        
        schedule = special.get(task.cron, task.cron)
        
        try:
            base_time = task.last_run or datetime(1970, 1, 1)
            itr = croniter(schedule, base_time)
            next_run = itr.get_next(datetime)
            
            return now >= next_run
        except Exception as e:
            logger.error(f"Error parsing cron for task {task.name}: {e}")
            return False
    
    async def _run_task(self, task: Task) -> None:
        """Execute a single task."""
        run = TaskRun(started_at=datetime.now(), status=TaskStatus.RUNNING)
        
        try:
            result = await self.executor.execute(task, run)
            
            if result.success:
                logger.info(f"Task '{task.name}' completed successfully")
            else:
                logger.error(f"Task '{task.name}' failed: {result.stderr}")
            
        except Exception as e:
            run.status = TaskStatus.FAILED
            run.stderr = str(e)
            run.finished_at = datetime.now()
            logger.error(f"Task '{task.name}' execution error: {e}")
        
        task.add_run(run)
        self.storage.save(task)
        
        if self.on_task_run:
            try:
                self.on_task_run(task, run)
            except Exception as e:
                logger.error(f"Error in task run callback: {e}")
        
        self._run_count += 1
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "paused": self._paused,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                (datetime.now() - self._started_at).total_seconds()
                if self._started_at else 0
            ),
            "run_count": self._run_count,
            "check_interval": self.check_interval,
        }
    
    async def run_task_now(self, name: str) -> TaskRun | None:
        """Manually trigger a task to run immediately."""
        task = self.storage.load(name)
        if task is None:
            return None
        
        run = TaskRun(started_at=datetime.now(), status=TaskStatus.RUNNING)
        
        try:
            await self.executor.execute(task, run)
            
            task.add_run(run)
            self.storage.save(task)
            
        except Exception as e:
            run.status = TaskStatus.FAILED
            run.stderr = str(e)
            run.finished_at = datetime.now()
        
        return run
