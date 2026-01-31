# Campus GPT Backend API

FastAPI backend that integrates the CrewAI-based RAG system with the frontend UI.

## Features

- 🚀 RESTful API with FastAPI
- 💬 Chat endpoint for student questions
- 📡 Server-Sent Events (SSE) for streaming responses
- 🔍 RAG-powered answers using ChromaDB and Ollama
- 🏥 Health check endpoint
- 🌐 CORS enabled for frontend communication

## Prerequisites

Before starting the backend, ensure you have:

1. **Ollama installed and running**

   ```bash
   # Start Ollama service (required!)
   ollama serve
   ```

2. **Victor Viking model loaded in Ollama**

   ```bash
   # Check if model exists
   ollama list

   # If not, create it from the Modelfile
   cd 04_deployment
   ollama create victor_viking -f Modelfile
   ```

3. **ChromaDB populated with data**
   ```bash
   # Run data ingestion (if not done already)
   uv run python 02_rag_system/main.py ingest
   ```

## Installation

Dependencies are managed via `pyproject.toml`. Install with:

```bash
uv sync
```

## Running the Backend

### Development Mode (with auto-reload)

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

The API will be available at:

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

### Production Mode

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check

```http
GET /health
```

Returns:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "rag_system": "operational"
}
```

### Chat

```http
POST /api/chat
Content-Type: application/json

{
  "question": "What are the admission requirements for NKU?"
}
```

Returns:

```json
{
  "answer": "To apply to NKU, you need...",
  "sources": [
    {
      "url": "https://nku.edu/admissions",
      "title": "Admissions"
    }
  ],
  "metadata": {
    "model": "victor_viking",
    "processing_time": 2.5
  }
}
```

### Streaming Chat

```http
POST /api/chat/stream
Content-Type: application/json

{
  "question": "What is NKU?"
}
```

Returns Server-Sent Events (SSE) stream with chunks of the answer.

## Testing

### Test Health Endpoint

```bash
# PowerShell
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content

# Bash/Linux
curl http://localhost:8000/health
```

### Test Chat Endpoint

```bash
# PowerShell
Invoke-WebRequest -Method POST -Uri http://localhost:8000/api/chat -ContentType "application/json" -Body '{"question": "What is NKU?"}' -UseBasicParsing | Select-Object -ExpandProperty Content

# Bash/Linux
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"question": "What is NKU?"}'
```

## CORS Configuration

The backend is configured to accept requests from:

- `http://localhost:5173` (Vite default)
- `http://localhost:3000` (Alternative React port)
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`

To add more origins, edit the `allow_origins` list in `backend/main.py`.

## Project Structure

```
backend/
├── __init__.py         # Package initialization
├── main.py            # FastAPI application
├── models.py          # Pydantic request/response models
├── rag_service.py     # RAG system integration
└── README.md          # This file
```

## Troubleshooting

### Ollama Connection Error

**Error**: `litellm.APIConnectionError: OllamaException - [WinError 10061]`

**Solution**: Start the Ollama service:

```bash
ollama serve
```

### ChromaDB Not Found

**Error**: `ChromaDB not found at...`

**Solution**: Run data ingestion:

```bash
uv run python 02_rag_system/main.py ingest
```

### CORS Errors in Frontend

If you get CORS errors in the browser console, verify:

1. The frontend URL is in the `allow_origins` list
2. The backend is running on port 8000
3. Both frontend and backend are running

## Integration with Frontend

The frontend should make requests to:

- Chat: `POST http://localhost:8000/api/chat`
- Streaming: `POST http://localhost:8000/api/chat/stream`

Example fetch request:

```javascript
const response = await fetch("http://localhost:8000/api/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    question: "What is NKU?",
  }),
});

const data = await response.json();
console.log(data.answer);
```

## License

Part of the Campus GPT project.
