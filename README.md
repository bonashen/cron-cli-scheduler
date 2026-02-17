# Cron CLI Scheduler

跨平台 Python 计划任务调度系统，功能与 cron 一致，提供命令行接口（CLI）和后台服务（daemon）。系统支持与 AI Agent 友好集成，通过 MCP（Model Context Protocol）服务器（基于 SSE，非 STDIO）暴露管理功能。

## 特性

- **跨平台支持**: Windows、macOS、Linux
- **Cron 表达式**: 完整支持标准 cron 语法及特殊表达式（@daily, @hourly, @reboot 等）
- **Markdown 存储**: 任务数据以 Markdown 格式存储，采用 YAML Front Matter
- **MCP 集成**: SSE over HTTP 传输，提供 `/sse` 和 `/messages` 端点
- **丰富元数据**: 描述、标签、环境变量（Base64 编码）、工作目录、超时、重试策略、优先级、所有者
- **AI 友好**: 所有 CLI 命令支持 `--json` 输出，便于 AI 解析

## 安装

```bash
pip install cron-cli-scheduler
```

或使用 uvx（无需安装）:

```bash
uvx cron-cli list
uvx cron-scheduler-daemon --mcp
```

## 快速开始

### 1. 添加任务

```bash
# 每天凌晨 2 点执行备份
cron-cli add \
  --name "daily-backup" \
  --cron "0 2 * * *" \
  --command "/usr/bin/backup.sh" \
  --env DB_HOST=localhost \
  --priority 9 \
  --retry-max 3 \
  --retry-delay 300

# 每小时执行健康检查
cron-cli add \
  --name "health-check" \
  --cron "@hourly" \
  --command "curl -f http://localhost/health"
```

### 2. 列出任务

```bash
cron-cli list
cron-cli list --json  # 结构化输出
```

### 3. 查看任务详情

```bash
cron-cli get daily-backup
cron-cli get daily-backup --json  # 结构化输出
```

### 4. 启动服务

```bash
# 前台运行（用于测试）
cron-scheduler-daemon --mcp

# 后台运行
cron-cli start --mcp --mcp-port 9000

# 查看状态
cron-cli status

# 停止服务
cron-cli stop
```

### 4. 查看执行历史

```bash
cron-cli logs
cron-cli logs --task daily-backup --json
```

## 任务文件格式

任务存储在 `~/.config/cron-scheduler/tasks/` 目录下，每个任务是一个 Markdown 文件：

```markdown
---
name: daily-backup
cron: "0 2 * * *"
command: "/usr/bin/backup.sh"
enabled: true
created_at: 2025-03-22T10:00:00
description: "Daily database backup"
tags: ["backup", "database"]
timeout: 3600
working_dir: "/home/user"
environment:
  DB_HOST: bG9jYWxob3N0   # Base64 encoded
retry:
  max_attempts: 3
  delay: 60
priority: 5
owner: "team-ops"
---

## Execution History

| 执行时间                | 退出码 | 输出                |
|------------------------|--------|---------------------|
| 2025-03-23 02:00:05   | 0      | Backup completed    |
| 2025-03-24 02:00:10   | 1      | Error: disk full    |
```

## MCP 服务器配置

### Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "cron-scheduler": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### 可用 MCP 工具

- `add_task(name, cron, command, ...)` - 添加任务
- `list_tasks()` - 列出所有任务
- `remove_task(name)` - 删除任务
- `get_task_history(task_name)` - 获取执行历史
- `pause_scheduler()` - 暂停调度
- `resume_scheduler()` - 恢复调度
- `get_status()` - 获取服务状态

## CLI 命令参考

| 命令 | 参数 | 说明 |
|------|------|------|
| `add` | `--name`, `--cron`, `--command`, `--description`, `--tags`, `--timeout`, `--working-dir`, `--env`, `--retry-max`, `--retry-delay`, `--priority`, `--owner` | 添加任务 |
| `get` | `<name>`, `--json` | 查看任务详情 |
| `list` | `--json` | 列出任务 |
| `remove` | `<name>` | 删除任务 |
| `logs` | `--task`, `--json` | 查看执行历史 |
| `start` | `--mcp`, `--mcp-host`, `--mcp-port` | 启动服务 |
| `stop` | - | 停止服务 |
| `status` | - | 查看状态 |

## 目录结构

```
~/.config/cron-scheduler/
├── tasks/
│   ├── backup.md
│   └── ...
└── scheduler.pid
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black src/ tests/
ruff check src/ tests/
```

## 发布

项目使用 GitHub Actions 自动发布到 PyPI。

### 发布流程

1. **配置 PyPI 可信发布**:
   - 访问 [PyPI 项目设置](https://pypi.org/manage/project/cron-cli-scheduler/settings/publishing/)
   - 添加新的可信发布者：
     - 提供者：GitHub
     - 仓库：`bonashen/cron-cli-scheduler`（请替换为你的用户名/组织）
     - 工作流：`.github/workflows/release.yml`
     - 环境：`pypi`

2. **创建标签并发布**:
   ```bash
   # 更新版本号（编辑 pyproject.toml 中的 version）
   git add pyproject.toml
   git commit -m "bump version to 0.1.1"
   
   # 创建标签
   git tag v0.1.1
   git push origin v0.1.1
   ```

3. **GitHub Actions 将自动**:
   - 构建包
   - 发布到 PyPI
   - 发布到 TestPyPI
   - 创建 GitHub Release

### 手动触发

也可以通过 GitHub 网站的 Actions 页面手动触发发布工作流。

## 许可证

MIT License
