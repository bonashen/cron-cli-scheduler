"""File storage operations using python-frontmatter."""

from __future__ import annotations

import frontmatter
from pathlib import Path
from typing import Any

from scheduler.config import TASKS_DIR, DATA_DIR
from scheduler.models import Task, TaskRun, TaskStatus


class TaskStorage:
    """Manages task storage in Markdown files with YAML Front Matter."""
    
    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            data_dir = DATA_DIR
        
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.tasks_dir = self.data_dir / "tasks"
        
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_task_path(self, name: str) -> Path:
        """Get file path for a task by name."""
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        return self.tasks_dir / f"{safe_name}.md"
    
    def save(self, task: Task) -> None:
        """Save a task to storage."""
        task_path = self._get_task_path(task.name)
        post = task.to_frontmatter()
        task_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    
    def load(self, name: str) -> Task | None:
        """Load a task from storage by name."""
        task_path = self._get_task_path(name)
        
        if not task_path.exists():
            return None
        
        try:
            post = frontmatter.load(task_path)
            return Task.from_frontmatter(post)
        except Exception:
            return None
    
    def delete(self, name: str) -> bool:
        """Delete a task from storage."""
        task_path = self._get_task_path(name)
        
        if not task_path.exists():
            return False
        
        task_path.unlink()
        return True
    
    def list_all(self) -> list[Task]:
        """List all tasks in storage."""
        tasks = []
        
        for task_file in self.tasks_dir.glob("*.md"):
            try:
                post = frontmatter.load(task_file)
                task = Task.from_frontmatter(post)
                tasks.append(task)
            except Exception:
                continue
        
        tasks.sort(key=lambda t: t.created_at)
        return tasks
    
    def list_enabled(self) -> list[Task]:
        """List all enabled tasks."""
        return [t for t in self.list_all() if t.enabled]
    
    def find_by_name(self, name: str) -> Task | None:
        """Find a task by exact name."""
        return self.load(name)
    
    def find_by_tag(self, tag: str) -> list[Task]:
        """Find tasks by tag."""
        return [t for t in self.list_all() if tag in t.tags]
    
    def find_by_owner(self, owner: str) -> list[Task]:
        """Find tasks by owner."""
        return [t for t in self.list_all() if t.owner == owner]
    
    def exists(self, name: str) -> bool:
        """Check if a task exists."""
        return self._get_task_path(name).exists()
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        tasks = self.list_all()
        enabled = sum(1 for t in tasks if t.enabled)
        
        return {
            "total_tasks": len(tasks),
            "enabled_tasks": enabled,
            "disabled_tasks": len(tasks) - enabled,
            "total_runs": sum(t.run_count for t in tasks),
            "total_failures": sum(t.fail_count for t in tasks),
            "data_dir": str(self.data_dir),
        }
