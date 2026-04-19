import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR


FOREIGN_KEYWORDS = (
    "ign",
    "gamespot",
    "eurogamer",
    "gamesindustry",
    "polygon",
    "kotaku",
    "pcgamer",
    "famitsu",
)

DOMESTIC_KEYWORDS = (
    "小黑盒",
    "机核",
    "3dm",
    "gamersky",
    "二柄",
    "游戏日报",
    "电玩巴士",
    "游戏基因",
    "xiaoheihe",
    "gcores",
    "diershoubing",
    "yxrb",
    "tgbus",
    "gamegene",
)


@dataclass
class FeedConfig:
    id: str
    name: str
    url: str
    enabled: bool = True
    region: str = "unknown"


@dataclass
class AIConfig:
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.minimax.chat/anthropic"
    model: str = "MiniMax-M2.7"
    prompt_file: Optional[Path] = None


@dataclass
class AppConfig:
    feeds: list[FeedConfig]
    proxies: Optional[dict]
    ai_config: AIConfig
    source_regions: dict[str, str]


def infer_region(name: str, url: str, explicit_region: str = "") -> str:
    region = (explicit_region or "").strip().lower()
    if region in {"domestic", "foreign"}:
        return region

    combined = f"{name} {url}".lower()
    if any(keyword in combined for keyword in FOREIGN_KEYWORDS):
        return "foreign"
    if any(keyword.lower() in combined for keyword in DOMESTIC_KEYWORDS):
        return "domestic"
    return "unknown"


def resolve_prompt_file(prompt_value: str) -> Optional[Path]:
    if not prompt_value:
        return None

    prompt_path = Path(prompt_value)
    if not prompt_path.is_absolute():
        prompt_path = BASE_DIR / prompt_path
    return prompt_path


def load_config() -> AppConfig:
    if not CONFIG_FILE.exists():
        logging.error(f"配置文件 {CONFIG_FILE} 不存在！")
        return AppConfig(feeds=[], proxies=None, ai_config=AIConfig(), source_regions={})

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"解析配置文件失败: {e}")
        return AppConfig(feeds=[], proxies=None, ai_config=AIConfig(), source_regions={})

    proxy_enabled = data.get("proxy_enabled", False)
    proxies = data.get("proxies") if proxy_enabled else None

    ai_data = data.get("ai_config", {})
    env_api_key = os.getenv("GAMERSS_AI_API_KEY", "").strip()
    file_api_key = ai_data.get("api_key", "").strip()
    if file_api_key:
        logging.warning("检测到 config.json 中仍存在明文 api_key，建议迁移到环境变量 GAMERSS_AI_API_KEY。")

    ai_config = AIConfig(
        enabled=ai_data.get("enabled", False),
        api_key=env_api_key or file_api_key,
        base_url=ai_data.get("base_url", "https://api.minimax.chat/anthropic"),
        model=ai_data.get("model", "MiniMax-M2.7"),
        prompt_file=resolve_prompt_file(ai_data.get("prompt_file", "")),
    )

    feeds: list[FeedConfig] = []
    source_regions: dict[str, str] = {}
    for item in data.get("feeds", []):
        feed = FeedConfig(
            id=item.get("id", "unknown"),
            name=item.get("name", "Unknown Feed"),
            url=item.get("url", ""),
            enabled=item.get("enabled", True),
            region=infer_region(item.get("name", ""), item.get("url", ""), item.get("region", "")),
        )
        feeds.append(feed)
        source_regions[feed.name] = feed.region

    return AppConfig(
        feeds=feeds,
        proxies=proxies,
        ai_config=ai_config,
        source_regions=source_regions,
    )
