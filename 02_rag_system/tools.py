import os
import json
import chromadb
from chromadb.config import Settings
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict
# from sentence_transformers import SentenceTransformer
import uuid

# --- Helper for Manual Chunking (since we aren't using LangChain's chunkers) ---
class TextChunker:
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        # self.model = SentenceTransformer(model_name) # Unused
        pass

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
            import chromadb.utils.embedding_functions as embedding_functions
            
            # Initialize Chroma (use absolute path)
            chroma_path = os.path.join(os.path.dirname(__file__), "chroma_db")
            client = chromadb.PersistentClient(path=chroma_path)
            
            # Use Ollama embeddings (nomic-embed-text)
            # We use the explicitly configured host from our environment/debugging
            ollama_ef = embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text",
                url="http://127.0.0.1:11435/api/embeddings"
            )
            
            collection = client.get_or_create_collection(
                name="nku_docs",
                embedding_function=ollama_ef
            )
            
            # Initialize Chunker
            chunker = TextChunker()
            
            # Read and Ingest
            count = 0
            web_count = 0
            pdf_count = 0
            
            # Batching variables
            batch_documents = []
            batch_metadatas = []
            batch_ids = []
            BATCH_SIZE = 100
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_idx, line in enumerate(f):
                    if not line.strip(): continue
                    
                    try:
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
                        
                        # Chunk the text
                        if len(text) > 500:
                            chunks = chunker.split_text(text)
                        else:
                            chunks = [text]
                        
                        # Prepare batch data
                        for i, chunk in enumerate(chunks):
                            chunk_id = f"{line_idx}_{i}_{str(uuid.uuid4())}"
                            
                            # Safe integer conversion helper (inline for speed)
                            def safe_int(val, default=0):
                                try:
                                    if val is None: return default
                                    s = str(val).lower().replace('h', '').replace(' ', '')
                                    return int(float(s))
                                except:
                                    return default

                            meta = {
                                "url": str(url),
                                "anchor_url": str(anchor_url),
                                "title": str(title),
                                "section_header": str(section_header) if section_header is not None else "",
                                "persona": str(persona),
                                "source_type": str(source_type),
                                "header_level": safe_int(header_level),
                                "pdf_page": safe_int(pdf_page),
                            }
                            
                            batch_documents.append(chunk)
                            batch_metadatas.append(meta)
                            batch_ids.append(chunk_id)

                        # Check if batch is full
                        if len(batch_documents) >= BATCH_SIZE:
                            collection.add(
                                documents=batch_documents,
                                metadatas=batch_metadatas,
                                ids=batch_ids
                            )
                            # Update counts
                            count += len(batch_ids) # Approximate record count (chunks)
                            # Clear batch
                            batch_documents = []
                            batch_metadatas = []
                            batch_ids = []
                            print(f"Processed batch... Total chunks: {count}", flush=True)

                        # Update source counts (approximate based on lines processed)
                        if source_type == "pdf":
                            pdf_count += 1
                        else:
                            web_count += 1
                            
                    except Exception as loop_e:
                        print(f"❌ Error on line {line_idx}: {loop_e}")
                        continue
            
            # Process remaining items in batch
            if batch_documents:
                collection.add(
                    documents=batch_documents,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
                count += len(batch_ids)
                print(f"Processed final batch... Total chunks: {count}", flush=True)
            
            return f"Successfully ingested {count} entries into ChromaDB ({web_count} web pages, {pdf_count} PDF chunks) with enhanced metadata (anchor URLs, personas, section headers) using nomic-embed-text."
        except Exception as e:
            import traceback
            traceback.print_exc()
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
            import chromadb.utils.embedding_functions as embedding_functions

            chroma_path = os.path.join(os.path.dirname(__file__), "chroma_db")
            client = chromadb.PersistentClient(path=chroma_path)
            
            # Use Ollama embeddings (nomic-embed-text) matches ingestion
            ollama_ef = embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text",
                url="http://127.0.0.1:11435/api/embeddings"
            )

            collection = client.get_collection(
                name="nku_docs",
                embedding_function=ollama_ef
            )
            
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
