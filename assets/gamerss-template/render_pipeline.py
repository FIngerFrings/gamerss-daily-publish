import base64
import html
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

XIAOHONGSHU_INTRO = "今天游戏圈有些新动向，来看看都发生了什么。"


def generate_markdown(new_entries: list[dict], batch_dir: Path, now: Optional[datetime] = None) -> Optional[Path]:
    if not new_entries:
        logging.info("本次执行没有新增抓取内容，不生成 Markdown 文件。")
        return None

    now = now or datetime.now()
    filename = batch_dir / f"news_raw_{now.strftime('%Y%m%d_%H%M')}.md"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("# 自动订阅 RSS 新闻汇总\n\n")
            f.write(f"> **生成时间:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"> **新增内容:** 共计 {len(new_entries)} 篇文章 \n\n")
            f.write("---\n\n")

            for entry in new_entries:
                title = entry.get("title", "无标题")
                link = entry.get("link", "#")
                source = entry.get("source_name", "未知来源")
                published = entry.get("published", "未知发布时间")
                pure_text = entry.get("pure_text", "")
                images = entry.get("images", [])

                f.write(f"## [{title}]({link})\n\n")
                f.write(f"- **来源平台:** {source}\n")
                f.write(f"- **发布时间:** {published}\n\n")

                if pure_text:
                    f.write(f"### 资讯正文\n\n{pure_text}\n\n")

                if images:
                    f.write("### 关联配图\n\n")
                    f.write(f"![封面配图]({images[0]})\n\n")

        logging.info(f"成功导出包含 {len(new_entries)} 条新资讯的文件: {filename.name}")
        return filename
    except Exception as e:
        logging.error(f"生成 Markdown 文件失败: {e}")
        return None


def render_final_markdown(items: list[dict], total_entries: int, now: datetime) -> str:
    lines = [
        "# 🤖 AI 精选 🎮 Top 10 早报",
        "",
        f"> **生成时间:** {now.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"> **情报基底:** 基于今日 {total_entries} 条全网原始快讯提取归纳 ",
        "",
        "---",
        "",
    ]

    for item in items:
        lines.append(f"### {item['index']}. {item['title']}")
        lines.append(f"- **信息来源**：{item['source']}")
        lines.append(f"- **资讯摘要**：{item['summary']}")
        lines.append("")
        if item["selected_img"]:
            lines.append(f"![配图]({item['selected_img']})")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def export_news_cards_to_images(items: list[dict], output_dir: Path):
    logging.info("开始生成视觉图片卡片...")
    if not items:
        logging.warning("未解析出有效新闻条目，跳过出图。")
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logging.error("未安装 playwright，跳过图片生成。")
        return

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{
            margin: 0; padding: 0; background: #ebe6dd; width: 720px;
            font-family: Georgia, "Times New Roman", "Songti SC", "STSong", serif;
        }}
        .container {{
            width: 720px;
            height: 960px;
            background: #f5f1e8;
            color: #171411;
            position: relative;
            overflow: hidden;
        }}
        .gridline {{
            position: absolute;
            inset: 24px;
            border: 1px solid rgba(23, 20, 17, 0.12);
            pointer-events: none;
        }}
        .topline {{
            position: absolute;
            top: 34px;
            left: 40px;
            right: 40px;
            display: flex;
            justify-content: space-between;
            font-size: 16px;
            letter-spacing: 2px;
            color: #6a5e50;
        }}
        .issue {{
            font-style: italic;
        }}
        .hero-wrap {{
            position: absolute;
            top: 86px;
            left: 40px;
            right: 40px;
            height: 360px;
            overflow: hidden;
            background: #ddd5c8;
        }}
        .hero-image {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
            filter: saturate(.92) contrast(1.02);
        }}
        .rule {{
            position: absolute;
            left: 40px;
            right: 40px;
            top: 470px;
            height: 1px;
            background: #1f1b17;
            opacity: .25;
        }}
        .title {{
            position: absolute;
            left: 40px;
            right: 40px;
            top: 500px;
            font-size: 50px;
            line-height: 1.08;
            font-weight: 700;
            letter-spacing: .2px;
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
            overflow: hidden;
        }}
        .summary {{
            position: absolute;
            left: 40px;
            right: 40px;
            top: 700px;
            font-size: 25px;
            line-height: 1.62;
            color: #3f372f;
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 5;
            overflow: hidden;
        }}
        .caption {{
            position: absolute;
            left: 40px;
            bottom: 34px;
            font-size: 15px;
            letter-spacing: 1.5px;
            color: #7d7061;
            text-transform: uppercase;
        }}
        .page {{
            position: absolute;
            right: 40px;
            bottom: 28px;
            font-size: 54px;
            line-height: 1;
            color: #171411;
        }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="gridline"></div>
            <div class="topline">
                <span>GAME REVIEW DAILY</span>
                <span class="issue">Vol. 18</span>
            </div>
            <div class="hero-wrap">
                <img class="hero-image" src="{img_url}">
            </div>
            <div class="rule"></div>
            <div class="title">{title}</div>
            <div class="summary">{summary}</div>
            <div class="caption">Editorial style / magazine reference</div>
            <div class="page">{page_no}</div>
        </div>
    </body>
    </html>
    """

    output_dir.mkdir(exist_ok=True, parents=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2.0)

        renderable_items = [item for item in items if item.get("selected_img")]
        skipped_items = [item for item in items if not item.get("selected_img")]

        for item in skipped_items:
            logging.warning(f"[{item['title']}] 缺少可访问配图，已跳过卡片生成。")

        for idx, item in enumerate(renderable_items, 1):
            title = html.escape(item["title"])
            summary = html.escape(item["summary"])
            img_url = item["selected_img"]

            page.set_content(
                html_template.format(
                    title=title,
                    summary=summary,
                    img_url=img_url,
                    page_no=f"{80 + idx:02d}",
                )
            )
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass

            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:12]
            out_path = output_dir / f"{idx:02d}_{safe_title}.png".replace(" ", "_")
            page.locator(".container").screenshot(path=str(out_path))

        browser.close()

    logging.info(f"所有卡片图片已生成，保存在: {output_dir.name} 文件夹下")


def generate_digest_text(items: list[dict], batch_dir: Path):
    generate_xiaohongshu_text(items, batch_dir)


def normalize_xiaohongshu_line(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = cleaned.rstrip("，；：,;: ")
    if cleaned and cleaned[-1] not in "。！？!?":
        cleaned = f"{cleaned}。"
    return cleaned


def build_xiaohongshu_item_line(item: dict) -> str:
    title = normalize_xiaohongshu_line(item.get("title", ""))
    return f"{item['index']}. {title}".strip()


def generate_xiaohongshu_text(items: list[dict], batch_dir: Path, max_chars: int = 950):
    if not items:
        logging.warning("未解析出有效新闻条目，跳过生成正文文件。")
        return

    intro = XIAOHONGSHU_INTRO
    tags_line = " ".join(item["tag"] for item in items if item.get("tag"))
    selected_blocks: list[str] = []
    current_text = intro

    for item in items:
        block = build_xiaohongshu_item_line(item)
        candidate_parts = [intro, *selected_blocks, block]
        if tags_line:
            candidate_parts.append(tags_line)
        candidate_text = "\n\n".join(candidate_parts)
        if len(candidate_text) > max_chars:
            break
        selected_blocks.append(block)
        current_text = candidate_text

    if not selected_blocks:
        logging.warning("正文文件未能在字数预算内生成有效内容。")
        return

    current_text = "\n\n".join([intro, *selected_blocks])
    if tags_line:
        current_text = f"{current_text}\n\n{tags_line}"

    date_str = datetime.now().strftime("%m.%d")
    digest_filename = batch_dir / f"每日游讯 ｜ {date_str}.txt"
    with open(digest_filename, "w", encoding="utf-8") as f:
        f.write(current_text)

    logging.info(f"正文文件已生成: {digest_filename.name}")


def generate_cover_image(batch_dir: Path, base_dir: Path, items: Optional[list[dict]] = None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logging.error("未安装 playwright，跳过封面生成。")
        return

    date_str = datetime.now().strftime("%m.%d")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ margin: 0; padding: 0; background: #efe9de; }}
        .cover {{
            width: 720px;
            height: 960px;
            position: relative;
            overflow: hidden;
            background: linear-gradient(180deg, #f5f0e7 0%, #ece3d5 100%);
            font-family: Georgia, "Times New Roman", "Songti SC", "STSong", serif;
            color: #15120f;
        }}
        .frame {{
            position: absolute;
            inset: 22px;
            border: 1px solid rgba(21,18,15,.15);
        }}
        .masthead {{
            position: absolute;
            top: 30px;
            left: 38px;
            right: 38px;
            display: flex;
            justify-content: space-between;
            font-size: 16px;
            color: #6e6253;
            letter-spacing: 2px;
        }}
        .bg-word {{
            position: absolute;
            left: 28px;
            top: 94px;
            font-size: 210px;
            line-height: .84;
            color: rgba(21,18,15,.055);
            font-weight: 700;
        }}
        .centerpiece {{
            position: absolute;
            left: 50px;
            top: 138px;
            right: 50px;
        }}
        .micro {{
            font-size: 18px;
            letter-spacing: 4px;
            color: #7a6d5d;
            margin-bottom: 16px;
        }}
        .main-title {{
            font-size: 142px;
            line-height: .86;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 22px;
        }}
        .deck {{
            max-width: 550px;
            font-size: 31px;
            line-height: 1.5;
            color: #3f372f;
        }}
        .divider {{
            width: 210px;
            height: 2px;
            background: #1f1b17;
            opacity: 0.18;
            margin: 34px 0 0;
        }}
        .date-block {{
            position: absolute;
            left: 50px;
            right: 48px;
            bottom: 64px;
        }}
        .date {{
            font-size: 112px;
            line-height: 0.92;
            color: #15120f;
        }}
        .footer-note {{
            position: absolute;
            right: 0;
            bottom: 10px;
            width: 218px;
            font-size: 18px;
            line-height: 1.6;
            letter-spacing: 1px;
            color: #746858;
            text-align: right;
        }}
    </style>
    </head>
    <body>
        <div class="cover">
            <div class="frame"></div>
            <div class="masthead">
                <span>GAME REVIEW DAILY</span>
                <span>ISSUE 01</span>
            </div>
            <div class="bg-word">ISSUE</div>
            <div class="centerpiece">
                <div class="micro">FOUNDING EDITION</div>
                <div class="main-title">每日游讯</div>
                <div class="deck">为每天的游戏世界，留下更有秩序也更有质感的记录。</div>
                <div class="divider"></div>
            </div>
            <div class="date-block">
                <div class="date">{date_str}</div>
                <div class="footer-note">Launch issue layout with a stronger sense of magazine identity and commemorative weight.</div>
            </div>
        </div>
    </body>
    </html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2.0)
        page.set_content(html_content)
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        out_path = batch_dir / "封面.png"
        page.locator(".cover").screenshot(path=str(out_path))
        browser.close()

    logging.info(f"封面图已生成: {out_path.name}")
