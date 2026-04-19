#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


MARKER_FILES = [
    "main.py",
    "feed_fetcher.py",
    "render_pipeline.py",
    "publish_xiaohongshu.sh",
    "requirements.txt",
]
REQUIRED_MODULES = ["requests", "feedparser", "anthropic", "playwright"]
XHS_SKILL_REPO = "autoclaw-cc/xiaohongshu-skills"
XHS_SKILL_NAME = "xiaohongshu-skills"
BUNDLED_TEMPLATE_DIR = "assets/gamerss-template"
XHS_PATCH_DIR = "assets/xhs-patches"


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, check=True)


def run_capture(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=timeout,
    )


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def ensure_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def bundled_template_root() -> Path:
    return skill_root() / BUNDLED_TEMPLATE_DIR


def xhs_patch_root() -> Path:
    return skill_root() / XHS_PATCH_DIR


def find_repo_root(start: Path) -> Path | None:
    for current in [start, *start.parents]:
        if all((current / marker).exists() for marker in MARKER_FILES):
            return current
    return None


def resolve_repo_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not all((root / marker).exists() for marker in MARKER_FILES):
            fail(f"指定的 repo-root 不是有效的 GameRSS 仓库: {root}")
        return root

    return materialize_bundled_repo()


def default_workspace_root() -> Path:
    return codex_home() / "workspaces" / "gamerss-daily-publish"


def materialize_bundled_repo() -> Path:
    source_root = bundled_template_root()
    if not source_root.exists():
        fail(f"skill 内未找到内置 GameRSS 模板: {source_root}")

    workspace_root = default_workspace_root()
    workspace_root.mkdir(parents=True, exist_ok=True)
    dest_root = workspace_root / "GameRSS"

    if not dest_root.exists():
        shutil.copytree(source_root, dest_root)

    for marker in MARKER_FILES + ["config.json"]:
        if not (dest_root / marker).exists():
            fail(f"内置模板不完整，缺少文件: {dest_root / marker}")

    return dest_root


def ensure_venv(repo_root: Path) -> Path:
    venv_python = repo_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        run(["python3", "-m", "venv", ".venv"], cwd=repo_root)
    return venv_python


def missing_modules(python_bin: Path) -> list[str]:
    code = (
        "import importlib.util\n"
        f"mods={REQUIRED_MODULES!r}\n"
        "missing=[m for m in mods if importlib.util.find_spec(m) is None]\n"
        "print('\\n'.join(missing))\n"
    )
    result = run_capture([str(python_bin), "-c", code])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def ensure_project_dependencies(repo_root: Path, python_bin: Path) -> None:
    missing = missing_modules(python_bin)
    if missing:
        run([str(repo_root / ".venv" / "bin" / "pip"), "install", "-r", "requirements.txt"], cwd=repo_root)


def ensure_ai_key(repo_root: Path, *, required: bool) -> None:
    env_key = os.environ.get("GAMERSS_AI_API_KEY", "").strip()
    if env_key:
        return

    config_file = repo_root / "config.json"
    file_key = ""
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            file_key = str(data.get("ai_config", {}).get("api_key", "")).strip()
        except Exception:
            file_key = ""

    if file_key:
        return

    if required:
        fail(
            "未找到可用的 AI key。"
            " 请设置环境变量 GAMERSS_AI_API_KEY，或在工作副本的 config.json 中填写 ai_config.api_key。"
        )


def ensure_playwright_browser(python_bin: Path) -> None:
    check_code = """
from pathlib import Path
from playwright.sync_api import sync_playwright

p = sync_playwright().start()
browser_path = Path(p.chromium.executable_path)
p.stop()
raise SystemExit(0 if browser_path.exists() else 1)
"""
    result = subprocess.run([str(python_bin), "-c", check_code], text=True)
    if result.returncode != 0:
        run([str(python_bin), "-m", "playwright", "install", "chromium"])


