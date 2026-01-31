# Campus GPT 🎓

**Your Intelligent AI Companion for Northern Kentucky University.**

Campus GPT is an advanced, open-source style AI agent designed to assist students by answering questions about university life, academic requirements, and campus policies. It leverages state-of-the-art techniques including **RAG (Retrieval-Augmented Generation)** and **RAFT (Retrieval-Augmented Fine-Tuning)** to provide accurate, context-aware responses.

---

## 🛠️ Concepts & Tools

This project integrates several cutting-edge AI technologies and libraries to create a robust student advisor system.

### 1. Data Collection & Processing
*   **Tools Used**: `crawl4ai`, `BeautifulSoup4`, `Requests`
*   **Process**: We employ high-performance asynchronous web crawlers (`crawl4ai`) to traverse university domains and extract raw text. This data is cleaned and structured into JSONL formats, serving as the ground truth for our knowledge base.

### 2. RAG (Retrieval-Augmented Generation)
*   **Tools Used**: `CrewAI`, `ChromaDB`, `Sentence-Transformers`
*   **Concept**: RAG allows our AI to "look up" information before answering.
    *   **Vector Database**: We use **ChromaDB** to index university data.
    *   **Orchestration**: **CrewAI** manages a team of agents (Ingestion Agent, Student Advisor Agent) that coordinate to search the database and synthesize answers.

### 3. RAFT (Retrieval-Augmented Fine-Tuning)
*   **Tools Used**: `Unsloth`, `Llama 3.1`, `PyTorch`
*   **Concept**: We don't just use a generic model. We implement **RAFT** techniques to fine-tune **Llama 3.1** on our specific domain data.
    *   **Fine-Tuning**: Using **Unsloth** for efficient, memory-friendly training (LoRA/QLoRA), we create a model that understands the specific terminology and context of NKU.

### 4. Custom Model Deployment
*   **Tools Used**: `Ollama`, `Modelfile`
*   **Concept**: The fine-tuned weights are exported and packaged into a custom GGUF model named `campus-gpt`.
    *   **Modelfile**: Defines the system prompt, parameters, and template to ensure the model behaves consistently as a helpful campus guide.
    *   **Ollama**: Serves the model locally, providing a fast and private inference engine.

### 5. User Interface
*   **Tools Used**: `Streamlit`
*   **Frontend**: A clean, responsive web interface built with Streamlit allows students to easily chat with Campus GPT.

---

## 📦 Tech Stack

*   **Language**: Python 3.11+
*   **LLM**: Llama 3.1 (via Ollama)
*   **Agents**: CrewAI
*   **Database**: ChromaDB (Vector Store)
*   **Crawling**: Crawl4AI
*   **Fine-Tuning**: Unsloth
*   **Dependency Management**: `uv`

---

## 🚀 Getting Started

We use `uv` for lightning-fast dependency management.

### 1. Setup
```bash
pip install uv
uv sync
```

### 2. Build the Model
Ensure you have Ollama installed and the GGUF file ready.
```bash
cd 04_deployment
ollama create campus-gpt -f Modelfile
```

### 3. Injest Data (RAG)
Populate the vector database with the latest campus data:
```bash
uv run python 02_rag_system/main.py ingest
```

### 4. Run the Advisor
Start the command-line interface:
```bash
uv run python 02_rag_system/main.py qa
```
Or run the web app:
```bash
streamlit run 04_deployment/app.py
```

---

*Built with ❤️ for the NKU Community.*
