"""Basic usage example."""

from scheduler import TaskStorage, Task, Scheduler
from scheduler.models import RetryPolicy


def main():
    storage = TaskStorage()
    
    # Create a task
    task = Task(
        name="daily-backup",
        cron="0 2 * * *",
        command="/usr/bin/backup.sh",
        description="Daily database backup",
        tags=["backup", "database"],
        retry=RetryPolicy(max_attempts=3, delay=300),
        priority=9,
    )
    
    storage.save(task)
    print(f"Created task: {task.name}")
    
    # List all tasks
    tasks = storage.list_all()
    print(f"\nTotal tasks: {len(tasks)}")
    for t in tasks:
        print(f"  - {t.name}: {t.cron}")


if __name__ == "__main__":
    main()
