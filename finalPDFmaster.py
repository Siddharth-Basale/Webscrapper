import os
import time
import requests
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
import re

# === Utility Functions ===
def clean_text(text: str) -> str:
    """Clean text by removing lines with excessive symbols/whitespace"""
    lines = text.splitlines()
    cleaned_lines = [line for line in lines if not re.match(r'^[_\W\s]{5,}$', line.strip())]
    return "\n".join(cleaned_lines).strip()

def configure_environment(google_api_key: str = None, groq_api_key: str = None):
    """Configure API keys from environment or parameters"""
    if not google_api_key:
        google_api_key = os.getenv("GOOGLE_API_KEY")
    if not groq_api_key:
        groq_api_key = os.getenv("GROQ_API_KEY")
    
    genai.configure(api_key=google_api_key)
    return google_api_key, groq_api_key

# === Document Processing Functions ===
def load_and_chunk_pdf(pdf_path: str, chunk_size: int = 800, chunk_overlap: int = 200):
    """Load PDF and split into chunks"""
    print("Loading and chunking PDF...")
    loader = PyPDFLoader(pdf_path)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap
    )
    chunks = loader.load_and_split(text_splitter)
    
    # Clean each chunk
    for chunk in chunks:
        chunk.page_content = clean_text(chunk.page_content)
    
    print(f"Created {len(chunks)} text chunks")
    return chunks

# === Vector Store Functions ===
def create_embeddings(chunks, model_name: str = "models/embedding-001"):
    """Create embeddings using Gemini model"""
    print("Creating embeddings...")
    embedding_model = GoogleGenerativeAIEmbeddings(model=model_name)
    return embedding_model

def create_vector_store(chunks, embedding_model):
    """Create and return FAISS vector store"""
    print("Creating vector store...")
    vectorstore = FAISS.from_documents(chunks, embedding_model)
    print(f"Vector store created with {vectorstore.index.ntotal} embeddings")
    return vectorstore

def save_vector_store(vectorstore, save_path: str):
    """Save vector store to disk"""
    vectorstore.save_local(save_path)
    print(f"Vector store saved locally at {save_path}")

def load_vector_store(load_path: str, embedding_model):
    """Load vector store from disk"""
    vectorstore = FAISS.load_local(load_path, embedding_model, allow_dangerous_deserialization=True)
    print(f"Loaded vector store with {vectorstore.index.ntotal} embeddings")
    return vectorstore

# === LLM Functions ===
def call_groq_llm(prompt: str, groq_api_key: str, model: str = "deepseek-r1-distill-llama-70b"):
    """Call Groq LLM API"""
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant. Answer based only on provided context."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                           json=payload, 
                           headers=headers)
    if response.status_code != 200:
        raise Exception(f"Groq LLM error: {response.status_code} - {response.text}")
    
    return response.json()["choices"][0]["message"]["content"]

def expand_query_with_llm(query: str, groq_api_key: str):
    """Expand short queries using LLM"""
    prompt = f"""You are an expert assistant. The user query below is too short for accurate search.
So please you answer that query in 10 lines 

Query: {query}

Expanded version:"""
    return call_groq_llm(prompt, groq_api_key)

# === QA Pipeline Functions ===
def retrieve_relevant_chunks(vectorstore, query: str, k: int = 5, fetch_k: int = 25):
    """Retrieve relevant document chunks using similarity search"""
    similar_docs = vectorstore.max_marginal_relevance_search(
        query=query, 
        k=k, 
        fetch_k=fetch_k
    )
    
    if not similar_docs:
        return None
    
    print("\n--- Retrieved Chunks ---")
    for i, doc in enumerate(similar_docs, 1):
        print(f"\nChunk {i}:\n{doc.page_content}")
    print("\n--- End of Retrieved Chunks ---")
    
    return similar_docs

def generate_answer(question: str, context: str, groq_api_key: str):
    """Generate answer using LLM with provided context"""
    prompt = f"""You are a highly knowledgeable AI assistant.

Answer the following question based ONLY on the context provided below. Be as detailed, thorough, and explanatory as possible. Cover all relevant aspects, examples, implications, and background knowledge that can be inferred from the context.

If the context includes multiple points, explain each one clearly. Use structured paragraphs if needed.

---
Context:
{context}

---
Question: {question}

If the answer is not in the context, respond strictly with "I don't know."
"""
    return call_groq_llm(prompt, groq_api_key)

def answer_question(question: str, vectorstore, groq_api_key: str):
    """Complete QA pipeline"""
    # Step 1: Expand the query
    expanded_query = expand_query_with_llm(question, groq_api_key)
    print("\nExpanded Query:\n", expanded_query)

    # Step 2: Semantic search on expanded query
    similar_docs = retrieve_relevant_chunks(vectorstore, expanded_query)
    if not similar_docs:
        return "No relevant context found."

    context = "\n\n".join([doc.page_content for doc in similar_docs])
    
    # Step 3: Generate answer
    return generate_answer(question, context, groq_api_key)

# === Main Execution ===
def main():
    # Configuration
    PDF_PATH = "book2.pdf"
    VECTOR_STORE_PATH = "book_vectorstore"
    GROQ_MODEL = "deepseek-r1-distill-llama-70b"
    
    # Step 1: Setup environment
    google_api_key, groq_api_key = configure_environment()
    
    # Step 2: Process PDF (only needed first time)
    if not os.path.exists(VECTOR_STORE_PATH):
        chunks = load_and_chunk_pdf(PDF_PATH)
        embedding_model = create_embeddings(chunks)
        vectorstore = create_vector_store(chunks, embedding_model)
        save_vector_store(vectorstore, VECTOR_STORE_PATH)
    else:
        embedding_model = create_embeddings([])  # Empty chunks just to get model
        vectorstore = load_vector_store(VECTOR_STORE_PATH, embedding_model)
    
    # Step 3: Ask question
    question = "give me synopsis of classical AI"
    print("\nGenerating answer using Groq LLM...")
    answer = answer_question(question, vectorstore, groq_api_key)
    
    # Display results
    print("\n" + "="*50)
    print("QUESTION:", question)
    print("="*50)
    print("ANSWER:", answer)
    print("="*50)

if __name__ == "__main__":
    main()