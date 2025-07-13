from flask import Flask, request, jsonify
import os
import json
from multiprocessing import Pool
from serp import get_places_from_google_maps, save_places_to_json
from google_maps_scraper import scrape_google_maps_reviews
from reddit_scraper import run_pipeline
from groq_client import groq_chat_completion
from quality_check import validate_summary_quality
from rag_engine import create_review_embeddings, find_most_relevant_reviews
from vibe_analyzer import generate_detailed_vibe_profile
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask_cors import CORS


app = Flask(__name__)
CORS(app)
# Configuration constants
MAX_PLACES = 3
MAX_REVIEWS = 15
MAX_WORKERS = 2  # Reduced to prevent resource conflicts
REQUEST_DELAY = 2  # Seconds between requests


def load_reddit_comments(place_name, city, category):
    try:
        # Look for files matching the pattern: filtered_<place>_<city>_*.json
        place_slug = place_name.lower().replace(' ', '_')
        city_slug = city.lower().replace(' ', '_')
        category_slug = category.lower().replace(' ', '_')

        pattern = f"filtered_{place_slug}_{city_slug}_*.json"
        reddit_files = [f for f in os.listdir("Reddit Reviews") if f.startswith(
            f"filtered_{place_slug}_{city_slug}")]

        if not reddit_files:
            # Try more generic pattern if specific one not found
            reddit_files = [f for f in os.listdir("Reddit Reviews")
                            if f.startswith("filtered_reddit_comments")]

        if reddit_files:
            latest_file = max(reddit_files)
            with open(f"Reddit Reviews/{latest_file}", 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading Reddit comments for {place_name}: {e}")
    return []


def scrape_google_reviews(place):
    """Wrapper function for Google Maps scraping with better error handling"""
    try:
        print(f"Starting Google Maps scraping for: {place['name']}")
        output_file = f"Google Reviews/reviews_{place['name'].replace(' ', '_')}.json"

        # Add delay between requests to prevent rate limiting
        time.sleep(REQUEST_DELAY)

        reviews = scrape_google_maps_reviews(
            place['source_url'],
            max_reviews=MAX_REVIEWS,
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


def scrape_reddit_single(args):
    """Wrapper function for Reddit scraping for a single place"""
    place, city = args
    try:
        print(f"Starting Reddit scraping for: {place['name']}")
        query = f"{place['name']} {city}"

        # Add delay between requests
        time.sleep(REQUEST_DELAY)

        run_pipeline(query)
        print(f"Completed Reddit scraping for: {place['name']}")
        return {"name": place['name'], "success": True}
    except Exception as e:
        print(f"Error in Reddit scraping for {place['name']}: {e}")
        return {"name": place['name'], "success": False, "error": str(e)}


def process_location_data(place, city, category):
    """Process a single location with error handling"""
    try:
        # Only create embeddings if we have reviews
        if place.get('google_reviews') or place.get('reddit_comments'):
            texts, embeddings = create_review_embeddings(place)
            place['review_embeddings'] = embeddings.tolist()

            # Generate vibe profile if we have reviews
            vibe_profile = generate_detailed_vibe_profile(place)
            if vibe_profile:
                try:
                    place['vibe_profile'] = json.loads(vibe_profile)
                    if place['vibe_profile'] and 'summary' in place['vibe_profile']:
                        place['vibe_profile'] = validate_summary_quality(
                            place['vibe_profile'])
                except json.JSONDecodeError:
                    place['vibe_profile'] = {
                        "error": "Could not parse vibe profile"}

        return place
    except Exception as e:
        print(f"Error processing location {place['name']}: {e}")
        place['processing_error'] = str(e)
        return place


@app.route('/scrape', methods=['GET'])
def scrape():
    city = request.args.get('city', '').strip()
    category = request.args.get('category', '').strip()

    if not city or not category:
        return jsonify({"error": "Both city and category parameters are required"}), 400

    print(f"\nStarting data collection for {category} in {city}...\n")

    # Step 1: Get places from SERP API
    print("=== Step 1: Fetching places ===")
    places = get_places_from_google_maps(city, category, max_places=MAX_PLACES)
    print(f"Found {len(places)} places.")

    if not places:
        return jsonify({"message": "No places found", "places": []})

    save_places_to_json(places, city, category)

    # Step 2: Google Maps scraping with ThreadPool
    print("\n=== Step 2: Google Maps reviews scraping ===")
    google_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scrape_google_reviews, place) for place in places]
        for future in as_completed(futures):
            google_results.append(future.result())

    # Step 3: Reddit scraping with ThreadPool
    print("\n=== Step 3: Reddit scraping ===")
    reddit_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scrape_reddit_single, (place, city)) for place in places]
        for future in as_completed(futures):
            reddit_results.append(future.result())

    # Combine all data
    final_output = []
    for place in places:
        google_data = next(
            (r for r in google_results if r['name'] == place['name'] and r['success']), None)

        entry = {
            **place,
            "google_reviews": google_data['reviews'] if google_data else [],
            "reddit_comments": load_reddit_comments(place['name'], city, category)
        }

        # Process with additional features (including vibe analysis)
        processed_entry = process_location_data(entry, city, category)
        final_output.append(processed_entry)

    # Save final output
    os.makedirs("Combined Output", exist_ok=True)
    output_file = f"Combined Output/{category}_{city}_combined.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    print(f"\n=== Final output saved to {output_file} ===")
    return jsonify(final_output)


