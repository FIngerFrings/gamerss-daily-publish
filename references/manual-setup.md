# Manual Setup

以下项目无法可靠自动化，首次使用时若检测失败，需要按此手动处理。

## Chrome 扩展

`xiaohongshu-skills` 依赖浏览器扩展 `XHS Bridge`。

扩展目录通常位于：

`$CODEX_HOME/skills/xiaohongshu-skills/extension`

默认本机路径：

`~/.codex/skills/xiaohongshu-skills/extension`

安装步骤：

1. 打开 Chrome
2. 访问 `chrome://extensions/`
3. 开启“开发者模式”
4. 点击“加载已解压的扩展程序”
5. 选择 `extension/` 目录
6. 确认扩展 `XHS Bridge` 已启用

## 小红书登录状态

扩展可用后，运行：

```bash
cd ~/.codex/skills/xiaohongshu-skills
uv run python scripts/cli.py check-login
```

如果返回 `{"logged_in": true}`，说明可以发布。

如果未登录，可运行：

```bash
uv run python scripts/cli.py login
```
