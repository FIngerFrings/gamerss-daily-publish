import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from app_config import AIConfig, BASE_DIR
from render_pipeline import (
    export_news_cards_to_images,
    generate_cover_image,
    generate_digest_text,
    generate_markdown,
    render_final_markdown,
)


GENERIC_TAGS = {"#游戏", "#资讯", "#热点", "#Game", "#game"}
IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
GAME_STOPWORDS = {
    "发售",
    "更新",
    "预告",
    "试玩",
    "演示",
    "公布",
    "上线",
    "媒体",
    "版本",
    "资料片",
    "消息",
    "确认",
    "官方",
    "主机",
    "平台",
    "公司",
    "工作室",
    "电竞",
    "玩家",
    "销量",
    "资讯",
    "新闻",
}


def is_probable_image_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    return not url.lower().endswith((".html", ".htm", ".shtml"))


def split_candidate_images(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    parts = re.split(r"[\s,，；;]+", raw_value.strip())
    return [part.strip() for part in parts if is_probable_image_url(part.strip())]


def can_render_image_url(url: str) -> bool:
    if not is_probable_image_url(url):
        return False

    try:
        response = requests.get(
            url,
            headers=IMAGE_HEADERS,
            timeout=12,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        response.close()
        return content_type.startswith("image/")
    except Exception:
        return False


def pick_working_image(selected_img: str, candidate_imgs: list[str]) -> str:
    checked_urls = []
    for url in [selected_img] + candidate_imgs:
        cleaned = (url or "").strip()
        if not cleaned or cleaned in checked_urls:
            continue
        checked_urls.append(cleaned)
        if can_render_image_url(cleaned):
            return cleaned
    return ""


def normalize_title(raw_title: str) -> str:
    title = raw_title.strip().lstrip("#").strip()
    title = re.sub(r"^\d+\s*[\.、:：\-]\s*", "", title)
    title = re.sub(r"^【|】$", "", title).strip()
    return title


def is_heading_line(line: str) -> bool:
    stripped = line.strip()
    return bool(
        stripped.startswith("###")
        or stripped.startswith("##")
        or re.match(r"^\d+\s*[\.、]", stripped)
    )


def build_empty_item(index: int, title: str) -> dict:
    return {
        "index": index,
        "title": normalize_title(title),
        "source": "未知来源",
        "summary": "",
        "tag": "",
        "candidate_imgs": [],
        "selected_img": "",
    }


def parse_ai_news_items_by_lines(final_text: str) -> list[dict]:
    items: list[dict] = []
    current_item: Optional[dict] = None

    for raw_line in final_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if is_heading_line(line):
            title = re.sub(r"^#{2,3}\s*", "", line).strip()
            if current_item and current_item["title"] and current_item["summary"]:
                items.append(current_item)
            current_item = build_empty_item(len(items) + 1, title)
            continue

        if current_item is None:
            if any(marker in line for marker in ("信息来源", "资讯摘要", "标签", "候选配图", "首选配图")):
                current_item = build_empty_item(len(items) + 1, f"未命名资讯{len(items) + 1}")
            else:
                continue

        if "信息来源" in line:
            current_item["source"] = split_field_value(line)
        elif "资讯摘要" in line:
            current_item["summary"] = split_field_value(line)
        elif "标签" in line:
            current_item["tag"] = split_field_value(line)
        elif "候选配图" in line:
            current_item["candidate_imgs"] = split_candidate_images(split_field_value(line))
        elif "首选配图" in line:
            current_item["selected_img"] = split_field_value(line)
        else:
            image_match = re.search(r"!\[[^\]]*\]\((https?://[^)]+)\)", line)
            if image_match:
                current_item["selected_img"] = image_match.group(1).strip()
                if current_item["selected_img"] not in current_item["candidate_imgs"]:
                    current_item["candidate_imgs"].append(current_item["selected_img"])

    if current_item and current_item["title"] and current_item["summary"]:
        items.append(current_item)

    return items


def parse_ai_news_items(final_text: str) -> list[dict]:
    items = parse_ai_news_items_by_lines(final_text)
    for idx, item in enumerate(items, 1):
        item["index"] = idx
    return items


def split_field_value(line: str) -> str:
    cleaned = re.sub(r"^\s*[-*]\s*", "", line).strip()
    cleaned = re.sub(r"\*\*", "", cleaned)
    if "：" in cleaned:
        return cleaned.split("：", 1)[-1].strip()
    if ":" in cleaned:
        return cleaned.split(":", 1)[-1].strip()
    return cleaned


def sanitize_tag(tag: str) -> str:
    tag = re.sub(r"\s+", "", tag or "")
    tag = tag.lstrip("#")
    tag = re.sub(r"[^\w\u4e00-\u9fff-]", "", tag)
    return f"#{tag}" if tag else ""


def build_tag_from_title(title: str, fallback_index: int) -> str:
    keywords = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", title or "")
    if keywords:
        return sanitize_tag(keywords[0])
    return f"#新闻{fallback_index}"


def dedupe_tags(items: list[dict]) -> None:
    seen = set()
    for item in items:
        tag = sanitize_tag(item.get("tag", ""))
        if not tag or tag in GENERIC_TAGS:
            tag = build_tag_from_title(item.get("title", ""), item["index"])

        if tag in seen:
            keywords = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", item.get("title", ""))
            replacement = ""
            for keyword in keywords:
                candidate = sanitize_tag(keyword)
                if candidate and candidate not in seen and candidate not in GENERIC_TAGS:
                    replacement = candidate
                    break
            if not replacement:
                suffix = 2
                while True:
                    candidate = sanitize_tag(f"{tag.lstrip('#')}{suffix}")
                    if candidate and candidate not in seen:
                        replacement = candidate
                        break
                    suffix += 1
            tag = replacement

        item["tag"] = tag
        seen.add(tag)


def normalize_ai_output_markdown(final_text: str) -> list[dict]:
    items = parse_ai_news_items(final_text)
    if not items:
        return []

    normalized_items = []
    for idx, item in enumerate(items, 1):
        item["title"] = re.sub(r"\s+", " ", item["title"] or "").strip()
        item["summary"] = re.sub(r"\s+", " ", item["summary"] or "").strip()
        item["source"] = re.sub(r"\s+", " ", item["source"]).strip()
        item["candidate_imgs"] = [url for url in item["candidate_imgs"] if is_probable_image_url(url)]

        selected_img = item.get("selected_img", "").strip()
        if item["candidate_imgs"] and selected_img and selected_img not in item["candidate_imgs"]:
            logging.warning(f"[{item['title']}] 首选配图不在候选图内，已尝试回退。")

        working_img = pick_working_image(selected_img, item["candidate_imgs"])
        if selected_img and not working_img:
            logging.warning(f"[{item['title']}] 首选配图及候选配图均不可访问，将跳过出图。")
        elif working_img and working_img != selected_img:
            logging.warning(f"[{item['title']}] 首选配图不可用，已回退到可访问候选图。")

        if not item["summary"]:
            continue

        item["index"] = idx
        item["selected_img"] = working_img
        item["renderable"] = bool(working_img)
        normalized_items.append(item)

    dedupe_tags(normalized_items)
    return normalized_items


def split_sources(source_field: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，/|；;]+", source_field) if part.strip()]


def infer_game_key(item: dict) -> str:
    candidates = []
    tag = sanitize_tag(item.get("tag", ""))
    if tag and tag not in GENERIC_TAGS:
        candidates.append(tag.lstrip("#"))

    title = item.get("title", "")
    quoted = re.findall(r"[《「『【](.{2,30}?)[》」』】]", title)
    candidates.extend(quoted)
    candidates.extend(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", title))

    for raw in candidates:
        value = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "", raw).strip().lower()
        if len(value) < 2 or value in {word.lower() for word in GAME_STOPWORDS}:
            continue
        return value
    return title.strip().lower()


def validate_items(items: list[dict], source_regions: dict[str, str]) -> list[str]:
    issues: list[str] = []
    if not items:
        issues.append("未解析出任何有效条目。")
        return issues
    if len(items) < 5:
        issues.append(f"有效条目过少，实际仅 {len(items)} 条。")

    tags = [item.get("tag", "") for item in items]
    if len(set(tags)) != len(tags):
        issues.append("标签存在重复。")

    domestic = False
    foreign = False
    for item in items:
        if item["selected_img"] and item["selected_img"] not in item["candidate_imgs"]:
            issues.append(f"《{item['title']}》首选配图不在候选列表中。")

        for source in split_sources(item["source"]):
            region = source_regions.get(source, "unknown")
            if region == "domestic":
                domestic = True
            elif region == "foreign":
                foreign = True

    if len(items) >= 5 and (not domestic or not foreign):
        issues.append("信息来源未同时覆盖国内与国外数据源。")

    seen_keys: dict[str, str] = {}
    for item in items:
        game_key = infer_game_key(item)
        if game_key in seen_keys:
            issues.append(f"疑似同一游戏重复入选：{seen_keys[game_key]} / {item['title']}")
        else:
            seen_keys[game_key] = item["title"]

    return issues


def build_ai_input(entries: list[dict]) -> str:
    lines = []
    for idx, entry in enumerate(entries, 1):
        lines.append(f"【资讯{idx}】")
        lines.append(f"标题: {entry.get('title', '无')}")
        lines.append(f"来源: {entry.get('source_name', '未知')}")
        lines.append(f"链接: {entry.get('link', '')}")
        lines.append(f"正文: {entry.get('pure_text', '')}")
        if entry.get("images"):
            lines.append(f"配图列表: {', '.join(entry['images'])}")
        lines.append("-" * 20)
    return "\n".join(lines)


def load_prompt(ai_config: AIConfig) -> str:
    prompt_path = ai_config.prompt_file
    if prompt_path and prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as pf:
            return pf.read()
    return "挑选热门新闻："


def request_ai_digest(
    client,
    ai_config: AIConfig,
    ai_input: str,
    extra_instruction: str = "",
) -> str:
    prompt_content = load_prompt(ai_config)
    format_protocol = """
输出协议：
1. 必须尽量输出 10 条；如果确实无法满足，也至少输出你能确定的全部合格条目。
2. 每条都必须使用下面的 6 行结构，不要省略字段名，不要输出解释。
3. 标题行必须以 `### 序号. 标题` 开头。
4. `候选配图` 中多个链接统一用英文逗号分隔。
5. `首选配图` 若无法确定，可留空，但字段名必须保留。

### 1. 标题
- **信息来源**：来源A, 来源B
- **资讯摘要**：摘要
- **标签**：#标签
- **候选配图**：url1, url2
- **首选配图**：url1
"""
    user_text = f"请对以下资讯进行挑选重构，输出Markdown结果：\n\n{format_protocol}\n\n{ai_input}"
    if extra_instruction:
        user_text += f"\n\n请特别修正以下问题后重新输出完整结果：\n{extra_instruction}"

    message = client.messages.create(
        model=ai_config.model,
        max_tokens=4000,
        system=prompt_content,
        messages=[{"role": "user", "content": [{"type": "text", "text": user_text}]}],
    )

    final_text = ""
    for block in message.content:
        if block.type == "text":
            final_text = block.text
    return final_text


def generate_ai_markdown(
    new_entries: list[dict],
    ai_config: AIConfig,
    source_regions: dict[str, str],
    batch_dir: Path,
) -> bool:
    if not new_entries:
        logging.info("本次执行没有新增抓取内容，跳过 AI 调用。")
        return False

    if not ai_config.api_key:
        logging.error("AI 已启用，但缺少可用 api_key。")
        generate_markdown(new_entries, batch_dir)
        return False

    ai_input = build_ai_input(new_entries)
    logging.info(f"开启 AI 前置处理 (共计 {len(new_entries)} 篇文章参与大模型分析筛选全景审视)")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ai_config.api_key, base_url=ai_config.base_url)
        final_text = ""
        issues: list[str] = []

        for attempt in range(2):
            extra_instruction = "\n".join(f"- {issue}" for issue in issues) if issues else ""
            final_text = request_ai_digest(client, ai_config, ai_input, extra_instruction)
            items = normalize_ai_output_markdown(final_text)
            issues = validate_items(items, source_regions) if items else ["AI 输出未能解析为标准结构。"]

            if not issues:
                now = datetime.now()
                filename = batch_dir / f"news_AI_{now.strftime('%Y%m%d_%H%M')}.md"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(render_final_markdown(items, len(new_entries), now))

                logging.info(f"AI 生成 Markdown 成功！已导出到: {batch_dir.name}/{filename.name}")
                export_news_cards_to_images(items, batch_dir)
                generate_digest_text(items, batch_dir)
                generate_cover_image(batch_dir, BASE_DIR, items)
                return True

            logging.warning(f"AI 结果校验未通过，第 {attempt + 1} 次问题: {' | '.join(issues)}")

        if items:
            logging.warning("AI 输出未完全满足校验要求，但已解析出有效条目，将继续生成结果。")
            now = datetime.now()
            filename = batch_dir / f"news_AI_partial_{now.strftime('%Y%m%d_%H%M')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(render_final_markdown(items, len(new_entries), now))
            export_news_cards_to_images(items, batch_dir)
            generate_digest_text(items, batch_dir)
            generate_cover_image(batch_dir, BASE_DIR, items)
            return True

        logging.warning("AI 输出多次校验失败且无有效条目，回退为原始归档模式。")
        generate_markdown(new_entries, batch_dir)
        return False

    except Exception as e:
        logging.error(f"AI 聚合大模型调用失败: {e}")
        logging.info("回退执行：转用传统拉取直接归档模式。")
        generate_markdown(new_entries, batch_dir)
        return False
