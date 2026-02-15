# Cron CLI Scheduler

A cross-platform cron-like task scheduler with rich metadata support, Markdown-based storage, and MCP (Model Context Protocol) integration.

## Metadata

- **Name**: cron-cli-scheduler
- **Version**: 0.1.0
- **Description**: Cross-platform cron-like scheduler with task management and execution history
- **Author**: Cron Scheduler Team
- **License**: MIT

## Capabilities

This skill enables Claude to:

1. **Manage Scheduled Tasks**: Create, read, update, and delete cron jobs with rich metadata
2. **Monitor Task Execution**: View execution history, exit codes, and output
3. **Control Scheduler Lifecycle**: Start, stop, pause, and resume the scheduler daemon
4. **Configure MCP Integration**: Set up SSE-based MCP server for external tool integration
5. **Manage Task Metadata**: Handle priorities, tags, timeouts, retry policies, and environment variables

## When to Use

Use this skill when you need to:

- Set up automated recurring tasks (backups, maintenance, data sync)
- Schedule commands to run at specific times using cron expressions
- Manage task execution with retry policies and timeouts
- Organize tasks with metadata (tags, priorities, owners)
- Monitor task execution history and troubleshoot failures
- Integrate task scheduling with AI agents via MCP protocol

## Tools

### add_task

Create a new scheduled task.

**Parameters:**
- `name` (string, required): Unique task name
- `cron` (string, required): Cron expression (e.g., "0 2 * * *" or @daily)
- `command` (string, required): Shell command to execute
- `description` (string): Task description
- `tags` (array): List of tags for organization
- `timeout` (integer): Timeout in seconds (0 = no limit, default: 0)
- `working_dir` (string): Working directory for command execution
- `environment` (object): Environment variables (values will be Base64 encoded)
- `retry` (object): Retry configuration with `max_attempts` and `delay`
- `priority` (integer): Priority 1-10 (default: 5)
- `owner` (string): Task owner

**Example:**
```json
{
  "name": "daily-backup",
  "cron": "0 2 * * *",
  "command": "/usr/bin/backup.sh",
  "description": "Daily database backup",
  "tags": ["backup", "database"],
  "timeout": 3600,
  "retry": {"max_attempts": 3, "delay": 300},
  "priority": 9,
  "owner": "admin"
}
```

### list_tasks

List all scheduled tasks with their metadata.

**Parameters:** None

**Returns:** Array of task objects with all metadata fields.

### remove_task

Remove a task by name.

**Parameters:**
- `name` (string, required): Task name to remove

**Returns:** Boolean indicating success

### get_task_history

Get execution history for tasks.

**Parameters:**
- `task_name` (string, optional): Filter by specific task name

**Returns:** Array of execution records with task name, execution time, exit code, and output.

### pause_scheduler

Pause the scheduler (stop executing new tasks).

**Parameters:** None

**Returns:** Boolean indicating success

### resume_scheduler

Resume the scheduler.

**Parameters:** None

**Returns:** Boolean indicating success

### get_status

Get scheduler status.

**Parameters:** None

**Returns:** Object with `running`, `paused`, and `tasks_count` fields.

## Workflows

### Setting Up a New Scheduled Task

1. Determine the schedule using cron expression
2. Define the command to execute
3. Set appropriate metadata (timeout, retry, priority)
4. Add environment variables if needed
5. Save the task and verify it appears in the list

### Monitoring Task Health

1. List all tasks to see enabled/disabled status
2. Check execution history for recent runs
3. Review exit codes and output for failures
4. Adjust retry policies or timeouts as needed

### Troubleshooting Failed Tasks

1. Get task history filtered by task name
2. Examine exit code and stderr output
3. Check if working directory exists
4. Verify environment variables are correct
5. Test command manually if needed

### Integrating with MCP

1. Start scheduler with MCP enabled: `cron-cli start --mcp`
2. Configure MCP client with SSE endpoint: `http://localhost:8000/sse`
3. Use MCP tools to manage tasks programmatically

## Examples

### Example 1: Daily Database Backup

```bash
# Create backup task
cron-cli add \
  --name "daily-backup" \
  --cron "0 2 * * *" \
  --command "pg_dump mydb | gzip > /backups/mydb-$(date +%Y%m%d).sql.gz" \
  --description "Daily PostgreSQL backup" \
  --tags backup,database \
  --timeout 3600 \
  --retry-max 3 \
  --retry-delay 300 \
  --priority 9 \
  --owner "dba"

# Verify task was created
cron-cli list --json

# Check execution history next day
cron-cli logs --task daily-backup --json
```

### Example 2: Health Check with Environment Variables

```bash
# Create health check task with env vars
cron-cli add \
  --name "health-check" \
  --cron "*/5 * * * *" \
  --command "curl -f $API_URL/health || echo 'Health check failed'" \
  --env API_URL=https://api.example.com \
  --timeout 30 \
  --priority 5
```

