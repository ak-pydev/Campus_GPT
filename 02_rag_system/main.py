import sys
import os
from crewai import Crew, Process
from agents import content_ingestion_agent, student_advisor_agent
from tasks import create_ingest_task, create_qa_task

def run_ingestion():
    print("\n--- Starting Ingestion Process ---")
    file_path = "campus_data.jsonl" # Assuming root dir
    if not os.path.exists(file_path):
         # Try looking one level up if running from inside 02_rag_system
        if os.path.exists(f"../{file_path}"):
            file_path = f"../{file_path}"
        else:
            print(f"Error: {file_path} not found.")
            return

    ingest_task = create_ingest_task(file_path)
    crew = Crew(
        agents=[content_ingestion_agent],
        tasks=[ingest_task],
        verbose=True,
        process=Process.sequential
    )
    result = crew.kickoff()
    print("\n--- Ingestion Complete ---")
    print(result)

def run_qa():
    print("\n--- Student Advisor System ---")
    print("Type 'exit' to quit.")
    
    while True:
        question = input("\nStudent Question: ")
        if question.lower() in ['exit', 'quit', 'q']:
            break
            
        qa_task = create_qa_task(question)
        crew = Crew(
            agents=[student_advisor_agent],
            tasks=[qa_task],
            verbose=True,
            process=Process.sequential
        )
        result = crew.kickoff()
        print("\nAdvisor Answer:\n")
        print(result)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'ingest':
        run_ingestion()
    elif len(sys.argv) > 1 and sys.argv[1] == 'qa':
        run_qa()
    else:
        print("Usage: python main.py [ingest|qa]")
        print("Defaulting to QA mode...")
        run_qa()
