from crewai import Agent, LLM
from tools import FileReadTool, ChromaIngestTool, ChromaSearchTool

# --- Configuration ---
# Use Ollama for the agents
# NOTE: Make sure Ollama is running: ollama serve
# You can change the model to any model you have pulled
kownledge_llm = LLM(
    model="ollama/llama3.1:8b-instruct-q8_0",  # Using gemma2:2b as default (small, fast)
    base_url="http://127.0.0.1:11435",  # Fixed: Ollama default port is 11434, not 11435
    api_key="NA"
)

# --- Agents ---

# 1. content_ingestion_agent
# Responsible for reading raw data and populating the knowledge base.
content_ingestion_agent = Agent(
    role='University Knowledge Architect',
    goal='Build a comprehensive and searchable knowledge base from university website data.',
    backstory="""You are an expert data engineer specializing in educational institutions. 
    Your job is to read raw data files (like JSONL from scrapers), understand the structure, 
    and store them efficiently in a vector database so that students can get accurate answers later.
    You are meticulous and ensure no data is lost.""",
    tools=[FileReadTool(), ChromaIngestTool()],
    verbose=True,
    memory=False,
    allow_delegation=False,
    llm=kownledge_llm
)

# 2. student_advisor_agent
# Responsible for answering user questions using the knowledge base.
student_advisor_agent = Agent(
    role='Student Success Advisor',
    goal='Provide accurate, helpful, and friendly answers to student questions using the university knowledge base.',
    backstory="""You are a friendly and knowledgeable advisor for Northern Kentucky University (NKU). 
    Students come to you with questions about admissions, tuition, courses, and campus life. 
    You principally rely on the 'Search Knowledge Base' tool to find facts. 
    If the information is missing, you honestly say you don't know but offer to help find out. 
    You never hallucinate facts.""",
    tools=[ChromaSearchTool()],
    verbose=False,  # Disabled for faster responses
    memory=False,  # Disabled for faster responses
    allow_delegation=False,
    llm=kownledge_llm
)
