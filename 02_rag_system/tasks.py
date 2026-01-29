from crewai import Task
from agents import content_ingestion_agent, student_advisor_agent

# --- Tasks ---

def create_ingest_task(file_path: str):
    return Task(
        description=f"""
        1. Read the scrapped data from '{file_path}'.
        2. Process the content to extract meaningful text.
        3. Ingest the processed text into the ChromaDB vector store using the 'Ingest Knowledge Base' tool.
        Ensure that the ingestion reports a success status.
        """,
        expected_output="A confirmation message stating how many pages/documents were successfully ingested.",
        agent=content_ingestion_agent
    )

def create_qa_task(user_question: str):
    return Task(
        description=f"""
        The student has asked: "{user_question}"
        1. Use the 'Search Knowledge Base' tool to find relevant information about this topic.
        2. Synthesize the retrieved information into a clear, concise, and helpful answer.
        3. If the retrieved context mentions specific links or resources, include them.
        4. If the answer is not in the knowledge base, politely inform the student.
        """,
        expected_output="A helpful, accurate response to the student's question, based strictly on the retrieved context.",
        agent=student_advisor_agent
    )
