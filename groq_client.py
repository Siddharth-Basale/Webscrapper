# groq_client.py
from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def groq_chat_completion(system_prompt, user_prompt, model="llama-3.3-70b-versatile"):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {str(e)}")
        return None
    


