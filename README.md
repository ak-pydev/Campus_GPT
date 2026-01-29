# Campus GPT

Welcome to **Campus GPT**, your intelligent assistant dedicated to navigating the wealth of information at Northern Kentucky University (NKU).

This project isn't just another chatbot; it's a specialized system designed to understand the specific context of our campus. deeper than generic models can. By leveraging advanced web crawling, RAG (Retrieval-Augmented Generation), and fine-tuned large language models, Campus GPT aims to provide accurate, timely, and relevant answers to everything from course details to campus events.

## How It Works

We've broken down the project into four main phases to ensure a robust and scalable system:

1.  **Data Acquisition (`01_crawling`)**: We start by gathering public information from NKU's websites using specialized scrapers. This raw data is then cleaned and formatted, serving as the knowledge base foundation.
2.  **Knowledge Retrieval (`02_rag_system`)**: Accessing information quickly is key. We use a RAG system to chunk, embed, and store our data in a vector database. This allows the bot to "read" relevant documents before answering a question.
3.  **Brain Training (`03_fine_tuning`)**: To make the AI truly understand the campus dialect and nuances, we fine-tune a Llama 3.1 8B model. This involves generating a custom dataset and training the model to prioritize our specific domain knowledge.
4.  **Deployment (`04_deployment`)**: Finally, we wrap everything in a user-friendly Streamlit interface, making it easy for anyone to interact with Campus GPT.

## Getting Started

Check out the `requirements.txt` to see what powers this project. You'll need `unsloth`, `ollama`, `crawl4ai`, and a few other libraries to get up and running.

Feel free to explore the directories to see how each part of the system is built. We're excited to see how this project evolves to help the campus community!