@app.route('/query_reviews', methods=['POST'])
def query_reviews():
    data = request.get_json()
    location_name = data.get('location_name')
    query = data.get('query')
    city = data.get('city')
    category = data.get('category')

    if not all([location_name, query, city, category]):
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        filename = f"Combined Output/{category}_{city}_combined.json"
        with open(filename, 'r', encoding='utf-8') as f:
            locations = json.load(f)
    except FileNotFoundError:
        return jsonify({"error": "Location data not found. Please scrape first."}), 404

    location = next(
        (loc for loc in locations if loc['name'] == location_name), None)
    if not location:
        return jsonify({"error": "Location not found"}), 404

    try:
        # Get all reviews and comments with their metadata
        all_reviews = []
        
        # Add Google reviews with metadata
        for review in location.get('google_reviews', []):
            all_reviews.append({
                "text": review['text'],
                "source": "google",
                "author": review.get('author', 'Anonymous'),
                "rating": review.get('rating', None),
                "time": review.get('time', None),
                "url": location.get('source_url', '')
            })
        
        # Add Reddit comments with metadata
        for thread in location.get('reddit_comments', []):
            for comment in thread.get('filtered_comments', []):
                all_reviews.append({
                    "text": comment['text'],
                    "source": "reddit",
                    "author": comment.get('author', 'Anonymous'),
                    "subreddit": thread.get('subreddit', ''),
                    "url": f"https://reddit.com{comment.get('permalink', '')}",
                    "score": comment.get('score', 0)
                })

        # Generate a detailed answer using Groq
        system_prompt = """You're a location expert. Analyze the provided reviews and answer the user's question in detail.
        Include specific review excerpts with [citation] markers. Provide links to original sources when available."""
        
        user_prompt = f"""Question: {query}
        
        About: {location_name} in {city} ({category})
        
        Reviews:
        {json.dumps(all_reviews[:15], indent=2)}
        
        Provide a detailed answer with citations and links:"""
        
        answer = groq_chat_completion(system_prompt, user_prompt)
        
        return jsonify({
            "location": location_name,
            "query": query,
            "answer": answer,
            "source_reviews": all_reviews[:5]  # Include some source reviews for reference
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/vibes', methods=['GET'])
def get_vibe_cards():
    city = request.args.get('city', '').strip()
    category = request.args.get('category', '').strip()

    if not city or not category:
        return jsonify({'error': 'City and category are required'}), 400

    output_path = f"output/{category.lower().replace(' ', '_')}_{city.lower().replace(' ', '_')}.json"
    if not os.path.exists(output_path):
        return jsonify({'error': 'No processed data found for this query'}), 404

    with open(output_path, 'r', encoding='utf-8') as f:
        places = json.load(f)

    results = []
    for place in places:
        vibe = place.get('vibe_profile', {})
        if not vibe or 'summary' not in vibe:
            continue

        card = {
            "name": place.get("name"),
            "address": place.get("address"),
            "rating": place.get("rating"),
            "coordinates": place.get("coordinates"),
            "tags": vibe.get("tags", []),
            "summary": vibe.get("summary", "No summary available"),
            "persona": vibe.get("persona", ""),
            "pro_tip": vibe.get("pro_tip", ""),
            "mood_emoji": "☕🌿🎶🔥" if "cafe" in category.lower() else "🌳🧘📷",  # Example
            "citations": extract_citations(place),
            "quality_score": vibe.get("quality_score", None)
        }
        results.append(card)

    return jsonify({
        "city": city,
        "category": category,
        "count": len(results),
        "places": results
    })


def extract_citations(place):
    """Pull top citations from Google and Reddit sources"""
    citations = []
    for r in place.get("google_reviews", [])[:2]:
        citations.append({
            "source": "google",
            "text": r.get("text", ""),
            "author": r.get("author", ""),
            "time": r.get("time", "")
        })

    for thread in place.get("reddit_comments", [])[:1]:
        for c in thread.get("filtered_comments", [])[:1]:
            citations.append({
                "source": "reddit",
                "text": c.get("text", "")
            })
    return citations


if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("output", exist_ok=True)
    os.makedirs("Google Reviews", exist_ok=True)
    os.makedirs("Reddit Reviews", exist_ok=True)
    os.makedirs("Combined Output", exist_ok=True)

    # Run the Flask app
    app.run(debug=True, threaded=True)
