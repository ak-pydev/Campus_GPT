"""
FastAPI Main Application
Provides REST API endpoints for the Campus GPT frontend
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from contextlib import asynccontextmanager
import time
import asyncio
from typing import AsyncGenerator
import json

from backend.models import ChatRequest, ChatResponse, HealthResponse, ErrorResponse
from backend.rag_service import get_rag_service, RAGService
from backend import __version__


# Global RAG service instance
rag_service: RAGService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for the FastAPI app
    """
    # Startup
    global rag_service
    try:
        print("🚀 Initializing RAG service...")
        rag_service = get_rag_service()
        health = rag_service.health_check()
        if health["status"] == "operational":
            print("✅ RAG service initialized successfully")
        else:
            print(f"⚠️ RAG service initialized with warnings: {health.get('reason', 'Unknown')}")
    except Exception as e:
        print(f"❌ Failed to initialize RAG service: {str(e)}")
        print("⚠️ API will start but /api/chat endpoint may not work")
    
    yield
    
    # Shutdown
    print("👋 Shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Campus GPT API",
    description="REST API for Campus GPT - AI-powered university assistant",
    version=__version__,
    lifespan=lifespan
)


# CORS Configuration
# Allow requests from frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",  # Vite alternate port
        "http://localhost:3000",  # Alternative React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for custom errors
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unexpected errors"""
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# Routes

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Campus GPT API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns the status of the API and RAG system
    """
    if rag_service is None:
        return HealthResponse(
            status="degraded",
            version=__version__,
            rag_system="not_initialized"
        )
    
    rag_health = rag_service.health_check()
    
    return HealthResponse(
        status="healthy" if rag_health["status"] == "operational" else "degraded",
        version=__version__,
        rag_system=rag_health["status"]
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Chat endpoint - Get answer from RAG system
    
    Args:
        request: ChatRequest with student question
        
    Returns:
        ChatResponse with AI-generated answer
        
    Raises:
        HTTPException: If RAG service is not available or request fails
    """
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG service not initialized. Please check server logs."
        )
    
    # Validate question
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )
    
    try:
        # Record start time
        start_time = time.time()
        
        # Get answer from RAG system
        result = await rag_service.get_answer_async(question)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Add processing time to metadata
        if result.get("metadata"):
            result["metadata"]["processing_time"] = round(processing_time, 2)
        else:
            result["metadata"] = {"processing_time": round(processing_time, 2)}
        
        return ChatResponse(
            answer=result["answer"],
            sources=result.get("sources"),
            metadata=result.get("metadata")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}"
        )


@app.post("/api/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint - Get answer from RAG system with SSE
    
    Args:
        request: ChatRequest with student question
        
    Returns:
        StreamingResponse with SSE events
        
    Raises:
        HTTPException: If RAG service is not available
    """
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG service not initialized"
        )
    
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events"""
        try:
            # Consume the async generator from the service
            async for chunk in rag_service.get_answer_stream(question):
                yield f"data: {json.dumps(chunk)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Campus GPT API...")
    print("📚 Documentation available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
