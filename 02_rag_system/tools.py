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
    description: str = "Reads the combined campus data file (web + PDF) and validates it."
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, file_path: str) -> str:
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            
            # Count by source type
            web_count = sum(1 for d in data if d.get('source_type', 'web') == 'web')
            pdf_count = sum(1 for d in data if d.get('source_type') == 'pdf')
            
            return f"Successfully validated file at {file_path} with {len(data)} records ({web_count} web pages, {pdf_count} PDF chunks)."
        except Exception as e:
            return f"Error reading file: {str(e)}"

# --- Tool: ChromaDB Ingestion with Enhanced Metadata ---
class ChromaIngestInput(BaseModel):
    file_path: str = Field(..., description="Path to the combined JSONL data file.")

class ChromaIngestTool(BaseTool):
    name: str = "Ingest Knowledge Base"
    description: str = "Reads combined JSONL file (web + PDF), chunks text, and embeds into ChromaDB with enhanced metadata."
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
            web_count = 0
            pdf_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    
                    entry = json.loads(line)
                    text = entry.get('text', '')
                    
                    if not text: continue
                    
                    # Extract enhanced metadata
                    url = entry.get('url', '')
                    anchor_url = entry.get('anchor_url', url)  # Prefer deep link
                    title = entry.get('title', '')
                    section_header = entry.get('section_header')
                    persona = entry.get('persona', 'all')
                    source_type = entry.get('source_type', 'web')
                    header_level = entry.get('header_level')
                    
                    # PDF-specific metadata
                    pdf_page = entry.get('pdf_page')
                    
                    # Chunk the text (only if it's large, otherwise keep as-is)
                    if len(text) > 500:
                        chunks = chunker.split_text(text)
                    else:
                        chunks = [text]
                    
                    ids = [str(uuid.uuid4()) for _ in chunks]
                    
                    # Enhanced metadata for each chunk
                    metadatas = [{
                        "url": url,
                        "anchor_url": anchor_url,  # Deep link for citations
                        "title": title,
                        "section_header": section_header if section_header else "",
                        "persona": persona,
                        "source_type": source_type,
                        "header_level": header_level if header_level else "",
                        "pdf_page": pdf_page if pdf_page else 0,
                    } for _ in chunks]
                    
                    collection.add(
                        documents=chunks,
                        metadatas=metadatas,
                        ids=ids
                    )
                    
                    count += 1
                    if source_type == "pdf":
                        pdf_count += 1
                    else:
                        web_count += 1
            
            return f"Successfully ingested {count} entries into ChromaDB ({web_count} web pages, {pdf_count} PDF chunks) with enhanced metadata (anchor URLs, personas, section headers)."
        except Exception as e:
            return f"Ingestion failed: {str(e)}"

# --- Tool: ChromaDB Search with Enhanced Results ---
class ChromaSearchInput(BaseModel):
    query: str = Field(..., description="The student's question to search for.")
    persona_filter: str = Field(default="all", description="Filter by persona (student, faculty, prospective, all)")

class ChromaSearchTool(BaseTool):
    name: str = "Search Knowledge Base"
    description: str = "Searches the vector database for relevant university information with persona filtering and deep-linked citations."
    args_schema: Type[BaseModel] = ChromaSearchInput

    def _run(self, query: str, persona_filter: str = "all") -> str:
        try:
            client = chromadb.PersistentClient(path="./chroma_db")
            collection = client.get_collection(name="nku_docs")
            
            # Build where filter for persona
            where_filter = None
            if persona_filter != "all":
                where_filter = {"persona": {"$in": [persona_filter, "all"]}}
            
            results = collection.query(
                query_texts=[query],
                n_results=5,  # Increased from 3 for better coverage
                where=where_filter if where_filter else None
            )
            
            # Format results with enhanced metadata
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            
            formatted_results = ""
            for i, doc in enumerate(docs):
                # Prefer anchor URL for deep linking
                source_url = metas[i].get('anchor_url', metas[i].get('url', 'Unknown URL'))
                title = metas[i].get('title', 'No Title')
                section = metas[i].get('section_header', '')
                source_type = metas[i].get('source_type', 'web')
                
                # Build citation
                citation = f"Source: {title}"
                if section:
                    citation += f" - {section}"
                if source_type == "pdf":
                    pdf_page = metas[i].get('pdf_page', 0)
                    if pdf_page:
                        citation += f" (PDF Page {pdf_page})"
                citation += f"\nLink: {source_url}"
                
                formatted_results += f"{citation}\nContent: {doc}\n\n"
                
            return formatted_results if formatted_results else "No relevant information found."
        except Exception as e:
            return f"Search failed: {str(e)}"
