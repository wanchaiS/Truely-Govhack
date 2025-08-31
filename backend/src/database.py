"""
Database setup and management for fact-checking system using ChromaDB
"""

import chromadb
import os
from typing import Dict, List, Optional
from datetime import datetime

class FactCheckDatabase:
    def __init__(self, db_path: str = "./data/chroma_db"):
        """
        Initialize ChromaDB client and collection for fact-checking documents
        
        Args:
            db_path: Path to store the persistent ChromaDB data
        """
        self.db_path = db_path
        self.client = None
        self.collection = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize ChromaDB client and create/get collection"""
        try:
            # Create persistent ChromaDB client
            self.client = chromadb.PersistentClient(path=self.db_path)
            
            # Create or get collection for fact-checking documents
            self.collection = self.client.get_or_create_collection(
                name="fact_check_documents",
                metadata={
                    "description": "Document chunks for fact-checking with embeddings",
                    "created_at": datetime.now().isoformat()
                }
            )
            
            print(f"Database initialized successfully at: {self.db_path}")
            print(f"Collection 'fact_check_documents' ready")
            
        except Exception as e:
            print(f"ERROR: Error initializing database: {e}")
            raise
    
    def add_document_chunks(self, chunks: List[str], metadatas: List[Dict], ids: List[str], embeddings: List[List[float]] = None):
        """
        Add document chunks to the collection
        
        Args:
            chunks: List of text chunks
            metadatas: List of metadata dictionaries for each chunk
            ids: List of unique IDs for each chunk
            embeddings: Optional pre-computed embeddings (if None, ChromaDB will generate them)
        """
        try:
            if embeddings is not None:
                self.collection.add(
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=embeddings
                )
            else:
                self.collection.add(
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids
                )
            print(f"Added {len(chunks)} document chunks to database")
            
        except Exception as e:
            print(f"ERROR: Error adding documents: {e}")
            raise
    
    def query_similar_with_embeddings(self, query_embeddings: List[float], n_results: int = 5) -> Dict:
        """
        Query for similar document chunks using pre-computed embeddings
        
        Args:
            query_embeddings: Pre-computed embedding vector for the query
            n_results: Number of results to return
            
        Returns:
            Dictionary with similar chunks and their metadata
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embeddings],
                n_results=n_results
            )
            return results
            
        except Exception as e:
            print(f"ERROR: Error querying database: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the collection"""
        try:
            count = self.collection.count()
            return {
                "total_chunks": count,
                "collection_name": self.collection.name,
                "db_path": self.db_path
            }
        except Exception as e:
            print(f"ERROR: Error getting stats: {e}")
            return {"total_chunks": 0, "collection_name": "unknown", "db_path": self.db_path}
    
    def delete_document_by_filename(self, filename: str) -> int:
        """
        Delete all chunks for a specific source file
        
        Args:
            filename: Name of the source file to delete
            
        Returns:
            Number of chunks deleted
        """
        try:
            # Delete all chunks with matching source_file metadata
            result = self.collection.delete(
                where={'source_file': {'$eq': filename}}
            )
            
            # ChromaDB delete returns None, so we need to check differently
            print(f"Deleted all chunks for file: {filename}")
            return 1  # Simplified return - indicates success
            
        except Exception as e:
            print(f"ERROR: Error deleting document chunks for {filename}: {e}")
            raise
    
    def clear_collection(self):
        """Clear all documents from the collection (useful for testing)"""
        try:
            # Delete and recreate collection
            self.client.delete_collection("fact_check_documents")
            self.collection = self.client.create_collection(
                name="fact_check_documents",
                metadata={
                    "description": "Document chunks for fact-checking with embeddings",
                    "cleared_at": datetime.now().isoformat()
                }
            )
            print("Collection cleared successfully")
            
        except Exception as e:
            print(f"ERROR: Error clearing collection: {e}")


def test_database():
    """Test function to verify database setup"""
    print("🧪 Testing database setup...")
    
    # Initialize database
    db = FactCheckDatabase()
    
    # Test adding sample data
    sample_chunks = [
        "The Earth is approximately 4.5 billion years old.",
        "Vaccines have been proven safe and effective by multiple clinical trials.",
        "Climate change is primarily caused by human activities since the industrial revolution."
    ]
    
    sample_metadata = [
        {"source": "test_doc", "category": "science", "chunk_id": 0},
        {"source": "test_doc", "category": "health", "chunk_id": 1},
        {"source": "test_doc", "category": "environment", "chunk_id": 2}
    ]
    
    sample_ids = ["test_1", "test_2", "test_3"]
    
    # Add test data
    db.add_document_chunks(sample_chunks, sample_metadata, sample_ids)
    
    # Test querying
    query = "How old is Earth?"
    results = db.query_similar(query, n_results=2)
    
    print(f"\nQuery: '{query}'")
    print("Results:")
    for i, doc in enumerate(results['documents'][0]):
        print(f"  {i+1}. {doc}")
        print(f"     Metadata: {results['metadatas'][0][i]}")
        print(f"     Distance: {results['distances'][0][i]:.4f}")
    
    # Show stats
    stats = db.get_collection_stats()
    print(f"\nDatabase Stats: {stats}")
    
    print("\nDatabase test completed successfully!")
    return db


if __name__ == "__main__":
    test_database()