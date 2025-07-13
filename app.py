from flask import Flask, request, jsonify, send_from_directory
import os
import json
import threading
from build_vibe_vectorstore import main as build_vectorstore
from query_vibe import structured_query_response, load_data_and_store
import sys
import logging
from main3 import main as run_scraper_direct  # Import directly

from flask_cors import CORS

app = Flask(__name__, static_folder='../vibe-navigator-frontend/build')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
vectorstore = None
place_map = None
lock = threading.Lock()
initialized = False

def initialize_data(city, category):
    global vectorstore, place_map, initialized
    with lock:
        if not initialized:
            try:
                logger.info(f"Initializing data for {category} in {city}")
                
                # 1. Check if data already exists
                output_file = f"Combined Output/{category}_{city}_combined.json"
                if os.path.exists(output_file):
                    logger.info(f"Found existing data file: {output_file}")
                else:
                    logger.info(f"Running scraper for new data collection")
                    run_scraper_direct(city, category)
                
                # 2. Check if vectorstore needs building
                tagged_file = f"Combined Output/{category}_{city}_combined_tagged.json"
                if not os.path.exists(tagged_file):
                    logger.info(f"Building vectorstore from {output_file}")
                    build_vectorstore(output_file)
                
                # 3. Load vectorstore
                logger.info("Loading vectorstore...")
                vectorstore, place_map = load_data_and_store(city.lower(), category.lower())
                initialized = True
                logger.info("Data initialization complete")
                
            except Exception as e:
                logger.error(f"Initialization failed: {str(e)}")
                raise

@app.route('/api/search', methods=['POST'])
def search_places():
    """Search endpoint with detailed logging"""
    logger.info("Received search request")
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
        
    city = data.get('city')
    category = data.get('category')
    
    if not city or not category:
        logger.warning("Missing city or category")
        return jsonify({"error": "Both city and category are required"}), 400
    
    try:
        initialize_data(city, category)
        response = {
            "status": "success",
            "message": f"Data collected for {category} in {city}",
            "data_file": f"Combined Output/{category}_{city}_combined_tagged.json"
        }
        logger.info(f"Search completed: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/query', methods=['POST'])
def query_vibes():
    """Query endpoint"""
    if not initialized:
        return jsonify({"error": "Data not initialized. Call /api/search first"}), 400
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
        
    query = data.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
        
    try:
        with lock:
            result = structured_query_response(
                query, 
                vectorstore, 
                place_map,
                data.get('tags', [])
            )
            return jsonify(result)
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)