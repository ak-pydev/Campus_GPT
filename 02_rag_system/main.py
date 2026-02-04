import sys
import os
from crewai import Crew, Process
from agents import content_ingestion_agent, student_advisor_agent
from tasks import create_ingest_task, create_qa_task

def run_ingestion():
    print("\n--- Starting Ingestion Process ---")
    print("Loading combined web + PDF dataset...")
    
    # Use absolute path based on this file's location
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "01_crawling", "combined_campus_data.jsonl")
    
    # Fallback to old paths if combined doesn't exist
    if not os.path.exists(file_path):
        print(f"⚠️ Combined dataset not found at {file_path}")
        print("Trying legacy path...")
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "campus_data.jsonl")
        
        if not os.path.exists(file_path):
            print(f"❌ Error: No data file found.")
            print(f"💡 Run the master scraper first: cd 01_crawling && python master_scraper.py")
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
