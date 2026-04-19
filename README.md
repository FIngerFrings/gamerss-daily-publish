# gamerss-daily-publish

一个可分享的 agent skill，用来自动完成这条链路：

`抓取每日游戏资讯 -> 生成图文卡片 -> 生成小红书正文 -> 发布到小红书`

这份仓库默认使用内置的 GameRSS 模板，不要求目标机器预先准备一份单独的 GameRSS 仓库。别人第一次拿到 skill 后，可以直接在新设备上自举环境并运行。

## 这是什么项目

`gamerss-daily-publish` 本质上是一个可复用的自动化 skill，适合这些场景：

- 每日抓取游戏资讯并生成图文内容
- 检查小红书登录状态后直接发布
- 首次在新设备上自动补齐运行环境
- 把 GameRSS 这条流水线打包成一个可复用、可分享的技能

仓库里已经内置了 GameRSS 运行模板，以及小红书发布兼容补丁。

## 仓库结构

- `SKILL.md`: skill 的触发规则和执行说明
- `README.md`: 项目说明、安装方式、使用方式
- `scripts/run_pipeline.py`: 总入口，负责环境自举和执行生成/发布
- `assets/gamerss-template/`: 内置 GameRSS 模板
- `assets/xhs-patches/`: 对 `xiaohongshu-skills` 的兼容补丁
- `assets/xhs-extension/`: 随仓库提供的 `XHS Bridge` 浏览器扩展副本
- `references/manual-setup.md`: 首次使用时仍需手动处理的部分
- `agents/openai.yaml`: skill 的展示配置

## 自动处理的环境

首次运行时，脚本会自动补齐这些内容：

- GameRSS 工作副本
- Python `.venv`
- `requirements.txt` 依赖
- Playwright Chromium
- `uv`
- `xiaohongshu-skills`
- `xiaohongshu-skills` 的 `uv sync`
- 小红书发布兼容补丁

## 仍需手动处理的部分

下面这些内容目前不适合完全自动化，第一次使用需要手动完成：

- Chrome 扩展 `XHS Bridge` 安装与启用
- 小红书账号登录
- AI key 提供

详细步骤见 [references/manual-setup.md](references/manual-setup.md)。

## 前置条件

目标机器至少需要：

- `python3`
- 可访问网络以安装依赖
- 可使用 Chrome，并允许安装扩展

## 怎么安装这个 skill

### 方式一：直接复制到本地 skills 目录

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.agent-home}"
mkdir -p "$AGENT_HOME/skills"
cp -R gamerss-daily-publish "$AGENT_HOME/skills/gamerss-daily-publish"
```

### 方式二：用软链接安装

适合本地开发和迭代：

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.agent-home}"
mkdir -p "$AGENT_HOME/skills"
ln -s /abs/path/to/gamerss-daily-publish "$AGENT_HOME/skills/gamerss-daily-publish"
```

安装完成后，重启你的 agent 运行环境，让它重新加载 skill。

## 怎么使用

### 只生成每日资讯

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.agent-home}"
cd "$AGENT_HOME/skills/gamerss-daily-publish"
python3 scripts/run_pipeline.py --mode generate
```

### 生成并发布到小红书

```bash
export AGENT_HOME="${AGENT_HOME:-$HOME/.agent-home}"
cd "$AGENT_HOME/skills/gamerss-daily-publish"
export GAMERSS_AI_API_KEY="your_api_key"
python3 scripts/run_pipeline.py --mode publish
```

### 使用外部 GameRSS 仓库

如果你不想用内置模板，也可以显式指定已有仓库：

```bash
python3 scripts/run_pipeline.py --repo-root /abs/path/to/GameRSS --mode publish
```

## 输出位置

默认会把 GameRSS 工作副本落到：

```text
$AGENT_HOME/workspaces/gamerss-daily-publish/GameRSS
```

生成的内容产物位于该目录下的 `news_*` 文件夹中。

## 安全说明

这份仓库当前已经检查过，没有包含真实 API key。

当前安全状态：

- `assets/gamerss-template/config.json` 中的 `ai_config.api_key` 为空字符串
- README 里只保留了环境变量示例，没有写入真实密钥
- skill 运行时优先读取环境变量 `GAMERSS_AI_API_KEY`

分享给别人时建议继续保持：

- 不要把真实 AI key 提交进仓库
- 如果需要演示，使用环境变量或 `.env` 之外的私有方式注入
- 首次使用前先让对方完成 Chrome 扩展安装和小红书登录
- 如果只想验证环境是否正常，先跑 `--mode generate`
