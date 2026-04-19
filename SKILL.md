---
name: gamerss-daily-publish
description: |
  获取 GameRSS 的每日游戏资讯并发布到小红书。适用于用户要求抓取当日游戏资讯、生成图文卡片、检查小红书登录状态并一键发布时触发。
  首次使用会自动补齐 GameRSS 的 Python 依赖、Playwright Chromium、uv，以及 xiaohongshu-skills 的运行时依赖。
---

# GameRSS Daily Publish

用于执行“抓取每日游戏资讯 -> 生成正文与图片 -> 发布到小红书”的完整流程。
默认使用 skill 内置的 GameRSS 模板，不依赖外部仓库。

## 何时使用

- 用户要求“获取每日游戏资讯并发布到小红书”
- 用户要求“一键跑通 GameRSS 发布链路”
- 用户希望首次使用时自动安装缺失依赖

## 执行规则

- 不要手写一长串命令重做流程，统一运行 `scripts/run_pipeline.py`
- 默认执行发布模式
- 默认只使用 skill 自带模板，并自动在本地创建一个工作副本
- 如果用户明确传入 `--repo-root`，才改用外部 GameRSS 仓库
- 在执行前，不需要手动检查依赖；脚本会自动完成：
  - GameRSS 项目 `.venv`
  - `requirements.txt`
  - Playwright Chromium
  - `uv`
  - `xiaohongshu-skills`
  - `xiaohongshu-skills` 的 `uv sync`
  - `xiaohongshu-skills` 的发布兼容补丁
- 如果用户只想生成资讯、不发小红书，传 `--mode generate`

## 命令

在 skill 目录中运行：

```bash
python3 scripts/run_pipeline.py --mode publish
```

如果用户想让 skill 使用外部的 GameRSS 仓库，可以显式指定：

```bash
python3 scripts/run_pipeline.py --repo-root /abs/path/to/GameRSS --mode publish
```

默认命令会自动在本地创建一个工作副本。

仅生成内容：

```bash
python3 scripts/run_pipeline.py --mode generate
```

## 失败处理

- 如果缺少 `uv`，脚本会自动尝试安装
- 如果缺少 `xiaohongshu-skills`，脚本会自动从 GitHub 安装
- 如果缺少可用的 AI key，脚本会在开始前直接停止，并提示设置 `GAMERSS_AI_API_KEY`
- 如果缺少 Chrome 扩展、小红书未登录，或登录检查超时，脚本会在登录检查阶段直接停止，并提示查看 [references/manual-setup.md](references/manual-setup.md)
- 如果 RSS 源不稳定导致条目不足，照常使用项目已有回退逻辑，不要额外改写正文逻辑
- skill 内置模板中的 `config.json` 不包含真实密钥；运行时优先从环境变量 `GAMERSS_AI_API_KEY` 读取

## 输出约定

- 成功时，直接返回最新 `news_*` 目录
- 发布模式下，额外返回小红书发布结果
- 如果失败，优先返回脚本打印出的关键错误，不要自行概括成模糊结论
