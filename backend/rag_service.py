"""
RAG Service - Optimized for production using utilizing direct ChromaDB and Ollama calls.
Bypasses CrewAI for lower latency and better control over the RAG pipeline.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Generator, AsyncGenerator
import asyncio
from functools import partial
import json

# Fix for Windows Unicode output issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import ollama

# Add parent directory to path to import from 02_rag_system if needed
current_dir = Path(__file__).parent
project_root = current_dir.parent


class RAGService:
    """Service class to interact with the RAG system directly"""
    
    def __init__(self):
        """Initialize the RAG service with persistent ChromaDB connection"""
        self.project_root = project_root
        
        # Ensure ChromaDB path is correct
        self.chroma_path = self.project_root / "02_rag_system" / "chroma_db"
        
        if not self.chroma_path.exists():
            # Fallback for dev environment path differences
            dev_path = self.project_root / "chroma_db"
            if dev_path.exists():
                self.chroma_path = dev_path
            else:
                 print(f"⚠️ Warning: ChromaDB not found at {self.chroma_path}")
        
        # Initialize Ollama client explicitly
        try:
            self.ollama_client = ollama.Client(host='http://127.0.0.1:11435')
            print("✅ Ollama client initialized for http://127.0.0.1:11435", flush=True)
        except Exception as e:
            print(f"❌ Failed to initialize Ollama client: {e}", flush=True)
            self.ollama_client = None

        try:
            print(f"DEBUG: Attempting to connect to ChromaDB at {self.chroma_path}", flush=True)
            # Log to file for debugging
            with open("rag_init.log", "w", encoding='utf-8') as f:
                f.write(f"Attempting to connect to {self.chroma_path}\n")

            self.client = chromadb.PersistentClient(path=str(self.chroma_path))
            
            # 1. Setup the explicit Ollama Embedding Function
            self.ollama_ef = embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text",
                url="http://127.0.0.1:11435/api/embeddings"
            )
            
            # 2. Re-bind the embedding function EVERY time you get the collection
            # This ensures query_texts=[...] uses nomic-embed-text, not the default MiniLM.
            self.collection = self.client.get_collection(
                name="nku_docs",
                embedding_function=self.ollama_ef
            )
            
            # Test query to check if embeddings match
            try:
                self.collection.count()
            except Exception as db_err:
                print(f"❌ DATABASE ERROR: {db_err}")
                print("⚠️ Likely cause: Existing database was created with a different embedding model.")
                print("Please delete the chroma_db folder and re-ingest your documents.")
                raise db_err

            with open("rag_init.log", "a", encoding='utf-8') as f:
                f.write("Success!\n")
                
            print(f"✅ RAG Service connected to ChromaDB at {self.chroma_path}")
            print(f"✅ RAG Service active. Collection count: {self.collection.count()}")
        except Exception as e:
            error_msg = f"❌ Failed to connect to ChromaDB: {e}"
            # Use safe printing for Windows
            try:
                print(error_msg, flush=True)
            except UnicodeEncodeError:
                print(error_msg.encode('utf-8', errors='replace').decode('utf-8'), flush=True)
                
            import traceback
            traceback.print_exc()
            with open("rag_error.log", "w", encoding='utf-8') as f:
                f.write(error_msg + "\n")
                f.write(traceback.format_exc())
            self.collection = None

    def _retrieve_context(self, question: str, n_results: int = 3) -> tuple[str, list]:
        """
        Retrieve relevant context from ChromaDB
        """
        if not self.collection:
            return "", []
            
        try:
            # 3. FIXED: Because we passed embedding_function to get_collection, 
            # query_texts will now correctly call your Ollama API at port 11435.
            results = self.collection.query(
                query_texts=[question],
                n_results=n_results
            )
            
            if not results['documents']:
                 return "", []
                 
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]
            
            context_parts = []
            sources = []
            
            for i, doc in enumerate(documents):
                meta = metadatas[i]
                
                # Format context for the LLM
                source_title = meta.get('title', 'Unknown Source')
                url = meta.get('anchor_url', meta.get('url', ''))
                
                context_parts.append(f"Source: {source_title} ({url})\nContent: {doc}")
                
                # Collect sources for the UI
                sources.append({
                    "title": source_title,
                    "url": url
                })
                
            return "\n\n".join(context_parts), sources
            
        except Exception as e:
            print(f"Error retrieving context: {e}")
            return "", []

    def get_answer(self, question: str) -> Dict[str, Any]:
        """
        Get answer from RAG system (Synchronous)
        """
        context, sources = self._retrieve_context(question)
        
        # We don't need to manually add the system prompt because it's defined in the Modelfile
        # Just provide the context and question in the user message
        user_content = f"""Context:
{context}

Question: {question}
"""
        
        try:
            if not self.ollama_client:
                 raise RuntimeError("Ollama client not initialized")

            print(f"DEBUG: Generating with model 'campus-gpt' using {len(context)} chars of context", flush=True)

            response = self.ollama_client.chat(
                model="campus-gpt:latest",
                messages=[
                    {
                        'role': 'user', 
                        'content': user_content
                    }
                ],
                stream=False
            )
            
            return {
                "answer": response['message']['content'],
                "sources": sources,
                "metadata": {
                    "model": "campus-gpt:latest",
                    "retriever": "chromadb_persistent"
                }
            }
        except Exception as e:
            return {
                "answer": f"Error generating response: {str(e)}",
                "sources": [],
                "metadata": {"error": str(e)}
            }

    async def get_answer_async(self, question: str) -> Dict[str, Any]:
        """Async wrapper for get_answer"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_answer, question)

    async def get_answer_stream(self, question: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generator for streaming responses
        """
        context, sources = self._retrieve_context(question)
        
        user_content = f"""Context:
{context}

Question: {question}
"""
        
        try:
            if not self.ollama_client:
                 yield {
                    "type": "error",
                    "message": "Ollama client not initialized"
                 }
                 return

            print(f"DEBUG: Streaming with model 'campus-gpt' using {len(context)} chars of context", flush=True)

            stream = self.ollama_client.chat(
                model="campus-gpt:latest",
                messages=[
                    {
                        'role': 'user', 
                        'content': user_content
                    }
                ],
                stream=True
            )
            
            # Send initial metadata
            yield {
                "type": "start",
                "sources": sources
            }
            
            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield {
                        "type": "chunk",
                        "content": chunk['message']['content']
                    }
                    # Yield control to event loop occasionally
                    await asyncio.sleep(0)
            
            yield {
                "type": "complete",
                "sources": sources,
                "metadata": {"model": "campus-gpt:latest"}
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e)
            }

    def health_check(self) -> Dict[str, str]:
        """Check if RAG system is operational"""
        status = "operational"
        reason = "System healthy"
        
        if not self.collection:
            status = "degraded"
            reason = "ChromaDB collection not accessible"
            return {"status": status, "reason": reason}
            
        try:
            # fast check if ollama is responsive
            if not self.ollama_client:
                raise RuntimeError("Ollama client is None")
            self.ollama_client.list()
        except Exception as e:
            status = "degraded"
            reason = f"Ollama service not reachable: {e}"
            print(f"❌ Ollama health check failed: {e}", flush=True)
            with open("ollama_error.log", "w", encoding='utf-8') as f:
                f.write(f"Ollama error: {e}\n")

        return {"status": status, "reason": reason}


# Singleton instance
_rag_service_instance = None

def get_rag_service() -> RAGService:
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    return _rag_service_instance
