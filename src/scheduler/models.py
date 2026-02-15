"""Task data models for the scheduler."""

from __future__ import annotations

import base64
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import frontmatter
from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DISABLED = "disabled"


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=1, ge=1, le=10)
    delay: int = Field(default=0, ge=0)
    
    def to_dict(self) -> dict[str, int]:
        return {"max_attempts": self.max_attempts, "delay": self.delay}
    
    @classmethod
    def from_dict(cls, data: dict[str, int]) -> RetryPolicy:
        return cls(max_attempts=data.get("max_attempts", 1), delay=data.get("delay", 0))


class NotifyConfig(BaseModel):
    enabled: bool = False
    on_success: bool = False
    on_failure: bool = True
    channels: list[str] = Field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "on_success": self.on_success,
            "on_failure": self.on_failure,
            "channels": self.channels,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotifyConfig:
        return cls(
            enabled=data.get("enabled", False),
            on_success=data.get("on_success", False),
            on_failure=data.get("on_failure", True),
            channels=data.get("channels", []),
        )


class TaskRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: datetime
    finished_at: datetime | None = None
    status: TaskStatus = TaskStatus.PENDING
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int | None = None
    attempt: int = 1
    
    @field_validator("stdout", "stderr")
    @classmethod
    def truncate_output(cls, v: str) -> str:
        max_len = 10000
        if len(v) > max_len:
            return v[:max_len] + f"\n... ({len(v) - max_len} chars truncated)"
        return v


