"""
Document processing pipeline for fact-checking database
Handles multiple document formats and creates embeddings for ChromaDB
"""

import os
import re
import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import hashlib
from datetime import datetime

# Document processing imports
import PyPDF2
from docx import Document
import pandas as pd
from tqdm import tqdm

# OpenAI for embeddings
import openai
from openai import OpenAI

# Database
from database import FactCheckDatabase


class DocumentProcessor:
    def __init__(self, api_key: str = None, embedding_model: str = "text-embedding-3-small"):
        """
        Initialize document processor with OpenAI embeddings
        
        Args:
            api_key: OpenAI API key
            embedding_model: OpenAI embedding model name
        """
        self.embedding_model_name = embedding_model
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError("OpenAI API key required. Provide api_key parameter or set OPENAI_API_KEY environment variable")
        
        print(f"Using OpenAI embedding model: {embedding_model}")
        self.client = OpenAI(api_key=self.api_key)
        print("OpenAI client initialized successfully")
        
        # Supported file extensions
        self.supported_formats = {'.txt', '.pdf', '.docx', '.csv'}
    
    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extract text from various file formats
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text content
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.txt':
                return self._extract_from_txt(file_path)
            elif extension == '.pdf':
                return self._extract_from_pdf(file_path)
            elif extension == '.docx':
                return self._extract_from_docx(file_path)
            elif extension == '.csv':
                return self._extract_from_csv(file_path)
            else:
                print(f"WARNING: Unsupported file format: {extension}")
                return ""
                
        except Exception as e:
            print(f"ERROR: Error processing {file_path}: {e}")
            return ""
    
    def _extract_from_txt(self, file_path: Path) -> str:
        """Extract text from TXT file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _extract_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        text = ""
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def _extract_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    
    def _extract_from_csv(self, file_path: Path) -> str:
        """Extract text from CSV file (converts to readable format)"""
        df = pd.read_csv(file_path)
        # Convert DataFrame to a readable text format
        text = f"Data from {file_path.name}:\n\n"
        text += df.to_string(index=False)
        return text
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:()\-]', '', text)
        
        return text
    
    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks for better context preservation
        
        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings in the last 100 characters
                last_part = text[end-100:end]
                sentence_end = max(
                    last_part.rfind('.'),
                    last_part.rfind('!'),
                    last_part.rfind('?')
                )
                
                if sentence_end != -1:
                    end = end - 100 + sentence_end + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts using OpenAI API
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            # OpenAI API has a limit on batch size, so we process in batches
            embeddings = []
            batch_size = 100  # Adjust based on OpenAI limits
            
            for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
                batch = texts[i:i + batch_size]
                
                response = self.client.embeddings.create(
                    model=self.embedding_model_name,
                    input=batch
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
            
            print(f"Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            print(f"ERROR: Error generating embeddings: {e}")
            raise
    
    def process_document(self, file_path: str, source_url: str = "") -> Tuple[List[str], List[Dict], List[str]]:
        """
        Process a single document into chunks with metadata
        
        Args:
            file_path: Path to document file
            source_url: Source URL for the document (stored in metadata)
            
        Returns:
            Tuple of (chunks, metadata_list, ids)
        """
        file_path = Path(file_path)
        print(f"Processing: {file_path.name}")
        
        # Extract text
        raw_text = self.extract_text_from_file(file_path)
        if not raw_text:
            print(f"WARNING: No text extracted from {file_path.name}")
            return [], [], []
        
        # Clean text
        clean_text = self.clean_text(raw_text)
        
        # Create chunks
        chunks = self.chunk_text(clean_text)
        print(f"  Created {len(chunks)} chunks")
        
        # Generate metadata for each chunk
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        metadata_list = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{file_path.stem}_{file_hash}_{i:04d}"
            metadata = {
                "source_file": file_path.name,
                "source_path": str(file_path),
                "source_url": source_url or "",  # Ensure never None - use empty string as fallback
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_type": file_path.suffix,
                "processed_at": datetime.now().isoformat(),
                "chunk_length": len(chunk),
                "file_hash": file_hash
            }
            
            metadata_list.append(metadata)
            ids.append(chunk_id)
        
        return chunks, metadata_list, ids
    
    def process_directory(self, input_dir: str, db: FactCheckDatabase) -> Dict:
        """
        Process all supported documents in a directory
        
        Args:
            input_dir: Directory containing documents
            db: Database instance to store processed chunks
            
        Returns:
            Processing statistics
        """
        input_dir = Path(input_dir)
        
        if not input_dir.exists():
            print(f"ERROR: Directory not found: {input_dir}")
            return {"error": "Directory not found"}
        
        # Find all supported files
        files_to_process = []
        for ext in self.supported_formats:
            files_to_process.extend(input_dir.glob(f"*{ext}"))
        
        if not files_to_process:
            print(f"WARNING: No supported files found in {input_dir}")
            print(f"Supported formats: {', '.join(self.supported_formats)}")
            return {"error": "No supported files found"}
        
        print(f"Found {len(files_to_process)} files to process")
        
        # Process statistics
        stats = {
            "total_files": len(files_to_process),
            "processed_files": 0,
            "total_chunks": 0,
            "failed_files": [],
            "processing_time": None
        }
        
        start_time = datetime.now()
        
        # Process each file
        for file_path in tqdm(files_to_process, desc="Processing documents"):
            try:
                chunks, metadata_list, ids = self.process_document(file_path)
                
                if chunks:
                    # Generate embeddings for chunks
                    embeddings = self.generate_embeddings(chunks)
                    
                    # Add to database with embeddings
                    db.add_document_chunks(chunks, metadata_list, ids, embeddings)
                    stats["total_chunks"] += len(chunks)
                    stats["processed_files"] += 1
                else:
                    stats["failed_files"].append(str(file_path))
                    
            except Exception as e:
                print(f"ERROR: Failed to process {file_path}: {e}")
                stats["failed_files"].append(str(file_path))
        
        end_time = datetime.now()
        stats["processing_time"] = str(end_time - start_time)
        
        print(f"\nProcessing completed!")
        print(f"Processed {stats['processed_files']}/{stats['total_files']} files")
        print(f"Created {stats['total_chunks']} total chunks")
        print(f"⏱️ Processing time: {stats['processing_time']}")
        
        if stats["failed_files"]:
            print(f"WARNING: Failed files: {len(stats['failed_files'])}")
            for failed_file in stats["failed_files"]:
                print(f"   - {failed_file}")
        
        return stats


def main():
    """Main function to run document processing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process documents for fact-checking database")
    parser.add_argument("--input_dir", default="./documents", 
                       help="Directory containing documents to process")
    parser.add_argument("--db_path", default="./data/chroma_db", 
                       help="Path to ChromaDB database")
    parser.add_argument("--embedding_model", default="all-MiniLM-L6-v2",
                       help="Sentence transformer model to use")
    parser.add_argument("--clear_db", action="store_true",
                       help="Clear existing database before processing")
    
    args = parser.parse_args()
    
    print("Starting document processing pipeline...")
    print(f"Input directory: {args.input_dir}")
    print(f"Database path: {args.db_path}")
    print(f"🤖 Embedding model: {args.embedding_model}")
    
    # Initialize database
    db = FactCheckDatabase(args.db_path)
    
    if args.clear_db:
        print("Clearing existing database...")
        db.clear_collection()
    
    # Initialize processor
    processor = DocumentProcessor(args.embedding_model)
    
    # Process documents
    stats = processor.process_directory(args.input_dir, db)
    
    # Show final database stats
    db_stats = db.get_collection_stats()
    print(f"\nFinal database stats: {db_stats}")
    
    print("\nDocument processing pipeline completed!")


if __name__ == "__main__":
    main()