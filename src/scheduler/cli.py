"""Command line interface for cron-cli."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import click
from colorama import init, Fore, Style
from croniter import croniter

from scheduler.config import DEFAULT_MCP_HOST, DEFAULT_MCP_PORT
from scheduler.models import Task, RetryPolicy, NotifyConfig, WebhookConfig
from scheduler.storage import TaskStorage
from scheduler.core import Scheduler
from scheduler.executor import TaskExecutor

init(autoreset=True)


def get_storage() -> TaskStorage:
    return TaskStorage()


@click.group()
@click.version_option(version="0.1.0", prog_name="cron-cli")
def cli() -> None:
    """Cross-platform cron-like scheduler with task management."""
    pass


@cli.command()
@click.option("--name", "-n", required=True, help="Task name (unique)")
@click.option("--cron", "-c", required=True, help="Cron expression")
@click.option("--command", "-cmd", required=True, help="Command to execute")
@click.option("--description", "-d", default="", help="Task description")
@click.option("--tags", default="", help="Comma-separated tags")
@click.option("--timeout", type=int, default=0, help="Timeout in seconds (0=no limit)")
@click.option("--working-dir", "-w", type=click.Path(), help="Working directory")
@click.option("--env", "-e", multiple=True, help="Environment variable (KEY=value)")
@click.option("--retry-max", type=int, default=1, help="Max retry attempts")
@click.option("--retry-delay", type=int, default=0, help="Retry delay in seconds")
@click.option("--priority", type=int, default=5, help="Priority 1-10 (default 5)")
@click.option("--owner", default="", help="Task owner")
@click.option("--webhook-url", default="", help="Webhook URL to call after execution")
@click.option("--webhook-token", default="", help="Authorization token for webhook (sent as Bearer token)")
@click.option("--webhook-on-success/--no-webhook-on-success", default=True, help="Call webhook on success")
@click.option("--webhook-on-failure/--no-webhook-on-failure", default=True, help="Call webhook on failure")
@click.option("--enabled/--disabled", default=True, help="Enable task immediately")
def add(
    name: str,
    cron: str,
    command: str,
    description: str,
    tags: str,
    timeout: int,
    working_dir: str | None,
    env: tuple[str, ...],
    retry_max: int,
    retry_delay: int,
    priority: int,
    owner: str,
    webhook_url: str,
    webhook_token: str,
    webhook_on_success: bool,
    webhook_on_failure: bool,
    enabled: bool,
) -> None:
    """Add a new scheduled task."""
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
    
    check_cron = special.get(cron, cron)
    if check_cron != "@reboot" and not croniter.is_valid(check_cron):
        click.echo(f"{Fore.RED}Error: Invalid cron expression: {cron}", err=True)
        sys.exit(1)
    
    storage = get_storage()
    
    # Check for duplicate name
    if storage.exists(name):
        click.echo(f"{Fore.RED}Error: Task with name '{name}' already exists", err=True)
        sys.exit(1)
    
    # Parse environment variables
    env_dict = {}
    for e in env:
        if "=" not in e:
            click.echo(f"{Fore.RED}Error: Invalid environment variable: {e}", err=True)
            sys.exit(1)
        key, value = e.split("=", 1)
        env_dict[key] = f"base64:{base64.b64encode(value.encode()).decode()}"
    
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    webhook = WebhookConfig(
        url=webhook_url,
        token=webhook_token,
        on_success=webhook_on_success,
        on_failure=webhook_on_failure,
    )
    
    try:
        task = Task(
            name=name,
            cron=cron,
            command=command,
            description=description,
            enabled=enabled,
            working_dir=Path(working_dir) if working_dir else None,
            environment=env_dict,
            tags=tag_list,
            timeout=timeout,
            retry=RetryPolicy(max_attempts=retry_max, delay=retry_delay),
            webhook=webhook,
            priority=priority,
            owner=owner,
        )
        
        storage.save(task)
        
        click.echo(f"{Fore.GREEN}✓ Task created: {name}")
    except ValueError as e:
        click.echo(f"{Fore.RED}Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--json", "-j", "output_json", is_flag=True, help="Output as JSON")
def list(output_json: bool) -> None:
    """List all tasks."""
    storage = get_storage()
    tasks = storage.list_all()
    
    if output_json:
        click.echo(json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False))
    else:
        if not tasks:
            click.echo("No tasks found.")
            return
        
        click.echo(f"{'Name':<25} {'Cron':<15} {'Status':<10} {'Next Run'}")
        click.echo("-" * 70)
        
        for task in tasks:
            status = f"{Fore.GREEN}enabled" if task.enabled else f"{Fore.RED}disabled"
            next_run = task.get_next_run()
            next_run_str = next_run.strftime("%m-%d %H:%M") if next_run else "N/A"
            cron_disp = task.cron if len(task.cron) <= 14 else task.cron[:11] + "..."
            click.echo(
                f"{task.name[:24]:<25} "
                f"{cron_disp:<15} "
                f"{status:<10} "
                f"{Style.RESET_ALL}{next_run_str}"
            )


@cli.command()
@click.argument("name")
def remove(name: str) -> None:
    """Remove a task."""
    storage = get_storage()
    
    if not storage.exists(name):
        click.echo(f"{Fore.RED}Error: Task not found: {name}", err=True)
        sys.exit(1)
    
    if storage.delete(name):
        click.echo(f"{Fore.GREEN}✓ Task deleted: {name}")
    else:
        click.echo(f"{Fore.RED}Error: Failed to delete task: {name}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("name")
@click.option("--json", "-j", "output_json", is_flag=True, help="Output as JSON")
def get(name: str, output_json: bool) -> None:
    """View task details."""
    storage = get_storage()
    
    task = storage.load(name)
    if task is None:
        click.echo(f"{Fore.RED}Error: Task not found: {name}", err=True)
        sys.exit(1)
    
    if output_json:
        click.echo(json.dumps(task.to_dict(), indent=2, ensure_ascii=False))
    else:
        # Display detailed task information
        click.echo(f"{Style.BRIGHT}Task: {task.name}{Style.RESET_ALL}")
        click.echo(f"{'─' * 50}")
        
        # Basic info
        click.echo(f"{Fore.CYAN}Basic{Style.RESET_ALL}")
        click.echo(f"  Cron:       {task.cron}")
        status = f"{Fore.GREEN}enabled" if task.enabled else f"{Fore.RED}disabled"
        click.echo(f"  Status:     {status}")
        click.echo(f"  Command:    {task.command}")
        
        if task.description:
            click.echo(f"  Description: {task.description}")
        
        # Schedule info
        next_run = task.get_next_run()
        if next_run:
            click.echo(f"\n{Fore.CYAN}Schedule{Style.RESET_ALL}")
            click.echo(f"  Next run:   {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Metadata
        click.echo(f"\n{Fore.CYAN}Metadata{Style.RESET_ALL}")
        if task.tags:
            click.echo(f"  Tags:       {', '.join(task.tags)}")
        click.echo(f"  Priority:   {task.priority}")
        if task.owner:
            click.echo(f"  Owner:      {task.owner}")
        
        # Execution settings
        click.echo(f"\n{Fore.CYAN}Execution{Style.RESET_ALL}")
        click.echo(f"  Timeout:    {task.timeout}s" if task.timeout > 0 else "  Timeout:    no limit")
        if task.retry:
            click.echo(f"  Retry:      {task.retry.max_attempts} attempts, {task.retry.delay}s delay")
        if task.working_dir:
            click.echo(f"  Working dir: {task.working_dir}")
        
        if task.webhook and task.webhook.url:
            click.echo(f"\n{Fore.CYAN}Webhook{Style.RESET_ALL}")
            click.echo(f"  URL:        {task.webhook.url}")
            if task.webhook.token:
                click.echo(f"  Token:      {task.webhook.token[:8]}..." if len(task.webhook.token) > 8 else f"  Token:      {task.webhook.token}")
            click.echo(f"  On success: {task.webhook.on_success}")
            click.echo(f"  On failure: {task.webhook.on_failure}")
        
        # Environment variables (show keys only, values are base64 encoded)
        if task.environment:
            click.echo(f"\n{Fore.CYAN}Environment{Style.RESET_ALL}")
            for key in task.environment:
                click.echo(f"  {key}")
        
        # Timestamps
        click.echo(f"\n{Fore.CYAN}Timestamps{Style.RESET_ALL}")
        click.echo(f"  Created:    {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if task.updated_at:
            click.echo(f"  Updated:    {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Recent runs
        if task.runs:
            click.echo(f"\n{Fore.CYAN}Recent Runs{Style.RESET_ALL}")
            click.echo(f"  {'Time':<20} {'Exit':<6} {'Webhook':<12} {'Output'}")
            click.echo(f"  {'─' * 60}")
            for run in task.runs[:5]:
                output = run.stdout[:20].replace('\n', ' ') + "..." if len(run.stdout) > 20 else run.stdout
                webhook_status = f"{run.webhook_status}" if run.webhook_called else "-"
                click.echo(f"  {run.started_at.strftime('%Y-%m-%d %H:%M:%S'):<20} {run.exit_code:<6} {webhook_status:<12} {output}")


@cli.command()
@click.option("--task", "-t", help="Task name to filter")
@click.option("--json", "-j", "output_json", is_flag=True, help="Output as JSON")
def logs(task: str | None, output_json: bool) -> None:
    """View execution history."""
    storage = get_storage()
    
    if task:
        t = storage.load(task)
        if t is None:
            click.echo(f"{Fore.RED}Error: Task not found: {task}", err=True)
            sys.exit(1)
        tasks = [t]
    else:
        tasks = storage.list_all()
    
    history = []
    for t in tasks:
        for run in t.runs:
            history.append({
                "task": t.name,
                "executed_at": run.started_at.isoformat(),
                "exit_code": run.exit_code,
                "output": run.stdout + (f"\n{run.stderr}" if run.stderr else ""),
            })
    
    if output_json:
        click.echo(json.dumps(history, indent=2, ensure_ascii=False))
    else:
        if not history:
            click.echo("No execution history.")
            return
        
        click.echo(f"{'Task':<25} {'Time':<20} {'Exit':<6} {'Output'}")
        click.echo("-" * 80)
        
        for item in history:
            output = item['output'][:40].replace('\n', ' ') + "..." if len(item['output']) > 40 else item['output']
            click.echo(
                f"{item['task'][:24]:<25} "
                f"{item['executed_at'][:19]:<20} "
                f"{item['exit_code']:<6} "
                f"{output}"
            )


@cli.command()
@click.option("--mcp", is_flag=True, help="Enable MCP server")
@click.option("--mcp-host", default=DEFAULT_MCP_HOST, help="MCP server host")
@click.option("--mcp-port", type=int, default=DEFAULT_MCP_PORT, help="MCP server port")
def start(mcp: bool, mcp_host: str, mcp_port: int) -> None:
    """Start the scheduler daemon."""
    import subprocess
    import sys
    
    # Check if already running
    from scheduler.config import PID_FILE
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            import os
            os.kill(pid, 0)
            click.echo(f"{Fore.YELLOW}Scheduler is already running (PID: {pid})")
            return
        except (ValueError, OSError, ProcessLookupError):
            PID_FILE.unlink(missing_ok=True)
    
    click.echo(f"{Fore.GREEN}Starting scheduler...")
    
    # Start daemon
    cmd = [sys.executable, "-m", "scheduler.daemon"]
    if mcp:
        cmd.extend(["--mcp", "--mcp-host", mcp_host, "--mcp-port", str(mcp_port)])
    
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    click.echo(f"{Fore.GREEN}✓ Scheduler started")
    if mcp:
        click.echo(f"  MCP server: http://{mcp_host}:{mcp_port}/sse")


@cli.command()
def stop() -> None:
    """Stop the scheduler daemon."""
    from scheduler.config import PID_FILE
    
    if not PID_FILE.exists():
        click.echo(f"{Fore.YELLOW}Scheduler is not running")
        return
    
    try:
        pid = int(PID_FILE.read_text().strip())
        import os
        import signal
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        click.echo(f"{Fore.GREEN}✓ Scheduler stopped")
    except Exception as e:
        click.echo(f"{Fore.RED}Error stopping scheduler: {e}", err=True)
        sys.exit(1)


@cli.command()
def status() -> None:
    """View scheduler status."""
    from scheduler.config import PID_FILE
    
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            import os
            os.kill(pid, 0)
            click.echo(f"{Fore.GREEN}Scheduler is running (PID: {pid})")
        except (OSError, ProcessLookupError):
            click.echo(f"{Fore.RED}Scheduler is not running (stale PID file)")
            PID_FILE.unlink(missing_ok=True)
    else:
        click.echo(f"{Fore.YELLOW}Scheduler is not running")


def main() -> None:
    cli()
