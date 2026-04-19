import html
import logging
import re
import time
from typing import Optional

import feedparser
import requests

from app_config import FeedConfig


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}


def fetch_feed(feed_info: FeedConfig, proxies: Optional[dict] = None) -> list[dict]:
    feed_id = feed_info.id
    name = feed_info.name
    url = feed_info.url

    if not feed_info.enabled:
        logging.info(f"订阅源 [{name}] 未启用，跳过抓取。")
        return []

    logging.info(f"开始抓取 [{name}] - {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=60, proxies=proxies)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)

        if parsed.bozo and isinstance(parsed.bozo_exception, Exception):
            logging.debug(f"订阅源 [{name}] 有异常，但不影响数据提取: {parsed.bozo_exception}")

        current_time = time.mktime(time.gmtime())
        entries = parsed.get("entries", [])
        valid_entries: list[dict] = []

        for entry in entries:
            if "published_parsed" in entry and entry.published_parsed:
                entry_time = time.mktime(entry.published_parsed)
                if current_time - entry_time > 24 * 3600:
                    continue

            content = ""
            if "content" in entry and len(entry.content) > 0:
                content = entry.content[0].value
            elif "summary" in entry:
                content = entry.summary

            images: list[str] = []
            pure_text = ""
            if content:
                images = re.findall(r'<img[^>]+src=["\'](.*?)["\']', content, flags=re.IGNORECASE)
                content_clean = re.sub(
                    r"<(script|style|iframe)[^>]*>[\s\S]*?</\1>",
                    "",
                    content,
                    flags=re.IGNORECASE,
                )
                content_clean = re.sub(r"</?(br|p|div|li)[^>]*>", "\n", content_clean, flags=re.IGNORECASE)
                pure_text = re.sub(r"<[^>]+>", "", content_clean)
                pure_text = html.unescape(pure_text)
                pure_text = re.sub(r"\n\s*\n", "\n\n", pure_text).strip()

            if len(pure_text) < 50 or not images:
                continue

            entry["pure_text"] = pure_text
            entry["images"] = images
            entry["source_name"] = name
            entry["source_id"] = feed_id
            valid_entries.append(entry)

        logging.info(f"[{name}] 原始拉取 {len(entries)} 条，经过(近24H/有图/长文)过滤后保留 {len(valid_entries)} 条。")
        return valid_entries

    except requests.exceptions.ConnectionError as e:
        logging.error(f"网络连接失败 - [{name}]: {e}")
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP 错误异常 - [{name}]: {e}")
    except requests.exceptions.Timeout as e:
        logging.error(f"网络请求超时 - [{name}]: {e}")
    except Exception as e:
        logging.error(f"解析或执行时发生未知错误 - [{name}]: {e}")

    return []
