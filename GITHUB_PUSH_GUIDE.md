# GitHub 推送指南

## 快速推送命令

请在本地终端执行以下命令：

```bash
cd /d/projects/openwork/cron-cli-scheduler

# 查看当前状态
git status

# 推送到 GitHub
git push -u origin main
```

## 认证方式

### 方式 1: HTTPS + Personal Access Token (推荐)

当提示输入时：
- **Username**: `bonashen`
- **Password**: 输入您的 GitHub Personal Access Token

**创建 Token 步骤：**
1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 token
5. 粘贴作为密码

### 方式 2: SSH

```bash
# 1. 生成 SSH 密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub

# 3. 添加到 GitHub
# 访问 https://github.com/settings/keys
# 点击 "New SSH key" 并粘贴

# 4. 切换为 SSH 并推送
git remote set-url origin git@github.com:bonashen/cron-cli-scheduler.git
git push -u origin main
```

### 方式 3: GitHub CLI

```bash
# 安装 GitHub CLI
# Windows: winget install --id GitHub.cli
# macOS: brew install gh
# Linux: 参见 https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# 登录
gh auth login

# 推送
gh repo create cron-cli-scheduler --public --source=. --remote=origin --push
```

## 推送成功后

访问仓库：
**https://github.com/bonashen/cron-cli-scheduler**

您将看到：
- 19 个文件
- 约 2500+ 行代码
- 完整的项目文档

## 常见问题

### 错误: "Repository not found"

确保在 GitHub 上创建了同名仓库：
1. 访问 https://github.com/new
2. Repository name: `cron-cli-scheduler`
3. 不要初始化 README
4. 创建仓库后再推送

### 错误: "Permission denied"

检查认证方式是否正确：
- HTTPS: 确认使用了 Personal Access Token 而不是密码
- SSH: 确认公钥已添加到 GitHub

### 错误: "fatal: unable to access"

检查网络连接和代理设置：
```bash
# 检查网络
curl -I https://github.com

# 如果需要代理
git config --global http.proxy http://proxy.example.com:8080
```

## 验证推送

```bash
# 查看远程分支
git branch -r

# 查看提交历史
git log --oneline --graph --all

# 查看远程仓库信息
git remote show origin
```

## 后续开发

推送后，日常开发流程：

```bash
# 修改代码后
git add .
git commit -m "描述你的修改"
git push

# 拉取最新代码
git pull
```
