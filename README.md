**CampusGPT RAG Chatbot**  
*End-to-end deployed conversational AI for Northern Kentucky University information.*  

---

## Overview  
CampusGPT is a fully deployed Retrieval‑Augmented Generation (RAG) chatbot that delivers accurate, up‑to‑date answers about Northern Kentucky University. By combining automated web scraping, vector search, and generative AI, it grounds its responses in official university content and cites sources for transparency.

## Key Features  

- **Automated Corpus Refresh**: Scheduled crawlers ingest and update content from NKU’s public website, ensuring CampusGPT stays current.  
- **Hybrid Retrieval**: A fixed-weight blend of BM25 and dense embeddings fetches the most relevant passages.  
- **Lightweight Reranking**: An optional cross‑encoder can be toggled for deeper semantic scoring on top candidates.  
- **Chain‑of‑Thought Generation**: Fusion‑in‑Decoder (FiD) jointly attends across multiple passages to produce coherent, context‑rich answers.  
- **Transparent Citations**: Every answer includes the exact snippet and source metadata, fostering trust and accountability.  

## Architecture  
```
[User Query]
     ↓
[Query Rewriter] → Flan‑T5‑Small
     ↓
[Hybrid Retriever] → (BM25 + Vector Search)
     ↓
[Optional Cross‑Encoder Rerank]
     ↓
[FiD Reader] → T5‑Base Fusion‑in‑Decoder
     ↓
[Generated Answer + Source Snippets]
```  

- **Vector Store**: Pinecone for 384‑dim embeddings, ChromaDB for full text.  
- **Embedding Models**: Sentence-Transformers MiniLM for retrieval; cross‑encoder for rerank.  
- **Generation Models**: DeepSeek R1.

## Usage  
CampusGPT is accessible via a web UI or REST API endpoint:  
- **Web UI**: Navigate to the hosted URL and enter your question.  
- **API**: POST a JSON payload `{ "query": "..." }` to `/api/chat` and receive `{ "answer": "...", "sources": [...] }`.
- **Scraper**:  run the command : ``` poetry run scrapy crawl crawler -o crawl_meta.json ```

## Configuration & Environment  
All settings are controlled through environment variables—no additional installer scripts are required. Key variables include:  
- `PINECONE_API_KEY`  
- `PINECONE_REGION`  
- `CHROMA_PERSIST_DIR`  
- `MODEL_NAME` (DeepSeek R1)

## Monitoring & Maintenance  
- **Daily Crawls**: Content pipeline runs automatically to refresh the knowledge base.  
- **Health Checks**: Uptime and response‑time monitoring for all services.  
- **Metrics Dashboard**: Tracks latency, throughput, and user feedback for continuous improvement.  
- **Feedback Loop**: User up/down votes feed into periodic retriever fine‑tuning.

## License & Acknowledgments  
CampusGPT is released under the **MIT License**. We gratefully acknowledge the following core technologies and libraries:  
- Pinecone Vector Database  
- ChromaDB Document Store  
- Sentence‑Transformers & Cross‑Encoder  
- Hugging Face Transformers & Accelerate  
- BitsAndBytes Quantization  
- T5 & Fusion‑in‑Decoder  
- Streamlit (UI framework)

