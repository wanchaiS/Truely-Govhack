# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Architecture

This is a ChromaDB-based fact-checking database backend implementing RAG (Retrieval-Augmented Generation). The system consists of three main components:

1. **DocumentProcessor** (`src/document_processor.py`) - Handles document ingestion, text extraction, chunking, and embedding generation
2. **FactCheckDatabase** (`src/database.py`) - Manages ChromaDB operations, similarity queries, and collection management
3. **LLMService** (`src/llm_service.py`) - Integrates OpenAI GPT models for generating fact-checking responses from retrieved context

### Document Processing Pipeline
- Supports multiple formats: PDF, DOCX, TXT, CSV
- Text chunking: 800-character chunks with 100-character overlap for context preservation  
- Embeddings: Sentence-BERT model `all-MiniLM-L6-v2` (configurable)
- Metadata tracking: source file, chunk index, processing timestamp, file hash

### Database Architecture
- ChromaDB persistent client at `./data/chroma_db`
- Collection: `fact_check_documents` with embedding-based similarity search
- Automatic vectorization with configurable embedding models

### LLM Integration
- OpenAI GPT integration for fact-checking response generation
- Uses retrieved context chunks as evidence for LLM analysis
- Structured prompt engineering for consistent fact-checking format
- Fallback mode when LLM service is unavailable

## Essential Commands

### Initial Setup
```bash
python setup.py  # Creates venv, installs dependencies, creates directories

# Environment Configuration
cp .env.example .env
# Edit .env file and add your OpenAI API key
```

### Environment Activation
```bash
# macOS/Linux
source venv/bin/activate

# Windows  
venv\Scripts\activate
```

### Document Processing
```bash
# Process all documents in documents/ folder
python src/document_processor.py

# Process specific directory
python src/document_processor.py --input_dir /path/to/documents

# Clear database and reprocess
python src/document_processor.py --clear_db

# Use different embedding model
python src/document_processor.py --embedding_model "all-mpnet-base-v2"
```

### Database Operations
```bash
# Test database connection and run sample queries
python src/database.py

# Test LLM service connection
python src/llm_service.py

# Interactive query example
python -c "
from src.database import FactCheckDatabase
db = FactCheckDatabase()
results = db.query_similar('Your question here', n_results=3)
print(results)
"
```

### API Server
```bash
# Start the Flask API server
python src/api.py

# The API will be available at http://localhost:5000
# Endpoints:
# - GET /health - Health check with LLM service status
# - POST /fact-check - Fact-checking with LLM-generated responses
# - POST /query - General query endpoint
```

## Key Configuration Parameters

### DocumentProcessor
- `chunk_size = 800` - Characters per text chunk
- `overlap = 100` - Overlap between chunks  
- `embedding_model = "all-MiniLM-L6-v2"` - Default Sentence-BERT model

### FactCheckDatabase  
- `db_path = "./data/chroma_db"` - ChromaDB storage location
- `collection_name = "fact_check_documents"` - Main collection name

### LLMService
- `model = "gpt-3.5-turbo"` - Default OpenAI model
- `temperature = 0.2` - Low temperature for consistent fact-checking
- `max_tokens = 1000` - Maximum response length

## Development Workflow

1. **Setup Environment**: Copy `.env.example` to `.env` and add OpenAI API key
2. **Add Documents**: Place source documents in `documents/` folder
3. **Process Documents**: Run document processor to populate database
4. **Test Services**: Run database.py and llm_service.py tests
5. **Start API**: Run api.py to start the Flask server
6. **Query Testing**: Use API endpoints or test functions
7. **Iterate**: Clear database and reprocess as needed during development

## Embedding Models

Default: `all-MiniLM-L6-v2` (fast, good quality, 384 dimensions)

Alternatives:
- `all-mpnet-base-v2` - Higher quality, slower, 768 dimensions
- `all-distilroberta-v1` - Balanced performance
- `paraphrase-multilingual-MiniLM-L12-v2` - Multilingual support

## File Structure Insights

- `documents/` - Document ingestion directory (user-provided files)
- `data/chroma_db/` - Persistent ChromaDB storage (auto-created)
- `logs/` - Application logs directory
- `sample_facts.txt` - Test data covering science, health, climate, technology, history, and space facts

## Common Issues

**"No module named 'chromadb'"**: Virtual environment not activated or setup.py not run
**"No supported files found"**: Check file extensions (.txt, .pdf, .docx, .csv) and permissions
**Memory issues**: Reduce chunk_size or use smaller embedding model
**Slow processing**: Use `all-MiniLM-L6-v2` model and reduce chunk overlap

## Query Results Structure
```python
results = {
    'documents': [["chunk1_text", "chunk2_text", ...]],
    'metadatas': [[{metadata1}, {metadata2}, ...]],  
    'distances': [[0.1, 0.3, ...]]  # Lower = more similar
}
```

## Browser Extension Integration
This backend is designed to work with a browser extension that sends fact-checking queries. The system now provides:

1. **Context Retrieval**: Similarity search finds relevant document chunks
2. **LLM Analysis**: OpenAI GPT analyzes context and generates fact-checking responses
3. **Structured Output**: Classifications (SUPPORTED/CONTRADICTED/INSUFFICIENT/MIXED) with reasoning
4. **Source Attribution**: Responses include citations to source documents
5. **Graceful Fallback**: Returns raw context when LLM service is unavailable

## API Response Format

### Fact-Check Endpoint (`POST /fact-check`)
```json
{
  "status": "success",
  "query": "The Earth is flat",
  "context": [
    {
      "text": "The Earth is approximately spherical...",
      "source_file": "science_facts.txt",
      "confidence": 0.95
    }
  ],
  "fact_check": {
    "response": "**Classification:** CONTRADICTED\n**Analysis:** The query is contradicted by scientific evidence...",
    "model_used": "gpt-3.5-turbo",
    "token_usage": {"total_tokens": 150}
  }
}
```