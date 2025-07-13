import os
import json
import time
from collections import defaultdict
import google.generativeai as genai
from finalPDFmaster import (
    configure_environment,
    create_embeddings,
    load_vector_store
)

def load_data_and_store(city, category):
    configure_environment()
    embedding_model = create_embeddings([])
    vectorstore = load_vector_store("vibe_vectorstore", embedding_model)

    tagged_file = f"Combined Output/{category}_{city}_combined_tagged.json"
    with open(tagged_file, "r", encoding="utf-8") as f:
        place_data = json.load(f)

    place_map = {place["name"]: place for place in place_data}
    return vectorstore, place_map

def group_docs_by_place(docs):
    place_reviews = defaultdict(list)
    for doc in docs:
        place_name = doc.metadata.get("source")
        place_reviews[place_name].append(doc)
    return place_reviews

def build_prompt_for_place(place, reviews, user_query):
    # Separate Google and Reddit reviews
    google_reviews = []
    reddit_reviews = []
    
    for doc in reviews:
        if "reddit.com" in str(doc.metadata.get("url", "")):
            reddit_reviews.append(doc)
        else:
            google_reviews.append(doc)

    review_blocks = {
        "google": "\n".join([
            f"- \"{doc.page_content.replace('\n', ' ').strip()}\""
            for doc in google_reviews[:5]  # Limit to 5 reviews per source
        ]),
        "reddit": "\n".join([
            f"- \"{doc.page_content.replace('\n', ' ').strip()}\" (from: {doc.metadata.get('url', 'Reddit')}"
            for doc in reddit_reviews[:5]  # Limit to 5 comments
        ])
    }

    prompt = f"""
Analyze the following place based on user reviews and provide a comprehensive response in JSON format.

Place: {place['name']}
Location: {place['address']}
User Query: "{user_query}"

=== REVIEW SUMMARY ===
Google Reviews:
{review_blocks['google']}

Reddit Comments:
{review_blocks['reddit']}

=== OUTPUT FORMAT ===
{{
  "name": "{place['name']}",
  "address": "{place['address']}",
  "rating": {place.get('rating', 'null')},
  "review_count": {place.get('reviews_count', 'null')},
  "tags": {json.dumps(place.get('tags', []))},
  "location": {{
    "latitude": {place['coordinates']['latitude']},
    "longitude": {place['coordinates']['longitude']}
  }},
  "links": {{
    "google_maps": "https://www.google.com/maps/place/?q=place_id:{place.get('source_url', '')}",
    "reddit_threads": {json.dumps([thread['url'] for thread in place.get('reddit_comments', [])][:3])}
  }},
  "summary": "A concise summary of the place's vibe based on reviews...",
  "key_features": [
    "List 3-5 most notable features",
    "Focus on aspects relevant to user query"
  ]
}}
"""
    return prompt

def generate_structured_output(prompt, max_retries=3):
    model = genai.GenerativeModel("gemini-2.5-flash")  # Using the more available model
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            
            # Clean up the response
            if raw.startswith("```"):
                raw = raw[raw.find('{'):raw.rfind('}')+1]
            
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Try to manually extract JSON if parsing fails
                try:
                    start = raw.find('{')
                    end = raw.rfind('}') + 1
                    return json.loads(raw[start:end])
                except:
                    print(f"[!] Attempt {attempt + 1}: Failed to parse response, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
        except Exception as e:
            print(f"[!] Attempt {attempt + 1}: Error generating content - {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                raise

    return {"error": "Could not generate valid response after retries"}

def structured_query_response(query, vectorstore, place_map, required_tags=None):
    print("\n[🔍] Searching relevant reviews...")
    all_docs = vectorstore.similarity_search(query, k=15)  # Reduced from 25 to 15

    if required_tags:
        required_tags = set(tag.strip().lower() for tag in required_tags)
        all_docs = [
            doc for doc in all_docs
            if required_tags.intersection(set(doc.metadata.get("tags", [])))
        ]
        print(f"[⚙️] Filtered with tags: {required_tags}, {len(all_docs)} docs remain")

    grouped = group_docs_by_place(all_docs)
    if not grouped:
        return {"error": "No relevant places found."}

    best_place_name = next(iter(grouped))
    reviews = grouped[best_place_name]
    place = place_map.get(best_place_name)

    if not place:
        return {"error": f"Details for place '{best_place_name}' not found."}

    prompt = build_prompt_for_place(place, reviews, query)
    return generate_structured_output(prompt)

def main():
    vectorstore, place_map = load_data_and_store()

    query = input("Ask about a place (e.g., 'Suggest a yoga-friendly gym in Pune'):\n> ").strip()
    tags_input = input("Optional tags to filter? (comma separated):\n> ").strip()
    tags = [t.strip() for t in tags_input.split(",")] if tags_input else None

    try:
        result = structured_query_response(query, vectorstore, place_map, tags)
        print("\n[🧾 Comprehensive Recommendation]\n")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n[❌ Error] Failed to generate recommendation: {str(e)}")
        print("Possible solutions:")
        print("- Check your Gemini API quota and billing status")
        print("- Try again later when API limits reset")
        print("- Reduce the number of documents retrieved (currently 15)")

if __name__ == "__main__":
    main()