def ensure_uv() -> str:
    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path

    run(["python3", "-m", "pip", "install", "--user", "uv"])
    user_base = run_capture(["python3", "-c", "import site; print(site.USER_BASE)"]).stdout.strip()
    candidates = [
        Path(user_base) / "bin" / "uv",
        Path.home() / ".local" / "bin" / "uv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path

    fail("已尝试安装 uv，但仍未找到可执行文件。")


def ensure_xhs_skill() -> Path:
    xhs_dir = codex_home() / "skills" / XHS_SKILL_NAME
    if xhs_dir.exists():
        return xhs_dir

    installer = codex_home() / "skills" / ".system" / "skill-installer" / "scripts" / "install-skill-from-github.py"
    if not installer.exists():
        fail(f"未找到 skill-installer: {installer}")

    run(
        [
            "python3",
            str(installer),
            "--repo",
            XHS_SKILL_REPO,
            "--path",
            ".",
            "--name",
            XHS_SKILL_NAME,
        ]
    )
    return xhs_dir


def ensure_xhs_dependencies(uv_bin: str, xhs_dir: Path) -> None:
    run([uv_bin, "sync"], cwd=xhs_dir)


def ensure_xhs_patches(xhs_dir: Path) -> None:
    patch_dir = xhs_patch_root()
    if not patch_dir.exists():
        return

    publish_patch = patch_dir / "publish.py"
    target_publish = xhs_dir / "scripts" / "xhs" / "publish.py"
    if publish_patch.exists() and target_publish.exists():
        target_publish.write_text(publish_patch.read_text(encoding="utf-8"), encoding="utf-8")


def parse_last_json_blob(text: str) -> dict | None:
    lines = [line for line in text.splitlines() if line.strip()]
    for start in range(len(lines)):
        candidate = "\n".join(lines[start:])
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def ensure_xhs_logged_in(uv_bin: str, xhs_dir: Path) -> None:
    manual_setup = skill_root() / "references" / "manual-setup.md"
    try:
        result = run_capture(
            [uv_bin, "run", "python", "scripts/cli.py", "check-login"],
            cwd=xhs_dir,
            timeout=45,
        )
    except subprocess.TimeoutExpired as exc:
        output = ensure_text(exc.stdout) + ensure_text(exc.stderr)
        payload = parse_last_json_blob(output)
        if payload and payload.get("logged_in") is True:
            return
        if output:
            print(output, file=sys.stderr)
        fail(
            "等待小红书浏览器扩展或登录状态检查超时。"
            f" 请先按 {manual_setup} 安装并启用 XHS Bridge 扩展，确认浏览器中的小红书已登录后再重试。"
        )

    payload = parse_last_json_blob(result.stdout)
    if payload and payload.get("logged_in") is True:
        return

    print(result.stdout, file=sys.stderr)
    if payload and payload.get("logged_in") is False:
        fail(
            "已连接到小红书自动化环境，但当前账号未登录。"
            f" 请先按 {manual_setup} 完成登录，再重新执行。"
        )
    fail(
        "未能确认小红书扩展连接或登录状态。"
        f" 请先按 {manual_setup} 完成扩展安装与登录，再重新执行。"
    )


def latest_news_dir(repo_root: Path) -> Path | None:
    news_dirs = sorted(path for path in repo_root.iterdir() if path.is_dir() and path.name.startswith("news_"))
    return news_dirs[-1] if news_dirs else None


def run_generate(repo_root: Path, python_bin: Path) -> None:
    run([str(python_bin), "main.py"], cwd=repo_root, env=os.environ.copy())


def run_publish(repo_root: Path, xhs_dir: Path) -> None:
    env = os.environ.copy()
    env["GAMERSS_DIR"] = str(repo_root)
    env["XHS_DIR"] = str(xhs_dir)
    run(["bash", str(repo_root / "publish_xiaohongshu.sh")], cwd=repo_root, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap and run the GameRSS daily publish pipeline.")
    parser.add_argument("--repo-root", help="GameRSS 仓库根目录")
    parser.add_argument("--mode", choices=["generate", "publish"], default="publish")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    python_bin = ensure_venv(repo_root)
    ensure_project_dependencies(repo_root, python_bin)
    ensure_playwright_browser(python_bin)
    ensure_ai_key(repo_root, required=(args.mode == "publish"))

    if args.mode == "generate":
        run_generate(repo_root, python_bin)
        news_dir = latest_news_dir(repo_root)
        if news_dir:
            print(f"生成完成: {news_dir}")
        return

    uv_bin = ensure_uv()
    xhs_dir = ensure_xhs_skill()
    ensure_xhs_dependencies(uv_bin, xhs_dir)
    ensure_xhs_patches(xhs_dir)
    ensure_xhs_logged_in(uv_bin, xhs_dir)
    run_publish(repo_root, xhs_dir)
    news_dir = latest_news_dir(repo_root)
    if news_dir:
        print(f"发布完成，产物目录: {news_dir}")


if __name__ == "__main__":
    main()
