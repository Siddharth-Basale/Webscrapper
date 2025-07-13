import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

def scrape_google_maps_reviews(place_id, max_reviews=20, output_file=None):
    reviews_data = []
    url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"[→] Visiting: {url}")
        page.goto(url, timeout=45000)
        page.wait_for_timeout(2500)

        # STEP 1: Click "Reviews" tab
        try:
            page.get_by_role("tab", name="Reviews").click()
            page.wait_for_timeout(2000)
            print("[✓] Clicked on 'Reviews' tab")
        except Exception as e:
            print("[✗] Failed to click 'Reviews' tab:", e)
            browser.close()
            return []

        # STEP 2: Scroll to load reviews
        print("[→] Scrolling...")
        for _ in range(3):
            page.mouse.wheel(0, 4000)
            time.sleep(0.6)
        print("[✓] Done scrolling")

        # STEP 3: Extract reviews
        review_elements = page.locator('div[data-review-id]')
        total_found = review_elements.count()
        print(f"[✓] Found {total_found} review blocks")

        seen = set()
        count_added = 0

        for el in review_elements.all():
            if count_added >= max_reviews:
                break
            try:
                author = el.locator('div[class*="d4r55"]').inner_text(timeout=300)
                time_ago = el.locator('span[class*="rsqaWe"]').inner_text(timeout=300)
                text = el.locator('span[class*="wiI7pd"]').inner_text(timeout=300)

                review_hash = f"{author}|{time_ago}|{text}"
                if review_hash in seen:
                    continue
                seen.add(review_hash)

                reviews_data.append({
                    "author": author,
                    "time": time_ago,
                    "text": text
                })
                count_added += 1

            except Exception as e:
                print(f"[!] Skipping review due to error: {e}")
                continue

        print(f"[✓] Extracted {len(reviews_data)} unique reviews")

        # STEP 4: Save to file inside 'Google Reviews' folder
        os.makedirs("Google Reviews", exist_ok=True)
        if output_file is None:
            output_file = f"Google Reviews/reviews_{place_id}_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(reviews_data, f, indent=2, ensure_ascii=False)

        print(f"[💾] Saved to {output_file}")
        browser.close()
        return reviews_data


# --- Run for standalone testing ---
if __name__ == "__main__":
    place_id = "ChIJgYWp8Cz9DDkRHGRazZ5BlZg"  # Example
    scrape_google_maps_reviews(place_id, max_reviews=20)