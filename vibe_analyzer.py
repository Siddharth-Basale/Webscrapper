from groq_client import groq_chat_completion 



def generate_detailed_vibe_profile(location_data):
    # Google reviews
    reviews = "\n".join([f"⭐ {r['text']}" for r in location_data.get("google_reviews", [])[:8]])
    
    # Reddit comments with better error handling
    reddit_comments = []
    for thread in location_data.get("reddit_comments", []):
        for comment in thread.get("filtered_comments", []):
            if isinstance(comment, dict) and 'text' in comment:
                reddit_comments.append(f"💬 {comment['text']}")
    
    reddit_text = "\n".join(reddit_comments[:5]) if reddit_comments else "No Reddit discussions found"
    
    prompt = f"""
    **Location**: {location_data['name']} | **Type**: {location_data['category']}
    
    **Recent Reviews**:
    {reviews}
    
    **Reddit Discussions**:
    {reddit_text}
    
    Analyze this location's vibe considering:
    1. Atmosphere descriptors (cozy, lively, etc.)
    2. Typical visitor demographics
    3. Unique selling points
    4. Best time to visit
    5. Potential drawbacks
    """
    
    system_prompt = """You're a vibe sommelier. Create a rich profile including:
    - 3-paragraph narrative summary with emoji highlights 🎯
    - 5-7 vibe tags (ranked by relevance)
    - Ideal visitor persona
    - "Pro Tip" based on reviews
    Format as JSON with keys: summary, tags, persona, pro_tip"""
    
    return groq_chat_completion(system_prompt, prompt)