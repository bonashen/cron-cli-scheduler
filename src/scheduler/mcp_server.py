"""MCP server using Starlette and SSE."""

from __future__ import annotations

import json
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, JSONResponse, StreamingResponse
from starlette.routing import Route

from scheduler.core import Scheduler
from scheduler.models import Task, TaskStatus, RetryPolicy, NotifyConfig
from scheduler.storage import TaskStorage


async def handle_sse(request: Request) -> StreamingResponse:
    """Handle SSE endpoint."""
    async def event_stream():
        # Send initial connection message
        yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def handle_messages(request: Request) -> JSONResponse:
    """Handle MCP message endpoint."""
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    
    storage: TaskStorage = request.app.state.storage
    scheduler: Scheduler = request.app.state.scheduler
    
    result = await handle_mcp_method(method, params, storage, scheduler)
    
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": body.get("id"),
        "result": result,
    })


async def handle_mcp_method(
    method: str,
    params: dict[str, Any],
    storage: TaskStorage,
    scheduler: Scheduler,
) -> Any:
    """Handle MCP method calls."""
    
    if method == "add_task":
        # Check for duplicate name
        if storage.exists(params["name"]):
            return {"success": False, "message": f"Task '{params['name']}' already exists"}
        
        from pathlib import Path
        
        task = Task(
            name=params["name"],
            cron=params["cron"],
            command=params["command"],
            description=params.get("description", ""),
            enabled=params.get("enabled", True),
            working_dir=Path(params["working_dir"]) if params.get("working_dir") else None,
            environment=params.get("environment", {}),
            tags=params.get("tags", []),
            timeout=params.get("timeout", 0),
            retry=RetryPolicy(**params["retry"]) if params.get("retry") else RetryPolicy(),
            notify=NotifyConfig(**params["notify"]) if params.get("notify") else NotifyConfig(),
            priority=params.get("priority", 5),
            owner=params.get("owner", ""),
        )
        
        storage.save(task)
        return {"success": True, "message": f"Task '{task.name}' created"}
    
    elif method == "list_tasks":
        tasks = storage.list_all()
        return [t.to_dict() for t in tasks]
    
    elif method == "get_task":
        name = params.get("name")
        task = storage.load(name)
        if task is None:
            return None
        return task.to_dict()
    
    elif method == "remove_task":
        name = params.get("name")
        if storage.delete(name):
            return True
        return False
    
    elif method == "get_task_history":
        task_name = params.get("task_name")
        
        if task_name:
            task = storage.load(task_name)
            if task is None:
                return []
            tasks = [task]
        else:
            tasks = storage.list_all()
        
        history = []
        for task in tasks:
            for run in task.runs:
                history.append({
                    "task": task.name,
                    "executed_at": run.started_at.isoformat(),
                    "exit_code": run.exit_code,
                    "output": run.stdout + (f"\n{run.stderr}" if run.stderr else ""),
                })
        
        return history
    
    elif method == "pause_scheduler":
        scheduler.pause()
        return True
    
    elif method == "resume_scheduler":
        scheduler.resume()
        return True
    
    elif method == "get_status":
        stats = storage.get_stats()
        scheduler_status = scheduler.get_status()
        
        return {
            "running": scheduler_status["running"],
            "paused": scheduler_status["paused"],
            "tasks_count": stats["total_tasks"],
        }
    
    else:
        return {"error": f"Unknown method: {method}"}


async def handle_tools(request: Request) -> JSONResponse:
    """Return available tools."""
    tools = [
        {
            "name": "add_task",
            "description": "Add a new scheduled task",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "cron": {"type": "string"},
                    "command": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "timeout": {"type": "integer", "default": 0},
                    "working_dir": {"type": "string"},
                    "environment": {"type": "object"},
                    "retry": {"type": "object"},
                    "priority": {"type": "integer", "default": 5},
                    "owner": {"type": "string"},
                },
                "required": ["name", "cron", "command"],
            },
        },
        {
            "name": "list_tasks",
            "description": "List all tasks",
            "parameters": {},
        },
        {
            "name": "get_task",
            "description": "Get detailed information about a specific task",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        {
            "name": "remove_task",
            "description": "Remove a task by name",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        {
            "name": "get_task_history",
            "description": "Get execution history",
            "parameters": {
                "type": "object",
                "properties": {"task_name": {"type": "string"}},
            },
        },
        {
            "name": "pause_scheduler",
            "description": "Pause the scheduler",
            "parameters": {},
        },
        {
            "name": "resume_scheduler",
            "description": "Resume the scheduler",
            "parameters": {},
        },
        {
            "name": "get_status",
            "description": "Get scheduler status",
            "parameters": {},
        },
    ]
    
    return JSONResponse({"tools": tools})


def create_mcp_app(storage: TaskStorage, scheduler: Scheduler) -> Starlette:
    """Create MCP server application."""
    routes = [
        Route("/sse", handle_sse),
        Route("/messages", handle_messages, methods=["POST"]),
        Route("/tools", handle_tools),
    ]
    
    app = Starlette(routes=routes)
    app.state.storage = storage
    app.state.scheduler = scheduler
    
    return app
