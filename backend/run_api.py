#!/usr/bin/env python3
"""
Easy startup script for the fact-checking API
"""

import os
import sys
from pathlib import Path

def main():
    """Run the API server with proper environment setup"""
    
    # Check if we're in the right directory
    if not Path("src/api.py").exists():
        print("❌ Please run this script from the backend directory")
        print("Current directory:", os.getcwd())
        sys.exit(1)
    
    # Check if virtual environment exists
    venv_path = Path("venv")
    if not venv_path.exists():
        print("❌ Virtual environment not found. Please run 'python setup.py' first")
        sys.exit(1)
    
    # Check if we have any data in the database
    db_path = Path("data/chroma_db")
    if not db_path.exists():
        print("⚠️ No database found. Please upload documents through the API or use the document upload feature.")
    
    print("🚀 Starting Fact-Checking API Server...")
    print("🌐 Available endpoints:")
    print("  - GET  /health      - Health check")
    print("  - GET  /stats       - Database statistics")  
    print("  - POST /fact-check  - Fact-check text")
    print("  - POST /query       - General query")
    print("")
    print("💡 Use PORT environment variable to change port (default: 8080)")
    print("💡 Example: PORT=5001 python run_api.py")
    print("")
    
    # Set default port if not specified
    port = os.environ.get('PORT', '8080')
    os.environ['PORT'] = port
    
    # Run the API server
    try:
        os.system("source venv/bin/activate && python src/api.py")
    except KeyboardInterrupt:
        print("\n👋 API server stopped")

if __name__ == "__main__":
    main()