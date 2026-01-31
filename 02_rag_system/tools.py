import os
import json
import chromadb
from chromadb.config import Settings
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict
from sentence_transformers import SentenceTransformer
import uuid

# --- Helper for Manual Chunking (since we aren't using LangChain's chunkers) ---
class TextChunker:
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)

    def split_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Simple splitting by character count for robustness, can be enhanced."""
        if not text:
            return []
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += (chunk_size - overlap)
        return chunks

# --- Tool: Read JSONL ---
class FileReadInput(BaseModel):
    file_path: str = Field(..., description="Path to the JSONL file to read.")

class FileReadTool(BaseTool):
    name: str = "Read Campus Data"
    description: str = "Reads the campus_data.jsonl file and returns a list of page content."
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, file_path: str) -> str:
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            return json.dumps(data[:50]) # Return first 50 for safety in context? 
            # Actually, agents shouldn't read the WHOLE file into context. 
            # This tool might be better used by the Ingestion Agent to iterate line by line internally.
            # But CrewAI tools usually return strings.
            # Let's return a summary or path for the agent to use the specialized IngestTool.
            return f"Successfully validated file at {file_path} with {len(data)} records."
        except Exception as e:
            return f"Error reading file: {str(e)}"

# --- Tool: ChromaDB Ingestion ---
class ChromaIngestInput(BaseModel):
    file_path: str = Field(..., description="Path to the JSONL data file.")

class ChromaIngestTool(BaseTool):
    name: str = "Ingest Knowledge Base"
    description: str = "Reads JSONL file, chunks text, and embeds into ChromaDB."
    args_schema: Type[BaseModel] = ChromaIngestInput

    def _run(self, file_path: str) -> str:
        try:
            # Initialize Chroma
            client = chromadb.PersistentClient(path="./chroma_db")
            collection = client.get_or_create_collection(name="nku_docs")
            
            # Initialize Chunker
            chunker = TextChunker()
            
            # Read and Ingest
            count = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    
                    page = json.loads(line)
                    text = page.get('text', '')
                    url = page.get('url', '')
                    title = page.get('title', '')
                    
                    if not text: continue
                    
                    chunks = chunker.split_text(text)
                    
                    ids = [str(uuid.uuid4()) for _ in chunks]
                    metadatas = [{"url": url, "title": title} for _ in chunks]
                    
                    # Embeddings are handled automatically by Chroma if not provided, 
                    # BUT default chroma uses onnx/sentence-transformers. 
                    # To be safe/explicit with our installed 'sentence-transformers', 
                    # we can manually embed or just let Chroma do it (it uses DefaultEmbeddingFunction).
                    # Let's let Chroma do it for simplicity unless it fails.
                    
                    collection.add(
                        documents=chunks,
                        metadatas=metadatas,
                        ids=ids
                    )
                    count += 1
            
            return f"Successfully ingested {count} pages into ChromaDB."
        except Exception as e:
            return f"Ingestion failed: {str(e)}"

# --- Tool: ChromaDB Search ---
class ChromaSearchInput(BaseModel):
    query: str = Field(..., description="The student's question to search for.")

class ChromaSearchTool(BaseTool):
    name: str = "Search Knowledge Base"
    description: str = "Searches the vector database for relevant university information."
    args_schema: Type[BaseModel] = ChromaSearchInput

    def _run(self, query: str) -> str:
        try:
            client = chromadb.PersistentClient(path="./chroma_db")
            collection = client.get_collection(name="nku_docs")
            
            results = collection.query(
                query_texts=[query],
                n_results=3  # Reduced from 5 for faster responses
            )
            
            # Format results
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            
            formatted_results = ""
            for i, doc in enumerate(docs):
                source = metas[i].get('url', 'Unknown URL')
                title = metas[i].get('title', 'No Title')
                formatted_results += f"Source: {title} ({source})\nContent: {doc}\n\n"
                
            return formatted_results if formatted_results else "No relevant information found."
        except Exception as e:
            return f"Search failed: {str(e)}"