### Example 3: Weekly Cleanup Task

```bash
# Create cleanup task
cron-cli add \
  --name "weekly-cleanup" \
  --cron "0 3 * * 0" \
  --command "find /tmp -type f -mtime +7 -delete" \
  --description "Remove temp files older than 7 days" \
  --tags maintenance,cleanup \
  --working-dir /tmp \
  --priority 3
```

### Example 4: Python API Usage

```python
from scheduler import TaskStorage, Task
from scheduler.models import RetryPolicy

# Initialize storage
storage = TaskStorage()

# Create task
task = Task(
    name="data-sync",
    cron="0 */6 * * *",
    command="python /opt/sync.py",
    description="Sync data every 6 hours",
    tags=["sync", "data"],
    timeout=1800,
    retry=RetryPolicy(max_attempts=2, delay=60),
    priority=7,
    owner="data-team"
)

# Save task
storage.save(task)

# List all tasks
tasks = storage.list_all()
for t in tasks:
    print(f"{t.name}: {t.cron}")
```

## Configuration

### Data Directory

Tasks are stored in `~/.cron-cli-scheduler/tasks/` as Markdown files with YAML Front Matter.

### MCP Server

To enable MCP integration:

```bash
cron-cli start --mcp --mcp-host 0.0.0.0 --mcp-port 8000
```

**Endpoints:**
- `GET /sse` - SSE endpoint for real-time updates
- `POST /messages` - JSON-RPC message endpoint
- `GET /tools` - List available tools

**Claude Desktop Configuration:**

```json
{
  "mcpServers": {
    "cron-scheduler": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Environment Variables

Environment variables in tasks are stored with Base64 encoding:

```yaml
environment:
  DB_HOST: bG9jYWxob3N0      # Base64 encoded "localhost"
  DB_PASS: c2VjcmV0         # Base64 encoded "secret"
```

Values are automatically decoded when the task runs.

## Best Practices

### Task Naming

- Use descriptive, kebab-case names (e.g., `daily-backup`, `weekly-cleanup`)
- Include the purpose and frequency in the name
- Keep names unique and consistent

### Cron Expressions

- Use special expressions for readability: `@daily`, `@hourly`, `@weekly`
- Test complex expressions with online cron validators
- Avoid overlapping schedules for resource-intensive tasks

### Timeouts and Retries

- Always set reasonable timeouts to prevent hanging tasks
- Use retries for transient failures (network calls, external services)
- Set appropriate delays between retries to avoid overwhelming systems

### Security

- Store sensitive data (passwords, API keys) in environment variables
- Use Base64 encoding for environment variable values
- Ensure working directories have appropriate permissions
- Validate commands before execution

### Organization

- Use tags to categorize tasks (e.g., `backup`, `maintenance`, `sync`)
- Set priorities to control execution order during high load
- Assign owners for accountability in team environments

## Troubleshooting

### Task Not Running

1. Check if scheduler is running: `cron-cli status`
2. Verify task is enabled: `cron-cli list --json | jq '.[] | select(.name=="task-name") | .enabled'`
3. Check cron expression validity
4. Review execution history: `cron-cli logs --task <name>`

### Command Failures

1. Check exit code in execution history
2. Review stderr output for error messages
3. Verify working directory exists and is accessible
4. Test command manually in the same environment
5. Check environment variables are correctly set

### MCP Connection Issues

1. Verify MCP server is running: `cron-cli status`
2. Check firewall rules for MCP port (default: 8000)
3. Ensure correct SSE endpoint URL in client configuration
4. Review daemon logs: `~/.cron-cli-scheduler/scheduler.log`

### Permission Errors

1. Ensure commands are executable
2. Check file permissions on working directories
3. Verify user has permission to write to `~/.cron-cli-scheduler/`
4. Review system logs for detailed error messages

## Task File Format

Tasks are stored as Markdown files:

```markdown
---
name: example-task
cron: "0 2 * * *"
command: "/path/to/command.sh"
enabled: true
created_at: 2025-03-22T10:00:00
updated_at: 2025-03-22T10:00:00
description: "Task description"
tags: ["tag1", "tag2"]
timeout: 3600
working_dir: "/home/user"
environment:
  VAR1: dmFsdWUx
retry:
  max_attempts: 3
  delay: 60
priority: 5
owner: "admin"
---

## Execution History

| 执行时间 | 退出码 | 输出 |
|----------|--------|------|
| 2025-03-23 02:00:05 | 0 | Success |
```

## References

- [Cron Expression Reference](https://crontab.guru/)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [Project Repository](https://github.com/yourusername/cron-cli-scheduler)

## Changelog

### 0.1.0
- Initial release
- CLI commands: add, list, remove, logs, start, stop, status
- MCP server with SSE transport
- Markdown-based task storage with YAML Front Matter
- Rich metadata support (tags, priority, timeout, retry, notify)
- Base64-encoded environment variables
- Cross-platform support (Windows, Linux, macOS)
