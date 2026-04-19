import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from ai_pipeline import generate_ai_markdown
from app_config import OUTPUT_DIR, load_config
from feed_fetcher import fetch_feed
from render_pipeline import generate_markdown


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def collect_entries(feeds, proxies) -> list[dict]:
    collected_entries: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(fetch_feed, feed, proxies): feed for feed in feeds}
        for future in as_completed(future_map):
            collected_entries.extend(future.result())
    return collected_entries


def main():
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    batch_dir = OUTPUT_DIR / f"news_{run_timestamp}"
    batch_dir.mkdir(exist_ok=True, parents=True)

    file_handler = logging.FileHandler(batch_dir / "run.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(file_handler)

    logging.info(f"===== 本次运行开始，输出目录: {batch_dir.name} =====")

    try:
        config = load_config()
        if not config.feeds:
            logging.warning("当前无有效配置，退出程序。")
            return

        if config.proxies:
            logging.info(f"已启用网络代理配置: {config.proxies}")

        new_entries = collect_entries(config.feeds, config.proxies)
        logging.info(f"本次抓取共收集 {len(new_entries)} 条候选资讯。")

        if config.ai_config.enabled:
            generate_ai_markdown(new_entries, config.ai_config, config.source_regions, batch_dir)
        else:
            generate_markdown(new_entries, batch_dir)
    finally:
        logging.info("===== 本次运行结束 =====")
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


if __name__ == "__main__":
    main()
