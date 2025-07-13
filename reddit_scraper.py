import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from tavily import TavilyClient
from playwright.sync_api import sync_playwright
import google.generativeai as genai

# Load API keys
load_dotenv()
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Configuration
MAX_THREADS = 3
MAX_COMMENTS_TO_SCAN = 30
MIN_COMMENT_LENGTH = 10
API_RETRY_LIMIT = 5
INITIAL_DELAY = 15
MAX_DELAY = 300
DELAY_MULTIPLIER = 2
BATCH_SIZE = 5

from ratelimit import limits, sleep_and_retry
import time

# Global rate limiter
LAST_API_CALL = 0
MIN_INTERVAL = 5  # seconds between API calls

@sleep_and_retry
@limits(calls=1, period=MIN_INTERVAL)
def call_gemini_api(prompt):
    global LAST_API_CALL
    now = time.time()
    if now - LAST_API_CALL < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - (now - LAST_API_CALL))
    LAST_API_CALL = time.time()
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    return model.generate_content(prompt)


def get_reddit_threads(query, max_results=MAX_THREADS):
    """Get Reddit threads with error handling"""
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
    """Extract comment with improved error handling"""
    try:
        text_node = comment_element.locator("div:has(p)").first
        if text_node.count() == 0:
            return None

        comment_text = text_node.inner_text(timeout=2000).strip()
        if len(comment_text) < MIN_COMMENT_LENGTH:
            return None

        permalink_node = comment_element.locator(
            "a[data-testid='comment_permalink']")
        perm = permalink_node.first.get_attribute(
            "href", timeout=1000) if permalink_node.count() > 0 else None
        full_url = f"https://www.reddit.com{perm}" if perm else None

        replies = []
        children = comment_element.locator(":scope > shreddit-comment")
        for i in range(min(children.count(), 5)):  # Limit replies to 5 levels deep
            child = children.nth(i)
            reply_data = extract_comment_tree(child)
            if reply_data:
                replies.append(reply_data)

        return {
            "text": comment_text,
            "permalink": full_url,
            "replies": replies  # Changed from 'replies' to maintain hierarchy
        }
    except Exception as e:
        print(f"  [!] Error parsing comment: {e}")
        return None


def scrape_all_comments(threads):
    """Scrape comments with better resource management"""
    all_data = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            for i, thread in enumerate(threads, 1):
                print(
                    f"\n[→] ({i}/{len(threads)}) Scanning: {thread['title']}")
                try:
                    page.goto(thread["url"], timeout=60000)
                    page.wait_for_timeout(3000)

                    # Scroll to load comments
                    for _ in range(3):
                        page.mouse.wheel(0, 2000)
                        time.sleep(0.5)

                    comment_blocks = page.locator("shreddit-comment")
                    total_comments = min(
                        comment_blocks.count(), MAX_COMMENTS_TO_SCAN)
                    print(f"[✓] Scanning {total_comments} comments")

                    top_level_comments = []
                    for j in range(total_comments):
                        comment = comment_blocks.nth(j)
                        is_top = comment.evaluate(
                            "node => !node.parentElement.closest('shreddit-comment')")
                        if not is_top:
                            continue
                        comment_data = extract_comment_tree(comment)
                        if comment_data:
                            top_level_comments.append(comment_data)
                            if len(top_level_comments) % 5 == 0:
                                print(
                                    f"  [✓] Saved {len(top_level_comments)} comments")

                    thread_data = {
                        "title": thread["title"],
                        "url": thread["url"],
                        "all_comments": top_level_comments
                    }
                    print(
                        f"[✓] Saved {len(top_level_comments)} comments total")
                    all_data.append(thread_data)

                except Exception as e:
                    print(f"[✗] Error loading thread: {e}")
                    continue

        finally:
            browser.close()
    return all_data


def flatten_comments(comments, parent_text=None):
    """Flatten comment tree while preserving hierarchy info"""
    flat = []
    for comment in comments:
        flat.append({
            "text": comment["text"],
            "permalink": comment.get("permalink"),
            "parent_text": parent_text,
            "original": comment  # Keep full comment for tree rebuild
        })
        flat += flatten_comments(comment.get("replies", []),
                                 parent_text=comment["text"])
    return flat


