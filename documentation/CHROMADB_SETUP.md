# ChromaDB Setup Guide

## Overview

ChromaDB is used to store vector embeddings of campus data for:

1. **RAG System**: Semantic search for student questions
2. **RAFT Generation**: Finding realistic distractors

## Setup Steps

### 1. Start Ollama

ChromaDB uses Ollama for embeddings:

```powershell
ollama serve
```

Keep this running in a separate terminal.

### 2. Verify Models

Check available models:

```powershell
ollama list
```

You should see models like `gemma3:12b` or similar.

### 3. Run Ingestion

From project root:

```bash
uv run python 02_rag_system/main.py ingest
```

This will:

- Read `01_crawling/combined_campus_data.jsonl`
- Filter out error pages
- Chunk text appropriately
- Generate embeddings
- Store in `02_rag_system/chroma_db`

### 4. Verify Ingestion

Check if ChromaDB was created:

```bash
uv run python 02_rag_system/verify_chromadb.py
```

Expected output:

```
✓ Connected to ChromaDB (1800+ documents)
✓ Test query returns results
```

## Configuration

### Ollama Settings (`02_rag_system/agents.py`)

```python
kownledge_llm = LLM(
    model="ollama/gemma3:12b",
    base_url="http://127.0.0.1:11434",  # Default Ollama port
    api_key="NA"
)
```

### ChromaDB Path (`02_rag_system/tools.py`)

```python
chroma_path = os.path.join(os.path.dirname(__file__), "chroma_db")
client = chromadb.PersistentClient(path=chroma_path)
```

## Troubleshooting

### Error: "No connection could be made"

**Problem**: Ollama is not running

**Solution**:

```bash
ollama serve
```

### Error: "Model not found"

**Problem**: Model hasn't been pulled

**Solution**:

```bash
ollama pull gemma3:12b
```

### Error: "Collection not found"

**Problem**: Ingestion hasn't been run

**Solution**:

```bash
uv run python 02_rag_system/main.py ingest
```

### ChromaDB Directory Not Found

**Problem**: Wrong working directory

**Fix**: ChromaDB is always created at `02_rag_system/chroma_db` (absolute path)

## Data Quality

### What Gets Ingested

✅ Valid web pages
✅ PDF content with page numbers
✅ FAQ entries
✅ Text with proper length (200+ chars)

### What Gets Filtered

❌ Error pages (404, "Page Not Found")
❌ Boilerplate content
❌ Very short snippets (<200 chars)
❌ Extremely long chunks (>3000 chars)

## Re-ingestion

If you update the source data:

1. **Regenerate combined dataset**:

   ```bash
   cd 01_crawling
   python master_scraper.py --merge-only
   ```

2. **Re-ingest into ChromaDB**:
   ```bash
   cd ..
   uv run python 02_rag_system/main.py ingest
   ```

The ingestion will overwrite the existing collection.

## Usage After Setup

### RAG System (Q&A)

```bash
uv run python 02_rag_system/main.py qa
```

### RAFT Generation

```bash
cd 03_fine_tuning
uv run python generate_raft_focused.py
```

ChromaDB will be used to find similar chunks as distractors.
