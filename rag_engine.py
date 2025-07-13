# rag_engine.py
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

def create_review_embeddings(location):
    texts = [r['text'] for r in location['google_reviews']] + \
           [c['text'] for thread in location['reddit_comments'] 
            for c in thread['filtered_comments']]
    
    embeddings = model.encode(texts)
    return texts, embeddings

def find_most_relevant_reviews(query, texts, embeddings, top_k=3):
    query_embedding = model.encode(query)
    similarities = np.dot(embeddings, query_embedding)
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    return [texts[i] for i in top_indices]


def create_review_embeddings(location):
    # Get Google reviews
    google_texts = [r['text'] for r in location.get('google_reviews', [])]
    
    # Get Reddit comments (with proper nested structure handling)
    reddit_texts = []
    for thread in location.get('reddit_comments', []):
        for comment in thread.get('filtered_comments', []):
            if isinstance(comment, dict) and 'text' in comment:
                reddit_texts.append(comment['text'])
    
    texts = google_texts + reddit_texts
    
    if not texts:
        return [], np.array([])  # Return empty if no texts
    
    embeddings = model.encode(texts)
    return texts, embeddings