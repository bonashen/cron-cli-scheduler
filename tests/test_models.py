"""Tests for scheduler models."""

import pytest
from datetime import datetime
from pathlib import Path

from scheduler.models import Task, TaskRun, TaskStatus, RetryPolicy, NotifyConfig


class TestTask:
    def test_task_creation(self):
        task = Task(
            name="test-task",
            cron="0 2 * * *",
            command="echo hello",
        )
        
        assert task.name == "test-task"
        assert task.cron == "0 2 * * *"
        assert task.command == "echo hello"
        assert task.enabled is True
        assert task.priority == 5
        assert task.timeout == 0
    
    def test_task_validation(self):
        Task(name="test", cron="0 2 * * *", command="cmd")
        Task(name="test", cron="@daily", command="cmd")
        
        with pytest.raises(ValueError):
            Task(name="test", cron="invalid", command="cmd")
        
        with pytest.raises(ValueError):
            Task(name="", cron="* * * * *", command="cmd")
    
    def test_environment_encoding(self):
        task = Task(
            name="test",
            cron="* * * * *",
            command="cmd",
        )
        
        task.add_environment_encoded("SECRET", "my-secret", encode=True)
        assert task.environment["SECRET"].startswith("base64:")
        
        decoded = task.get_environment_decoded()
        assert decoded["SECRET"] == "my-secret"
    
    def test_frontmatter_roundtrip(self):
        task = Task(
            name="test-task",
            cron="0 2 * * *",
            command="python script.py",
            description="Test task",
            working_dir=Path("/home/user"),
            environment={"VAR1": "value1"},
            tags=["test"],
            timeout=300,
            retry=RetryPolicy(max_attempts=3, delay=10),
            priority=8,
            owner="admin",
        )
        
        post = task.to_frontmatter()
        task2 = Task.from_frontmatter(post)
        
        assert task2.name == task.name
        assert task2.cron == task.cron
        assert task2.command == task.command
        assert task2.priority == 8
        assert task2.owner == "admin"


class TestRetryPolicy:
    def test_default_values(self):
        retry = RetryPolicy()
        assert retry.max_attempts == 1
        assert retry.delay == 0
    
    def test_custom_values(self):
        retry = RetryPolicy(max_attempts=5, delay=30)
        assert retry.max_attempts == 5
        assert retry.delay == 30


class TestNotifyConfig:
    def test_default_values(self):
        notify = NotifyConfig()
        assert notify.enabled is False
        assert notify.on_failure is True