def simple_keyword_filter(comments, query):
    """Fallback keyword-based filtering"""
    keywords = set(word.lower() for word in query.split() if len(word) > 3)
    relevant = set()

    for comment in comments:
        text = comment['text'].lower()
        if any(keyword in text for keyword in keywords):
            relevant.add(comment['text'])

    return relevant


def filter_relevant_comments(comments, query):
    """Improved filtering with hierarchy preservation"""
    relevant_texts = set()
    current_delay = INITIAL_DELAY

    try:
        model = genai.GenerativeModel("gemini-1.5-flash-8b")

        for i in range(0, len(comments), BATCH_SIZE):
            batch = comments[i:i+BATCH_SIZE]
            prompt = "\n\n".join([
                f"Comment: \"{c['text']}\"\nParent Context: \"{c['parent_text'] or ''}\""
                for c in batch
            ])

            full_prompt = (

                f"You are a helpful assistant tasked with identifying Reddit comments that are directly or indirectly useful for understanding the topic: '{query}'.\n"
                f"Some comments may only mention related experiences, opinions, or tangential aspects — you should include those as well.\n\n"
                f"Below are Reddit comments and their context. Return a list of comment texts that are clearly relevant or even slightly related to '{query}':\n\n{prompt}"

            )

            for attempt in range(API_RETRY_LIMIT):
                try:
                    response = model.generate_content(full_prompt)
                    result = response.text

                    for c in batch:
                        if c["text"] in result:
                            relevant_texts.add(c["text"])
                    break

                except Exception as e:
                    if attempt == API_RETRY_LIMIT - 1:
                        raise

                    if "429" in str(e) or "quota" in str(e).lower():
                        print(
                            f"[!] Rate limited. Waiting {current_delay}s (attempt {attempt+1})")
                        time.sleep(current_delay)
                        current_delay = min(
                            current_delay * DELAY_MULTIPLIER, MAX_DELAY)
                    else:
                        print(f"[!] API error: {e}")
                        break

            print(f"[⏳] Waiting {INITIAL_DELAY}s between batches...")
            time.sleep(INITIAL_DELAY)

    except Exception as e:
        print(f"[⚠️] Falling back to keyword filter due to: {e}")
        return simple_keyword_filter(comments, query)

    return relevant_texts


def rebuild_tree(comment, relevant_texts):
    """Rebuild hierarchical structure with only relevant comments"""
    if comment["text"] not in relevant_texts:
        return None
    replies = []
    for r in comment.get("replies", []):
        rebuilt = rebuild_tree(r, relevant_texts)
        if rebuilt:
            replies.append(rebuilt)
    return {
        "text": comment["text"],
        "permalink": comment.get("permalink"),
        "replies": replies  # Maintain hierarchical structure
    }


def run_pipeline(query):
    """Main pipeline with enhanced error handling"""
    start_time = time.time()
    print(f"\n[🚀] Starting pipeline for: {query}")

    try:
        threads = get_reddit_threads(query)
        if not threads:
            print("[✗] No threads found")
            return

        all_data = scrape_all_comments(threads)
        if not all_data:
            print("[✗] No comments scraped")
            return

        filtered_threads = []
        for thread in all_data:
            print(f"\n[→] Filtering: {thread['title']}")
            flat_comments = flatten_comments(thread.get("all_comments", []))

            if not flat_comments:
                print("[!] No comments to filter")
                continue

            relevant_texts = filter_relevant_comments(flat_comments, query)
            print(f"[✓] Found {len(relevant_texts)} relevant comments")

            # Rebuild hierarchical structure
            filtered_threads.append({
                "title": thread["title"],
                "url": thread["url"],
                "filtered_comments": [
                    rebuild_tree(c, relevant_texts)
                    for c in thread["all_comments"]
                    if rebuild_tree(c, relevant_texts)
                ]
            })

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        place_slug = query.lower().replace(' ', '_')[:50]
        output_path = f"Reddit Reviews/filtered_{place_slug}_{timestamp}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(filtered_threads, f, indent=2, ensure_ascii=False)

        print(f"\n[✅] Pipeline completed in {time.time()-start_time:.1f}s")
        print(f"[💾] Saved to {output_path}")

    except Exception as e:
        print(f"[💥] Pipeline failed: {e}")


if __name__ == "__main__":
    run_pipeline("Triveni Terrace Cafe, Delhi")
