"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    question: str = Field(..., min_length=1, max_length=1000, description="Student's question")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the admission requirements for NKU?"
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    answer: str = Field(..., description="AI-generated answer")
    sources: Optional[List[Dict[str, str]]] = Field(default=None, description="Source documents used")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "To apply to NKU, you need...",
                "sources": [
                    {"url": "https://nku.edu/admissions", "title": "Admissions"}
                ],
                "metadata": {
                    "model": "victor_viking",
                    "processing_time": 2.5
                }
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str = Field(..., description="API health status")
    version: str = Field(..., description="API version")
    rag_system: str = Field(..., description="RAG system status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "rag_system": "operational"
            }
        }


class ErrorResponse(BaseModel):
    """Response model for errors"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid request",
                "detail": "Question cannot be empty"
            }
        }
