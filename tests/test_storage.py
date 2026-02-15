"""Tests for scheduler storage."""

import pytest
from pathlib import Path

from scheduler.models import Task, RetryPolicy
from scheduler.storage import TaskStorage


class TestTaskStorage:
    def test_storage_initialization(self, tmp_path):
        storage = TaskStorage(tmp_path)
        assert storage.tasks_dir.exists()
    
    def test_save_and_load(self, tmp_path):
        storage = TaskStorage(tmp_path)
        
        task = Task(
            name="test-task",
            cron="0 2 * * *",
            command="echo hello",
        )
        
        storage.save(task)
        loaded = storage.load("test-task")
        
        assert loaded is not None
        assert loaded.name == "test-task"
        assert loaded.cron == "0 2 * * *"
    
    def test_delete(self, tmp_path):
        storage = TaskStorage(tmp_path)
        
        task = Task(name="test", cron="* * * * *", command="cmd")
        storage.save(task)
        assert storage.exists("test")
        
        storage.delete("test")
        assert not storage.exists("test")
    
    def test_list_all(self, tmp_path):
        storage = TaskStorage(tmp_path)
        
        for i in range(3):
            task = Task(name=f"task{i}", cron="* * * * *", command="cmd")
            storage.save(task)
        
        tasks = storage.list_all()
        assert len(tasks) == 3
    
    def test_find_by_tag(self, tmp_path):
        storage = TaskStorage(tmp_path)
        
        task1 = Task(name="task1", cron="* * * * *", command="cmd", tags=["backup"])
        task2 = Task(name="task2", cron="* * * * *", command="cmd", tags=["cleanup"])
        
        storage.save(task1)
        storage.save(task2)
        
        results = storage.find_by_tag("backup")
        assert len(results) == 1
        assert results[0].name == "task1"
