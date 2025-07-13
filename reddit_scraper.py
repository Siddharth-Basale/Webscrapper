import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from tavily import TavilyClient
from playwright.sync_api import sync_playwright

# Load API keys
load_dotenv()
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Configuration
MAX_THREADS = 3
MAX_COMMENTS_TO_SCAN = 30
MIN_COMMENT_LENGTH = 10

def get_reddit_threads(query, max_results=MAX_THREADS):
    try:
        print(f"[→] Searching Reddit for: {query}")
        response = tavily_client.search(
            query=f"{query} site:reddit.com",
            max_results=max_results,
            include_domains=["reddit.com"],
            include_content=False
        )
        threads = []
        for r in response["results"]:
            url = r["url"].split("?")[0]
            if "reddit.com/r/" in url and "/comments/" in url:
                threads.append({
                    "title": r["title"],
                    "url": url
                })
        print(f"[✓] Found {len(threads)} Reddit threads")
        return threads
    except Exception as e:
        print(f"[✗] Error searching Reddit: {e}")
        return []

def extract_comment_tree(comment_element):
    try:
        text_node = comment_element.locator("div:has(p)").first
        if text_node.count() == 0:
            return None

        comment_text = text_node.inner_text(timeout=2000).strip()
        comment_text = comment_text.encode('utf-8', errors='replace').decode('utf-8')  # 🛠️ sanitize here

        if len(comment_text) < MIN_COMMENT_LENGTH:
            return None

        permalink_node = comment_element.locator("a[data-testid='comment_permalink']")
        perm = permalink_node.first.get_attribute("href", timeout=1000) if permalink_node.count() > 0 else None
        full_url = f"https://www.reddit.com{perm}" if perm else None

        replies = []
        children = comment_element.locator(":scope > shreddit-comment")
        for i in range(min(children.count(), 5)):
            child = children.nth(i)
            reply_data = extract_comment_tree(child)
            if reply_data:
                replies.append(reply_data)

        return {
            "text": comment_text,
            "permalink": full_url,
            "replies": replies
        }
    except Exception as e:
        print(f"  [!] Error parsing comment: {e}")
        return None

def scrape_all_comments(threads):
    all_data = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            for i, thread in enumerate(threads, 1):
                print(f"\n[→] ({i}/{len(threads)}) Scanning: {thread['title']}")
                try:
                    page.goto(thread["url"], timeout=60000)
                    page.wait_for_timeout(3000)

                    for _ in range(3):
                        page.mouse.wheel(0, 2000)
                        time.sleep(0.5)

                    comment_blocks = page.locator("shreddit-comment")
                    total_comments = min(comment_blocks.count(), MAX_COMMENTS_TO_SCAN)
                    print(f"[✓] Scanning {total_comments} comments")

                    top_level_comments = []
                    for j in range(total_comments):
                        comment = comment_blocks.nth(j)
                        is_top = comment.evaluate("node => !node.parentElement.closest('shreddit-comment')")
                        if not is_top:
                            continue
                        comment_data = extract_comment_tree(comment)
                        if comment_data:
                            top_level_comments.append(comment_data)
                            if len(top_level_comments) % 5 == 0:
                                print(f"  [✓] Saved {len(top_level_comments)} comments")

                    thread_data = {
                        "title": thread["title"],
                        "url": thread["url"],
                        "all_comments": top_level_comments
                    }
                    print(f"[✓] Saved {len(top_level_comments)} comments total")
                    all_data.append(thread_data)

                except Exception as e:
                    print(f"[✗] Error loading thread: {e}")
                    continue

        finally:
            browser.close()
    return all_data

def sanitize_text(obj):
    """Recursively sanitize strings in any data structure"""
    if isinstance(obj, str):
        return obj.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    elif isinstance(obj, list):
        return [sanitize_text(item) for item in obj]
    elif isinstance(obj, dict):
        return {sanitize_text(k): sanitize_text(v) for k, v in obj.items()}
    return obj

def run_pipeline(query):
    start_time = time.time()
    print(f"\n[🚀] Starting pipeline for: {query}")

    try:
        threads = get_reddit_threads(query)
        if not threads:
            print("[✗] No threads found")
            return None

        all_data = scrape_all_comments(threads)
        if not all_data:
            print("[✗] No comments scraped")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        place_slug = query.lower().replace(' ', '_')[:50]
        output_path = f"Reddit Reviews/unfiltered_{place_slug}_{timestamp}.json"

        # ✅ Sanitize before writing
        all_data = sanitize_text(all_data)

        with open(output_path, "w", encoding="utf-8", errors='replace') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        print(f"\n[✅] Pipeline completed in {time.time()-start_time:.1f}s")
        print(f"[💾] Saved to {output_path}")
        return output_path

    except Exception as e:
        print(f"[💥] Pipeline failed: {e}")
        return None

if __name__ == "__main__":
    run_pipeline("Triveni Terrace Cafe, Delhi")
