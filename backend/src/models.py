"""
Pydantic models for structured LLM responses and API data
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class FactCheckClassification(str, Enum):
    """Classification for fact-checking responses"""
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"
    MIXED = "MIXED"




class SourceReference(BaseModel):
    """Reference to a source document used in fact-checking"""
    source_number: int = Field(description="Source number from the context")
    file_name: str = Field(description="Name of the source file")
    document_url: Optional[str] = Field(default=None, description="URL or path to access the source document")


class FactCheckResponse(BaseModel):
    """Structured fact-checking response from LLM"""
    classification: FactCheckClassification = Field(description="Fact-check classification")
    analysis: str = Field(description="Detailed analysis of the claim", min_length=10)
    sources_used: List[SourceReference] = Field(description="Sources that support the conclusion")
    reasoning: str = Field(description="Step-by-step reasoning process", min_length=20)


class TokenUsage(BaseModel):
    """Token usage statistics for LLM requests"""
    prompt_tokens: int = Field(description="Number of tokens in the prompt")
    completion_tokens: int = Field(description="Number of tokens in the completion")
    total_tokens: int = Field(description="Total tokens used")


class ContextChunk(BaseModel):
    """Context chunk with metadata"""
    text: str = Field(description="Text content of the chunk")
    source_file: str = Field(description="Source file name")
    source: Optional[str] = Field(default=None, description="Original source URL of the document")
    document_url: Optional[str] = Field(default=None, description="URL or path to access the source document")
    chunk_index: int = Field(description="Index of the chunk in the source")
    confidence: float = Field(description="Confidence score for relevance", ge=0.0, le=1.0)
    distance: float = Field(description="Vector distance from query", ge=0.0)


class LLMResponseWrapper(BaseModel):
    """Complete LLM service response"""
    status: str = Field(description="Response status")
    fact_check: Optional[FactCheckResponse] = Field(default=None, description="Structured fact-check response")
    model_used: str = Field(description="LLM model used for generation")
    token_usage: TokenUsage = Field(description="Token usage statistics")
    error: Optional[str] = Field(default=None, description="Error message if any")
    fallback_response: Optional[str] = Field(default=None, description="Fallback response if structured parsing fails")


class APIFactCheckResponse(BaseModel):
    """Complete API response for fact-checking endpoint"""
    status: str = Field(description="API response status")
    query: str = Field(description="Original query text")
    context: List[ContextChunk] = Field(description="Retrieved context chunks")
    total_context_chunks: int = Field(description="Total number of context chunks")
    timestamp: str = Field(description="Response timestamp")
    fact_check: Optional[FactCheckResponse] = Field(default=None, description="LLM fact-check response")
    llm_response: Optional[LLMResponseWrapper] = Field(default=None, description="Complete LLM response details")
    message: Optional[str] = Field(default=None, description="Additional status message")


class APIQueryResponse(BaseModel):
    """API response for general query endpoint"""
    status: str = Field(description="API response status")
    query: str = Field(description="Original query text")
    context: List[ContextChunk] = Field(description="Retrieved context chunks")
    message: str = Field(description="Response message")
    timestamp: str = Field(description="Response timestamp")