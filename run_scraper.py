#!/usr/bin/env python3
"""
Script to run the NKU scraper with proper setup checks and error handling.
"""

import subprocess
import sys
from pathlib import Path
import importlib.util

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        'scrapy', 'beautifulsoup4', 'lxml', 'sentence_transformers', 
        'tiktoken', 'chromadb', 'tqdm', 'pypdf', 'python-docx'
    ]
    
    missing_packages = []
    for package in required_packages:
        # Handle package names that differ from import names
        import_name = package
        if package == 'python-docx':
            import_name = 'docx'
        elif package == 'beautifulsoup4':
            import_name = 'bs4'
        elif package == 'pypdf':
            import_name = 'pypdf'
            
        spec = importlib.util.find_spec(import_name)
        if spec is None:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing dependencies: {', '.join(missing_packages)}")
        print("📦 Install with: pip install -r crawler/requirements.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True

def setup_directories():
    """Create necessary output directories."""
    dirs = [
        "crawler/output",
        "crawler/output/text",
        "crawler/processed",
        "chroma_store"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {dir_path}")

def run_scraper():
    """Run the Scrapy spider."""
    print("🚀 Starting NKU scraper...")
    
    try:
        # Change to crawler/src directory and run scrapy
        result = subprocess.run([
            sys.executable, "-m", "scrapy", "crawl", "nku_info",
            "-o", "../output/scraped_data.json"
        ], 
        cwd="crawler/src",
        capture_output=True,
        text=True
        )
        
        if result.returncode == 0:
            print("✅ Scraping completed successfully!")
            print("📊 Output saved to: crawler/output/scraped_data.json")
            print("📊 Text files saved to: crawler/output/text/")
            return True
        else:
            print("❌ Scraping failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running scraper: {e}")
        return False

def main():
    print("🔍 NKU Campus Scraper Setup & Run")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup directories
    setup_directories()
    
    # Run scraper
    if run_scraper():
        print("\n🎉 Scraping completed! Next steps:")
        print("1. Run text extraction: python crawler/src/crawler/extractor.py")
        print("2. Ingest into ChromaDB: python crawler/src/crawler/data_ingest.py")
    else:
        print("\n❌ Scraping failed. Check the logs above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
