"""
LLM service for generating fact-checking responses
Uses OpenAI GPT models to analyze retrieved context and provide fact-checking responses
"""

import os
import openai
from typing import List, Dict, Optional
import logging
import json
from models import FactCheckResponse, LLMResponseWrapper, TokenUsage, SourceReference, FactCheckClassification

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize LLM service with OpenAI configuration
        
        Args:
            api_key: OpenAI API key (if None, reads from environment)
            model: OpenAI model to use for generation
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter")
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)
        
        logger.info(f"LLM Service initialized with model: {model}")
    
    def create_fact_check_prompt(self, query: str, context_chunks: List[Dict]) -> str:
        """
        Create a fact-checking prompt using the query and retrieved context
        
        Args:
            query: User's fact-checking query
            context_chunks: List of relevant document chunks with metadata
            
        Returns:
            Formatted prompt for the LLM
        """
        prompt = f"""You are a fact-checking assistant. Your task is to analyze the provided context and give a factual assessment of the user's query.

USER QUERY: "{query}"

RETRIEVED CONTEXT:
"""
        
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk.get('source_file', 'unknown')
            text = chunk.get('text', '')
            
            prompt += f"\n[Source {i}] (File: {source})\n{text}\n"
        
        prompt += """
INSTRUCTIONS:
1. Analyze the retrieved context carefully
2. Determine if the context supports, contradicts, or is insufficient to verify the query
3. Provide a clear fact-check response with one of these classifications:
   - SUPPORTED: The query is supported by the evidence
   - CONTRADICTED: The query is contradicted by the evidence  
   - INSUFFICIENT: Not enough evidence to make a determination
   - MIXED: Evidence both supports and contradicts aspects of the query

4. If the query is not a factual statement suitable for fact-checking (e.g., opinions, requests, questions), classify it as INSUFFICIENT and explain why it's not fact-checkable
5. In your reasoning, DO NOT refer to sources by number (like "Source 1" or "Source 3"). Instead, refer to them by their content or context (like "the tax documentation" or "official guidelines")
6. Be precise and avoid speculation beyond what the evidence shows

You must respond with a JSON object matching this exact structure:
{
  "classification": "SUPPORTED|CONTRADICTED|INSUFFICIENT|MIXED",
  "analysis": "Your detailed analysis of the claim without source numbers",
  "sources_used": [
    {
      "source_number": 1,
      "file_name": "filename.txt"
    }
  ],
  "reasoning": "Step-by-step reasoning process without mentioning source numbers"
}
"""
        
        return prompt
    
    def generate_fact_check_response(self, query: str, context_chunks: List[Dict]) -> LLMResponseWrapper:
        """
        Generate a fact-checking response using LLM with structured output
        
        Args:
            query: User's fact-checking query
            context_chunks: List of relevant document chunks with metadata including document_url
            
        Returns:
            LLMResponseWrapper containing structured response
        """
        # Handle case where no context is found
        if not context_chunks:
            no_context_response = FactCheckResponse(
                classification=FactCheckClassification.INSUFFICIENT,
                analysis="No relevant documents found to fact-check this query.",
                sources_used=[],
                reasoning="No context documents were retrieved from the database that match this query."
            )
            
            return LLMResponseWrapper(
                status="success",
                fact_check=no_context_response,
                model_used=self.model,
                token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            )
        
        try:
            # Create the prompt
            prompt = self.create_fact_check_prompt(query, context_chunks)
            
            # Generate response using OpenAI with JSON mode
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional fact-checker who analyzes evidence carefully and provides accurate assessments. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Low temperature for more consistent fact-checking
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            generated_text = response.choices[0].message.content
            
            # Parse and validate the JSON response
            try:
                json_response = json.loads(generated_text)
                
                # Create source references with document URLs
                # First, create a mapping from source file names to document URLs
                source_file_to_url = {}
                for chunk in context_chunks:
                    if chunk.get('source_file') and chunk.get('document_url'):
                        source_file_to_url[chunk.get('source_file')] = chunk.get('document_url')
                
                sources_used = []
                for source_data in json_response.get('sources_used', []):
                    source_file = source_data.get('file_name', 'unknown')
                    document_url = source_file_to_url.get(source_file)
                    
                    sources_used.append(SourceReference(
                        source_number=source_data.get('source_number', 1),
                        file_name=source_file,
                        document_url=document_url
                    ))
                
                # Create structured fact-check response
                fact_check = FactCheckResponse(
                    classification=FactCheckClassification(json_response.get('classification', 'INSUFFICIENT')),
                    analysis=json_response.get('analysis', 'Analysis not provided'),
                    sources_used=sources_used,
                    reasoning=json_response.get('reasoning', 'Reasoning not provided')
                )
                
                return LLMResponseWrapper(
                    status="success",
                    fact_check=fact_check,
                    model_used=self.model,
                    token_usage=TokenUsage(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens
                    )
                )
                
            except (json.JSONDecodeError, ValueError) as parse_error:
                logger.warning(f"Failed to parse LLM JSON response: {parse_error}")
                logger.warning(f"Raw response: {generated_text}")
                
                return LLMResponseWrapper(
                    status="error",
                    fact_check=None,
                    model_used=self.model,
                    token_usage=TokenUsage(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens
                    ),
                    error=f"JSON parsing failed: {str(parse_error)}",
                    fallback_response=generated_text
                )
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return LLMResponseWrapper(
                status="error",
                fact_check=None,
                model_used=self.model,
                token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                error=str(e),
                fallback_response=self._create_fallback_response(context_chunks)
            )
    
    def _create_fallback_response(self, context_chunks: List[Dict]) -> str:
        """
        Create a fallback response when LLM fails
        
        Args:
            context_chunks: List of relevant document chunks
            
        Returns:
            Fallback response text
        """
        if not context_chunks:
            return "No relevant context found to fact-check this query."
        
        response = "LLM service unavailable. Here are the most relevant sources found:\n\n"
        
        for i, chunk in enumerate(context_chunks[:3], 1):  # Show top 3 chunks
            confidence = chunk.get('confidence', 0)
            source = chunk.get('source_file', 'unknown')
            text = chunk.get('text', '')[:200] + "..." if len(chunk.get('text', '')) > 200 else chunk.get('text', '')
            
            response += f"Source {i} (Confidence: {confidence:.3f})\nFrom: {source}\n{text}\n\n"
        
        return response
    
    def test_connection(self) -> Dict:
        """
        Test the LLM service connection
        
        Returns:
            Dictionary with connection status
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Say 'Connection test successful'"}],
                max_tokens=10
            )
            
            return {
                "status": "success",
                "message": "LLM service connection successful",
                "model": self.model,
                "response": response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM service connection failed: {str(e)}"
            }


def test_llm_service():
    """Test function for LLM service"""
    try:
        llm = LLMService()
        
        # Test connection
        connection_test = llm.test_connection()
        print("🔗 Connection Test:", connection_test)
        
        # Test fact-checking with sample data
        sample_query = "Is the Earth round?"
        sample_context = [
            {
                "text": "The Earth is approximately spherical in shape, with a slight flattening at the poles due to its rotation.",
                "confidence": 0.95,
                "source_file": "science_facts.txt"
            },
            {
                "text": "Satellite imagery and space missions have confirmed the Earth's spherical shape.",
                "confidence": 0.92,
                "source_file": "space_exploration.txt"
            }
        ]
        
        print(f"\n🧪 Testing fact-check for: '{sample_query}'")
        result = llm.generate_fact_check_response(sample_query, sample_context)
        
        if result["status"] == "success":
            print("✅ Fact-check response generated successfully")
            print("\n📝 Response:")
            print(result["response"])
            print(f"\n📊 Token usage: {result['token_usage']}")
        else:
            print("❌ Fact-check failed:")
            print(result.get("error", "Unknown error"))
            if "fallback_response" in result:
                print("\n🔄 Fallback response:")
                print(result["fallback_response"])
        
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    test_llm_service()