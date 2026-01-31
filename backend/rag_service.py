"""
RAG Service - Wraps the CrewAI-based RAG system for API use
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any
import asyncio
from functools import partial

# Add parent directory to path to import from 02_rag_system
current_dir = Path(__file__).parent
project_root = current_dir.parent
rag_system_path = project_root / "02_rag_system"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(rag_system_path))

# Import from 02_rag_system
from crewai import Crew, Process

# Import agents and tasks from 02_rag_system
import importlib.util

# Load agents module
agents_spec = importlib.util.spec_from_file_location("agents", rag_system_path / "agents.py")
agents_module = importlib.util.module_from_spec(agents_spec)
agents_spec.loader.exec_module(agents_module)

# Load tasks module
tasks_spec = importlib.util.spec_from_file_location("tasks", rag_system_path / "tasks.py")
tasks_module = importlib.util.module_from_spec(tasks_spec)
tasks_spec.loader.exec_module(tasks_module)

student_advisor_agent = agents_module.student_advisor_agent
create_qa_task = tasks_module.create_qa_task


class RAGService:
    """Service class to interact with the RAG system"""
    
    def __init__(self):
        """Initialize the RAG service"""
        self.agent = student_advisor_agent
        self.project_root = project_root
        
        # Ensure ChromaDB path is correct
        self.chroma_path = self.project_root / "chroma_db"
        if not self.chroma_path.exists():
            raise RuntimeError(
                f"ChromaDB not found at {self.chroma_path}. "
                "Please run ingestion first: python 02_rag_system/main.py ingest"
            )
    
    def get_answer(self, question: str) -> Dict[str, Any]:
        """
        Get answer from RAG system for a given question
        
        Args:
            question: The student's question
            
        Returns:
            Dictionary containing answer and metadata
        """
        try:
            # Create QA task
            qa_task = create_qa_task(question)
            
            # Create and run crew
            crew = Crew(
                agents=[self.agent],
                tasks=[qa_task],
                verbose=False,  # Set to False for API usage
                process=Process.sequential
            )
            
            # Execute and get result
            result = crew.kickoff()
            
            # Extract answer (CrewAI returns CrewOutput object)
            answer_text = str(result)
            
            return {
                "answer": answer_text,
                "sources": self._extract_sources(answer_text),
                "metadata": {
                    "model": "victor_viking",
                    "agent": "student_advisor"
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"RAG system error: {str(e)}")
    
    async def get_answer_async(self, question: str) -> Dict[str, Any]:
        """
        Async wrapper for get_answer
        
        Args:
            question: The student's question
            
        Returns:
            Dictionary containing answer and metadata
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            partial(self.get_answer, question)
        )
    
    def _extract_sources(self, answer: str) -> list:
        """
        Extract source URLs from the answer text
        
        Args:
            answer: The answer text that may contain sources
            
        Returns:
            List of source dictionaries
        """
        sources = []
        
        # Look for patterns like "Source: Title (URL)"
        # This is a simple extraction - can be enhanced
        lines = answer.split('\n')
        for line in lines:
            if 'Source:' in line or 'http' in line:
                # Basic extraction - can be improved with regex
                if 'http' in line:
                    # Try to extract URL and title
                    parts = line.split('http')
                    if len(parts) > 1:
                        url = 'http' + parts[1].split(')')[0].strip()
                        title = parts[0].replace('Source:', '').strip()
                        sources.append({
                            "url": url,
                            "title": title if title else "University Resource"
                        })
        
        return sources if sources else None
    
    def health_check(self) -> Dict[str, str]:
        """
        Check if RAG system is operational
        
        Returns:
            Dictionary with health status
        """
        try:
            # Check if ChromaDB exists
            if not self.chroma_path.exists():
                return {"status": "unhealthy", "reason": "ChromaDB not found"}
            
            # Check if agent is initialized
            if self.agent is None:
                return {"status": "unhealthy", "reason": "Agent not initialized"}
            
            return {"status": "operational"}
            
        except Exception as e:
            return {"status": "unhealthy", "reason": str(e)}


# Singleton instance
_rag_service_instance = None


def get_rag_service() -> RAGService:
    """
    Get or create RAG service singleton
    
    Returns:
        RAGService instance
    """
    global _rag_service_instance
    
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    
    return _rag_service_instance
