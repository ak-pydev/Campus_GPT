# Campus GPT 🎓

**Your Intelligent AI Companion for Northern Kentucky University.**

Campus GPT goes beyond a simple chatbot. It is a sophisticated, agent-based AI system capable of reading, understanding, and answering questions about university life with high accuracy. By combining **web scraping**, **retrieval-augmented generation (RAG)**, and **large language models**, we bring the campus knowledge base to your fingertips.

---

## 🏗️ System Architecture

Our system is organized into four intelligent modules:

### 1. Data Acquisition (`01_crawling`)
*   **The Foundation**: Specialized web scrapers (using `crawl4ai`) that traverse university domains.
*   **Goal**: Harvest raw text data to build a comprehensive knowledge base.

### 2. The Agentic Brain (`02_rag_system`)
*   **The Engine**: Powered by **CrewAI**.
*   **How it Works**: We employ autonomous agents—an **Ingestion Agent** to organize data and a **Student Advisor Agent** to answer questions. They work together using **ChromaDB** to ensure every answer is grounded in fact.

### 3. Fine-Tuning (`03_fine_tuning`)
*   **The Personality**: Adapting the Llama 3.1 model to understand the specific "campus dialect" and nuances of university queries.

### 4. User Experience (`04_deployment`)
*   **The Interface**: A clean, accessible endpoint for students to interact with the AI.

---

## ⚡ Tech Stack

*   **Framework**: Python 3.11+
*   **Agent Orchestration**: CrewAI
*   **Vector Database**: ChromaDB
*   **LLM Engine**: Ollama (Llama 3.x)
*   **Package Manager**: `uv` (Fast & Modern)

---

## 🚀 Getting Started

We use `uv` for lightning-fast dependency management.

### 1. Setup
```bash
pip install uv
uv sync
```

### 2. Build the Knowledge Base
Train the agents on the latest data:
```bash
uv run python 02_rag_system/main.py ingest
```

### 3. Ask a Question
Start a chat session with the Student Advisor:
```bash
uv run python 02_rag_system/main.py qa
```

---
*Built with ❤️ for the NKU Community.*
