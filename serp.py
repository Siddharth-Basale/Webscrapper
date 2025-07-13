import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
SERPAPI_API_KEY = os.getenv("SERPAPI_KEY")

def get_places_from_google_maps(city: str, category: str, max_places: int = 10):
    query = f"{category} in {city}"
    
    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "api_key": SERPAPI_API_KEY
    }

    response = requests.get("https://serpapi.com/search.json", params=params)
    
    if response.status_code != 200:
        print(f"[✗] Request failed: {response.status_code} - {response.text}")
        return []

    data = response.json()
    results = data.get("local_results", [])
    places = []

    for place in results[:max_places]:
        places.append({
            "name": place.get("title"),
            "address": place.get("address"),
            "rating": place.get("rating"),
            "reviews_count": place.get("reviews"),
            "coordinates": place.get("gps_coordinates"),
            "category": category,
            "city": city,
            "source_url": place.get("place_id"),
        })

    return places

def save_places_to_json(places, city, category):
    filename = f"output/{category.lower().replace(' ', '_')}_{city.lower().replace(' ', '_')}.json"
    os.makedirs("output", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(places, f, indent=2)
    print(f"[✓] Saved {len(places)} {category} in {city} to {filename}")


if __name__ == "__main__":
    city = "Pune"
    category = "restaurants"
    places = get_places_from_google_maps(city, category)
    print(f"Found {len(places)} places:")
    for p in places:
        print(f"- {p['name']}")