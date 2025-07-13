import os
import json
from multiprocessing import Pool
from serp import get_places_from_google_maps, save_places_to_json
from google_maps_scraper import scrape_google_maps_reviews
from reddit_scraper import run_pipeline
from datetime import datetime

def scrape_google_reviews(place):
    try:
        print(f"Starting Google Maps scraping for: {place['name']}")
        output_file = f"Google Reviews/reviews_{place['name'].replace(' ', '_')}.json"
        reviews = scrape_google_maps_reviews(
            place['source_url'],
            max_reviews=20,
            output_file=output_file
        )
        print(f"Completed Google Maps scraping for: {place['name']}")
        return {
            "name": place['name'],
            "success": True,
            "reviews": reviews,
            "output_file": output_file
        }
    except Exception as e:
        print(f"Error in Google Maps scraping for {place['name']}: {e}")
        return {"name": place['name'], "success": False, "error": str(e)}

def scrape_reddit(args):
    place, city = args
    try:
        print(f"Starting Reddit scraping for: {place['name']}")
        query = f"{place['name']} {city}"
        output_file = run_pipeline(query)
        print(f"Completed Reddit scraping for: {place['name']}")
        return {"name": place['name'], "success": True, "output_file": output_file}
    except Exception as e:
        print(f"Error in Reddit scraping for {place['name']}: {e}")
        return {"name": place['name'], "success": False, "error": str(e)}

def sanitize_string(obj):
    if isinstance(obj, str):
        return obj.encode('utf-8', errors='replace').decode('utf-8')
    elif isinstance(obj, list):
        return [sanitize_string(item) for item in obj]
    elif isinstance(obj, dict):
        return {sanitize_string(k): sanitize_string(v) for k, v in obj.items()}
    return obj

def main(city=None, category=None):
    if isinstance(city, tuple):  # Handle Flask's argument passing
        city, category = city
    if not city or not category:
        city = input("Enter the city name: ").strip()
        category = input("Enter the category: ").strip()

    print(f"\nStarting data collection for {category} in {city}...\n")

    print("=== Step 1: Fetching places ===")
    places = get_places_from_google_maps(city, category, max_places=3)
    print(f"Found {len(places)} places.")

    if not places:
        print("No places found. Exiting.")
        return

    save_places_to_json(places, city, category)

    print("\n=== Step 2: Google Maps reviews scraping ===")
    with Pool(processes=min(3, len(places))) as pool:
        google_results = pool.map(scrape_google_reviews, places)

    print("\n=== Step 3: Reddit scraping ===")
    with Pool(processes=min(3, len(places))) as pool:
        reddit_results = pool.map(scrape_reddit, [(place, city) for place in places])

    final_output = []
    for place in places:
        google_data = next((r for r in google_results if r['name'] == place['name'] and r['success']), None)
        reddit_data = next((r for r in reddit_results if r['name'] == place['name'] and r['success']), None)

        reddit_comments = []
        if reddit_data and reddit_data.get("output_file"):
            try:
                with open(reddit_data['output_file'], 'r', encoding='utf-8', errors='replace') as f:
                    reddit_threads = json.load(f)
                    reddit_comments = reddit_threads
            except Exception as e:
                print(f"Error loading Reddit comments for {place['name']}: {e}")

        entry = {
            **place,
            "google_reviews": google_data['reviews'] if google_data else [],
            "reddit_comments": reddit_comments
        }

        final_output.append(entry)

    final_output = sanitize_string(final_output)

    os.makedirs("Combined Output", exist_ok=True)
    output_file = f"Combined Output/{category}_{city}_combined.json"
    with open(output_file, 'w', encoding='utf-8', errors='replace') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    print(f"\n=== Final output saved to {output_file} ===")

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    os.makedirs("Google Reviews", exist_ok=True)
    os.makedirs("Reddit Reviews", exist_ok=True)
    main()