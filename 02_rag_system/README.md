# Campus GPT - RAG System Integration

Welcome to the **Retrieval-Augmented Generation (RAG)** module of Campus GPT. This system is designed to be the "brain" of our application, responsible for learning from university data and answering student questions accurately.

Instead of a traditional script, we use an **agent-based approach** powered by **CrewAI**. Think of it as hiring two specialized virtual employees to handle the workload.

## 🤖 Meet the Team

We have defined two specialized agents to handle the work:

### 1. The Knowledge Architect (`IngestionAgent`)
*   **Role:** Data Engineer & Librarian.
*   **Job:** Reads the raw data scraped from the website, organizes it, and files it away into our vector database (ChromaDB).
*   **Why:** Ensures that the information we rely on is clean, structured, and easy to find later.

### 2. The Student Advisor (`QAAgent`)
*   **Role:** Student Success Specialist.
*   **Job:** Listens to student questions, searches the database for the exact answers, and formulates a helpful response.
*   **Why:** Provides accurate answers based strictly on facts, ensuring students get reliable information.

---

## 🛠️ How It Works

1.  **Ingestion Phase**:
    *   The **Knowledge Architect** takes the `campus_data.jsonl` file.
    *   It breaks the text down into small, meaningful "chunks."
    *   These chunks are stored in **ChromaDB**, which acts as our long-term memory.

2.  **Retrieval Phase (Q&A)**:
    *   A student asks a question (e.g., *"How much is tuition?"*).
    *   The **Student Advisor** searches ChromaDB for the most relevant documents.
    *   It reads those documents and writes a clear, natural answer for the student.

---

## 🚀 How to Run

We have a single entry point for this system: `main.py`.

### To Build the Knowledge Base (Ingest Data):
Run this command once (or whenever you have new scraped data) to populate the database.
```bash
uv run python 02_rag_system/main.py ingest
```

### To Ask Questions (Test Mode):
Run this command to chat with the Student Advisor in your terminal.
```bash
uv run python 02_rag_system/main.py qa
```

---

*Powered by CrewAI, ChromaDB, and Sentence Transformers.*
