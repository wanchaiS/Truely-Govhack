#!/usr/bin/env python3
"""
Flask API server for fact-checking database
Provides endpoints for browser extension integration
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import logging
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from database import FactCheckDatabase
from llm_service import LLMService
from models import APIFactCheckResponse, APIQueryResponse, ContextChunk
from document_processor import DocumentProcessor

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for browser extension

# Configure file upload
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), '..', 'documents')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'csv'}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize database
try:
    db = FactCheckDatabase()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    db = None

# Initialize document processor for query embeddings
try:
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        doc_processor = DocumentProcessor(api_key=api_key)
        logger.info("Document processor initialized for query embeddings")
    else:
        doc_processor = None
        logger.warning("WARNING: OpenAI API key not found - query embeddings will not work")
except Exception as e:
    logger.error(f"Failed to initialize document processor: {e}")
    doc_processor = None

# LLM service will be initialized per-request when API key is provided
# This allows clients (browser extension) to provide their own API keys

def create_llm_service(client_api_key: str = None) -> LLMService:
    """
    Create LLM service instance with client-provided API key or environment variable
    
    Args:
        client_api_key: API key provided by client (browser extension)
        
    Returns:
        LLMService instance or None if no API key available
        
    Raises:
        ValueError: If neither client API key nor environment variable is available
    """
    # Prefer client-provided API key, fallback to environment variable
    api_key = client_api_key or os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("No OpenAI API key provided. Either include 'api_key' in request or set OPENAI_API_KEY environment variable")
    
    return LLMService(api_key=api_key)

# Source URLs are now stored directly in database metadata - no separate mapping file needed

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_status(file_path, db_stats):
    """Check if a file has been processed into the database"""
    file_name = os.path.basename(file_path)
    # Simple heuristic: if we have chunks in DB and file exists, assume it's processed
    # In a real system, you'd track this more precisely
    return {
        'name': file_name,
        'size': os.path.getsize(file_path),
        'processed': db_stats['total_chunks'] > 0,  # Simplified check
        'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
    }

def generate_document_url(source_file: str, source_url: str = None) -> str:
    """
    Generate a URL to access the source document from database metadata
    
    Args:
        source_file: Name of the source file (not used anymore, kept for compatibility)
        source_url: Source URL from database metadata
        
    Returns:
        Source URL from database metadata
    """
    # Return the source URL directly from database metadata
    return source_url or ""

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Check if LLM service is available with backend API key
    llm_available = False
    try:
        backend_api_key = os.getenv('OPENAI_API_KEY')
        if backend_api_key:
            # Try to create LLM service to test availability
            test_llm = create_llm_service()
            llm_available = True
    except Exception as e:
        logger.warning(f"LLM service test failed: {e}")
        llm_available = False
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_connected": db is not None,
        "llm_service_available": llm_available
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    
    try:
        stats = db.get_collection_stats()
        return jsonify({
            "status": "success",
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/fact-check', methods=['POST'])
def fact_check():
    """
    Fact-check endpoint for browser extension
    Accepts text and returns LLM-generated fact-checking response with source context
    """
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    
    try:
        # Get request data
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' parameter"}), 400
        
        text = data.get('text', '').strip()
        if not text:
            return jsonify({"error": "Empty text provided"}), 400
        
        n_results = min(data.get('n_results', 5), 10)  # Max 10 results
        use_llm = data.get('use_llm', True)  # Allow disabling LLM
        client_api_key = data.get('api_key')  # Client-provided OpenAI API key
        
        logger.info(f"Fact-checking query: '{text[:100]}...'")
        
        # Generate OpenAI embeddings for query
        if not doc_processor:
            return jsonify({"error": "Document processor not initialized"}), 500
            
        query_embeddings = doc_processor.generate_embeddings([text])
        if not query_embeddings:
            return jsonify({"error": "Failed to generate query embeddings"}), 500
        
        # Query similar documents using embeddings
        results = db.query_similar_with_embeddings(query_embeddings[0], n_results=n_results)
        
        # Format results for context using Pydantic models
        context_chunks = []
        if results['documents'][0]:  # Check if we have results
            for i in range(len(results['documents'][0])):
                doc = results['documents'][0][i]
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                confidence = max(0, 1 - distance)  # Ensure confidence >= 0
                
                context_chunks.append(ContextChunk(
                    text=doc,
                    source_file=metadata.get('source_file', 'unknown'),
                    source=metadata.get('source_url'),  # Include source URL from metadata
                    document_url=generate_document_url(metadata.get('source_file', 'unknown'), metadata.get('source_url')),
                    chunk_index=metadata.get('chunk_index', 0),
                    confidence=round(confidence, 3),
                    distance=round(distance, 3)
                ))
        
        # Create structured API response
        api_response = APIFactCheckResponse(
            status="success",
            query=text,
            context=context_chunks,
            total_context_chunks=len(context_chunks),
            timestamp=datetime.now().isoformat()
        )
        
        # Generate LLM response if API key provided, LLM requested, and context available
        if use_llm and context_chunks and (client_api_key or os.getenv('OPENAI_API_KEY')):
            try:
                logger.info("Creating LLM service for fact-check response...")
                llm_service = create_llm_service(client_api_key)
                
                logger.info("Generating LLM fact-check response...")
                # Convert ContextChunk objects to dicts for LLM service
                context_dicts = [chunk.model_dump() for chunk in context_chunks]
                llm_result = llm_service.generate_fact_check_response(text, context_dicts)
                
                if llm_result.status == "success":
                    api_response.fact_check = llm_result.fact_check
                    api_response.llm_response = llm_result
                    logger.info("LLM fact-check response generated")
                else:
                    api_response.llm_response = llm_result
                    logger.warning(f"WARNING: LLM generation failed: {llm_result.error}")
                    
            except ValueError as e:
                logger.warning(f"WARNING: LLM service creation failed: {e}")
                api_response.message = "LLM service requires API key - add 'api_key' to request or set OPENAI_API_KEY environment variable"
            except Exception as e:
                logger.error(f"ERROR: Unexpected LLM error: {e}")
                api_response.message = f"LLM service error: {str(e)}"
        
        elif not (client_api_key or os.getenv('OPENAI_API_KEY')):
            api_response.message = "LLM service requires API key - add 'api_key' to request or set OPENAI_API_KEY environment variable"
        elif not context_chunks:
            api_response.message = "No relevant context found for fact-checking"
        
        return jsonify(api_response.model_dump())
        
    except Exception as e:
        logger.error(f"Error in fact-check endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/query', methods=['POST'])
def general_query():
    """
    General query endpoint (for Ask feature)
    Similar to fact-check but with different response format
    """
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    
    try:
        # Get request data  
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' parameter"}), 400
        
        text = data.get('text', '').strip()
        if not text:
            return jsonify({"error": "Empty text provided"}), 400
        
        n_results = min(data.get('n_results', 3), 10)  # Max 10 results
        client_api_key = data.get('api_key')  # Client-provided OpenAI API key (for future LLM features)
        
        logger.info(f"General query: '{text[:100]}...'")
        
        # Generate OpenAI embeddings for query
        if not doc_processor:
            return jsonify({"error": "Document processor not initialized"}), 500
            
        query_embeddings = doc_processor.generate_embeddings([text])
        if not query_embeddings:
            return jsonify({"error": "Failed to generate query embeddings"}), 500
        
        # Query similar documents using embeddings
        results = db.query_similar_with_embeddings(query_embeddings[0], n_results=n_results)
        
        # Format results for general query using Pydantic models
        context_chunks = []
        if results['documents'][0]:
            for i in range(len(results['documents'][0])):
                doc = results['documents'][0][i]
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                confidence = max(0, 1 - distance)
                
                if confidence > 0.1:  # Only include reasonably relevant results
                    context_chunks.append(ContextChunk(
                        text=doc,
                        source_file=metadata.get('source_file', 'unknown'),
                        source=metadata.get('source_url'),  # Include source URL from metadata
                        document_url=generate_document_url(metadata.get('source_file', 'unknown'), metadata.get('source_url')),
                        chunk_index=metadata.get('chunk_index', 0),
                        confidence=round(confidence, 3),
                        distance=round(distance, 3)
                    ))
        
        api_response = APIQueryResponse(
            status="success",
            query=text,
            context=context_chunks,
            message=f"Found {len(context_chunks)} relevant context chunks",
            timestamp=datetime.now().isoformat()
        )
        
        return jsonify(api_response.model_dump())
        
    except Exception as e:
        logger.error(f"Error in general query endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all files in the documents directory with processing status"""
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    
    try:
        docs_path = Path(app.config['UPLOAD_FOLDER'])
        docs_path.mkdir(exist_ok=True)
        
        files = []
        db_stats = db.get_collection_stats()
        
        for file_path in docs_path.glob('*'):
            if file_path.is_file() and allowed_file(file_path.name):
                file_info = get_file_status(file_path, db_stats)
                files.append(file_info)
        
        return jsonify({
            "status": "success",
            "files": files,
            "total_files": len(files),
            "database_stats": db_stats,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a file to the documents directory"""
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Get source URL from form data
        source_url = request.form.get('source_url', '').strip()
        if not source_url:
            return jsonify({"error": "Source URL is required"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "error": f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # Save file
        filename = secure_filename(file.filename)
        docs_path = Path(app.config['UPLOAD_FOLDER'])
        docs_path.mkdir(exist_ok=True)
        file_path = docs_path / filename
        
        # Check if file already exists
        if file_path.exists():
            return jsonify({"error": "File already exists"}), 409
        
        file.save(str(file_path))
        logger.info(f"File uploaded: {filename} with source URL: {source_url}")
        
        # Process the file immediately after upload
        try:
            # Initialize document processor
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                return jsonify({"error": "OpenAI API key not configured"}), 500
            
            processor = DocumentProcessor(api_key=api_key)
            
            # Process the file with source URL
            logger.info(f"Processing uploaded file: {filename}")
            chunks, metadata_list, ids = processor.process_document(str(file_path), source_url)
            
            if not chunks:
                return jsonify({"error": "No content extracted from file"}), 400
            
            # Generate embeddings and add to database
            embeddings = processor.generate_embeddings(chunks)
            db.add_document_chunks(chunks, metadata_list, ids, embeddings)
            
            logger.info(f"File uploaded and processed successfully: {filename} ({len(chunks)} chunks)")
            
            return jsonify({
                "status": "success",
                "message": "File uploaded and processed successfully",
                "filename": filename,
                "source_url": source_url,
                "chunks_created": len(chunks),
                "processed": True,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as processing_error:
            # If processing fails, still keep the uploaded file but log the error
            logger.error(f"Processing failed for {filename}: {processing_error}")
            return jsonify({
                "status": "partial_success", 
                "message": f"File uploaded but processing failed: {str(processing_error)}",
                "filename": filename,
                "source_url": source_url,
                "processed": False,
                "timestamp": datetime.now().isoformat()
            }), 500
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500

# process-file endpoint removed - processing now happens automatically during upload

@app.route('/api/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a file from both the filesystem and vector database"""
    if not db:
        return jsonify({"error": "Database not initialized"}), 500
    
    try:
        docs_path = Path(app.config['UPLOAD_FOLDER'])
        file_path = docs_path / filename
        
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        
        # First, delete from vector database
        logger.info(f"Deleting chunks for file: {filename}")
        chunks_deleted = db.delete_document_by_filename(filename)
        
        # Then delete the physical file
        file_path.unlink()
        logger.info(f"File deleted: {filename}")
        
        return jsonify({
            "status": "success",
            "message": "File deleted successfully",
            "filename": filename,
            "chunks_removed": chunks_deleted,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/clear-database', methods=['POST'])
def clear_database():
    """Clear all documents from the database"""
    try:
        if not db:
            return jsonify({"error": "Database not initialized"}), 500
            
        # Clear the ChromaDB collection
        db.clear_collection()
        logger.info("Database cleared successfully")
        
        return jsonify({
            "status": "success",
            "message": "Database cleared successfully"
        })
        
    except Exception as e:
        error_msg = f"Failed to clear database: {str(e)}"
        logger.error(f"ERROR: {error_msg}")
        return jsonify({"error": error_msg}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    """Run the Flask development server"""
    port = int(os.environ.get('PORT', 8877))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting fact-checking API server on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    if db:
        stats = db.get_collection_stats()
        logger.info(f"Database ready with {stats['total_chunks']} chunks")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == '__main__':
    main()