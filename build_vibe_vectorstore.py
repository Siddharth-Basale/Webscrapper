import os
import json
import re
import google.generativeai as genai
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from finalPDFmaster import (
    clean_text,
    create_embeddings,
    create_vector_store,
    save_vector_store,
    configure_environment
)

# === Tag Classification ===
def extract_vibe_tags(name, city, reviews):
    combined_text = "\n".join([r["text"] for r in reviews])

    prompt = f"""
You are a vibe classifier for city locations such as cafes, restaurants, gyms, etc.

Given the following reviews for a place called "{name}" in {city}, extract 3–6 vibe-related tags that best describe the experience of the location.

Use lowercase, dash-separated words.

Only choose tags from a consistent predefined set that applies across all categories (e.g., cafes, restaurants, gyms).

Examples of valid tags: "budget-friendly", "aesthetic", "lively", "quiet", "family-friendly", "cozy", "spacious", "premium", "crowded", "peaceful", "healthy-options", "music", "zumba", "yoga", "late-night", "outdoor-seating", "fast-service", "pet-friendly", "romantic", "group-friendly", "modern", "traditional", "luxury", "noisy", "clean".

Only output the tags in the form of a JSON list.

Reviews:
{combined_text}
"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    raw = response.text.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return tags
    except Exception as e:
        print(f"[!] Failed to parse tags for {name}. Raw:\n{response.text}")
    return []

# === Step 1: Load JSON and classify ===
def load_reviews_and_tag(json_path, save_tagged_json=True):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    for place in data:
        name = place["name"]
        city = place.get("city", "unknown city")

        google_reviews = place.get("google_reviews", [])
        reddit_reviews = [
            {"text": c["text"], "author": c.get("author", "Anonymous")}
            for thread in place.get("reddit_comments", [])
            for c in thread.get("all_comments", [])
        ]
        all_reviews = google_reviews + reddit_reviews

        # 🔹 Get tags from Gemini
        tags = extract_vibe_tags(name, city, all_reviews)
        place["tags"] = tags

        # 🔹 Create FAISS documents
        for r in all_reviews:
            docs.append(Document(
                page_content=r["text"],
                metadata={
                    "source": name,
                    "city": city,
                    "tags": tags,
                    "author": r.get("author", "Anonymous"),
                    "address": place.get("address"),
                    "rating": place.get("rating"),
                    "reviews_count": place.get("reviews_count"),
                    "coordinates": place.get("coordinates"),
                    "url": f"https://www.google.com/maps/place/?q=place_id:{place.get('source_url')}"
                }
            ))

    # 🔹 Save the updated JSON
    if save_tagged_json:
        tagged_path = os.path.splitext(json_path)[0] + "_tagged.json"
        with open(tagged_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[💾] Tagged JSON saved to {tagged_path}")

    return docs

# === Step 2: Chunking ===
def chunk_documents(documents, chunk_size=600, chunk_overlap=150):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(documents)

    for chunk in chunks:
        chunk.page_content = clean_text(chunk.page_content)

    print(f"[✓] Prepared {len(chunks)} chunks")
    return chunks

# === Main ===
def main(input_path=None):
    VECTOR_STORE_PATH = "vibe_vectorstore"
    JSON_INPUT_PATH = input_path if input_path else r"C:\Users\Lenovo\Desktop\Jinvaani\solution\Combined Output\gym_pune_combined.json"
    
    configure_environment()
    documents = load_reviews_and_tag(JSON_INPUT_PATH)
    chunks = chunk_documents(documents)
    embedding_model = create_embeddings(chunks)
    vectorstore = create_vector_store(chunks, embedding_model)
    save_vector_store(vectorstore, VECTOR_STORE_PATH)

if __name__ == "__main__":
    main()
