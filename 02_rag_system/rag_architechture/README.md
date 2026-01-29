# Campus GPT - RAG Agent Architecture

## Overview
This directory (`rag_architechture`) contains the blueprint for our Retrieval-Augmented Generation system. 
(Note: The actual vector database storage might also be located here or in `chroma_db` depending on configuration).

## 🧠 The Agentic Brain
We use **CrewAI** to orchestrate intelligent agents that handle knowledge processing and student interaction.

### The Agents
| Agent Name | Role | Responsibilities |
| :--- | :--- | :--- |
| **IngestionAgent** | *Knowledge Architect* | 1. Reads raw `jsonl` data.<br>2. Slices text into semantic chunks.<br>3. Stores vectors in ChromaDB. |
| **QAAgent** | *Student Advisor* | 1. Receives student queries.<br>2. Searches ChromaDB for facts.<br>3. Synthesizes human-friendly answers. |

## 📂 Data Flow
1.  **Raw Data** (`campus_data.jsonl`) $\rightarrow$ **Ingestion Tool**
2.  **Ingestion Tool** $\rightarrow$ **Vector Database** (ChromaDB)
3.  **Student Question** $\rightarrow$ **Search Tool** $\rightarrow$ **Final Answer**

## 🚀 Usage
From the project root:

**Ingest Data:**
```bash
uv run python 02_rag_system/main.py ingest
```

**Ask a Question:**
```bash
uv run python 02_rag_system/main.py qa
```

---
*Architecture implemented using CrewAI, ChromaDB, and Python 3.11/uv.*