class Task(BaseModel):
    name: str
    cron: str
    command: str
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    timeout: int = Field(default=0, ge=0)
    working_dir: Path | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    priority: int = Field(default=5, ge=1, le=10)
    owner: str = ""
    
    last_run: datetime | None = None
    last_status: TaskStatus | None = None
    run_count: int = 0
    fail_count: int = 0
    runs: list[TaskRun] = Field(default_factory=list, exclude=True)
    max_history: int = 50
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task name cannot be empty")
        if re.search(r'[<>:"/\\|?*]', v):
            raise ValueError("Task name contains invalid characters")
        return v.strip()
    
    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        from croniter import croniter
        
        special = {
            "@yearly": "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *",
            "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *",
            "@midnight": "0 0 * * *",
            "@hourly": "0 * * * *",
            "@reboot": "@reboot",
        }
        
        schedule = special.get(v, v)
        
        if schedule != "@reboot":
            if not croniter.is_valid(schedule):
                raise ValueError(f"Invalid cron expression: {v}")
        
        return v
    
    @field_validator("working_dir")
    @classmethod
    def validate_working_dir(cls, v: Path | None) -> Path | None:
        if v is not None:
            return Path(v).expanduser().resolve()
        return v
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: dict[str, str]) -> dict[str, str]:
        normalized = {}
        for key, value in v.items():
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                raise ValueError(f"Invalid environment variable name: {key}")
            normalized[key] = value
        return normalized
    
    def get_environment_decoded(self) -> dict[str, str]:
        decoded = {}
        for key, value in self.environment.items():
            if value.startswith("base64:"):
                try:
                    b64_data = value[7:]
                    decoded[key] = base64.b64decode(b64_data).decode("utf-8")
                except Exception:
                    decoded[key] = value
            else:
                decoded[key] = value
        return decoded
    
    def add_environment_encoded(self, key: str, value: str, encode: bool = False) -> None:
        if encode:
            b64_data = base64.b64encode(value.encode("utf-8")).decode("utf-8")
            self.environment[key] = f"base64:{b64_data}"
        else:
            self.environment[key] = value
        self.updated_at = datetime.now()
    
    def add_run(self, run: TaskRun) -> None:
        self.runs.append(run)
        
        if len(self.runs) > self.max_history:
            self.runs = self.runs[-self.max_history:]
        
        self.last_run = run.finished_at or run.started_at
        self.last_status = run.status
        self.run_count += 1
        
        if run.status == TaskStatus.FAILED:
            self.fail_count += 1
        
        self.updated_at = datetime.now()
    
    def get_next_run(self, base_time: datetime | None = None) -> datetime | None:
        from croniter import croniter
        
        if not self.enabled:
            return None
        
        if self.cron == "@reboot":
            return None
        
        special = {
            "@yearly": "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *",
            "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *",
            "@midnight": "0 0 * * *",
            "@hourly": "0 * * * *",
        }
        
        schedule = special.get(self.cron, self.cron)
        
        try:
            itr = croniter(schedule, base_time or datetime.now())
            return itr.get_next(datetime)
        except Exception:
            return None
    
    def to_frontmatter(self) -> frontmatter.Post:
        metadata = {
            "name": self.name,
            "cron": self.cron,
            "command": self.command,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
        if self.description:
            metadata["description"] = self.description
        
        if self.tags:
            metadata["tags"] = self.tags
        
        if self.timeout > 0:
            metadata["timeout"] = self.timeout
        
        if self.working_dir:
            metadata["working_dir"] = str(self.working_dir)
        
        if self.environment:
            metadata["environment"] = self.environment
        
        retry_dict = self.retry.to_dict()
        if retry_dict["max_attempts"] > 1 or retry_dict["delay"] > 0:
            metadata["retry"] = retry_dict
        
        notify_dict = self.notify.to_dict()
        if notify_dict["enabled"]:
            metadata["notify"] = notify_dict
        
        if self.priority != 5:
            metadata["priority"] = self.priority
        
        if self.owner:
            metadata["owner"] = self.owner
        
        if self.last_run:
            metadata["last_run"] = self.last_run.isoformat()
        
        if self.last_status:
            metadata["last_status"] = self.last_status.value
        
        if self.run_count > 0:
            metadata["run_count"] = self.run_count
            metadata["fail_count"] = self.fail_count
        
        content = self._generate_markdown_content()
        
        return frontmatter.Post(content, **metadata)
    
    def _generate_markdown_content(self) -> str:
        lines = [f"# {self.name}", ""]
        
        if self.description:
            lines.append(self.description)
            lines.append("")
        
        lines.append("## Execution History")
        lines.append("")
        
        if self.runs:
            lines.append("| 执行时间 | 退出码 | 输出 |")
            lines.append("|----------|--------|------|")
            
            for run in reversed(self.runs[-self.max_history:]):
                executed_at = run.started_at.strftime("%Y-%m-%d %H:%M:%S")
                exit_code = str(run.exit_code) if run.exit_code is not None else "-"
                
                output = (run.stdout or "")[:100].replace("|", "\\|").replace("\n", " ")
                if len(run.stdout or "") > 100:
                    output += "..."
                
                lines.append(f"| {executed_at} | {exit_code} | {output} |")
        else:
            lines.append("*No execution history yet*")
        
        lines.append("")
        
        return "\n".join(lines)
    
    @classmethod
    def from_frontmatter(cls, post: frontmatter.Post) -> Task:
        metadata = post.metadata
        
        data: dict[str, Any] = {
            "name": metadata.get("name"),
            "cron": metadata.get("cron"),
            "command": metadata.get("command"),
            "enabled": metadata.get("enabled", True),
            "created_at": datetime.fromisoformat(metadata["created_at"]) if "created_at" in metadata else datetime.now(),
            "updated_at": datetime.fromisoformat(metadata["updated_at"]) if "updated_at" in metadata else datetime.now(),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "timeout": metadata.get("timeout", 0),
            "priority": metadata.get("priority", 5),
            "owner": metadata.get("owner", ""),
        }
        
        if "working_dir" in metadata:
            data["working_dir"] = Path(metadata["working_dir"])
        
        if "environment" in metadata:
            data["environment"] = metadata["environment"]
        
        if "retry" in metadata:
            data["retry"] = RetryPolicy.from_dict(metadata["retry"])
        else:
            data["retry"] = RetryPolicy()
        
        if "notify" in metadata:
            data["notify"] = NotifyConfig.from_dict(metadata["notify"])
        else:
            data["notify"] = NotifyConfig()
        
        if "last_run" in metadata:
            data["last_run"] = datetime.fromisoformat(metadata["last_run"])
        
        if "last_status" in metadata:
            data["last_status"] = TaskStatus(metadata["last_status"])
        
        data["run_count"] = metadata.get("run_count", 0)
        data["fail_count"] = metadata.get("fail_count", 0)
        
        runs = cls._parse_execution_history(post.content)
        data["runs"] = runs
        
        return cls(**data)
    
    @classmethod
    def _parse_execution_history(cls, content: str) -> list[TaskRun]:
        import re
        
        runs = []
        
        table_match = re.search(
            r'\|\s*执行时间\s*\|\s*退出码\s*\|\s*输出\s*\|\s*\n'
            r'\|[-\|]+\|\s*\n(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL
        )
        
        if table_match:
            for line in table_match.group(1).strip().split('\n'):
                if line.startswith('|') and not line.strip().startswith('|---'):
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) >= 3:
                        try:
                            run = TaskRun(
                                started_at=datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S"),
                                exit_code=int(parts[1]) if parts[1] != '-' else None,
                                stdout=parts[2].replace("\\|", "|"),
                                status=TaskStatus.SUCCESS if parts[1] == '0' else TaskStatus.FAILED,
                            )
                            runs.append(run)
                        except (ValueError, IndexError):
                            continue
        
        return runs
    
    def to_dict(self) -> dict[str, Any]:
        next_run = self.get_next_run()
        
        return {
            "name": self.name,
            "cron": self.cron,
            "command": self.command,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "description": self.description,
            "tags": self.tags,
            "timeout": self.timeout,
            "working_dir": str(self.working_dir) if self.working_dir else None,
            "environment": self.environment,
            "retry": self.retry.to_dict(),
            "notify": self.notify.to_dict(),
            "priority": self.priority,
            "owner": self.owner,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_status": self.last_status.value if self.last_status else None,
            "run_count": self.run_count,
            "fail_count": self.fail_count,
            "next_run": next_run.isoformat() if next_run else None,
        }
