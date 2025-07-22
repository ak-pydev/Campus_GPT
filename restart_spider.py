#!/usr/bin/env python3
"""
Recovery script to restart the spider from the last checkpoint.
Handles graceful recovery after crashes or interruptions.
"""

import json
import pickle
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def check_checkpoint_status():
    """Check the current checkpoint status and provide recovery options."""
    checkpoint_file = Path("crawler_checkpoint.pkl")
    visited_urls_file = Path("visited_urls.json")
    
    print("🔍 CampusGPT Spider Recovery Tool")
    print("=" * 50)
    
    if not checkpoint_file.exists() and not visited_urls_file.exists():
        print("❌ No checkpoint files found. Starting fresh crawl.")
        return None, 0, 0, 0
    
    pages_scraped = 0
    visited_count = 0
    failed_count = 0
    last_updated = None
    
    try:
        if checkpoint_file.exists():
            with open(checkpoint_file, 'rb') as f:
                checkpoint = pickle.load(f)
                pages_scraped = checkpoint.get('pages_scraped', 0)
                visited_count = len(checkpoint.get('visited_urls', []))
                failed_count = len(checkpoint.get('failed_urls', []))
                last_updated = checkpoint.get('timestamp')
            print(f"✅ Binary checkpoint found: {pages_scraped} pages scraped")
            
        if visited_urls_file.exists():
            with open(visited_urls_file, 'r') as f:
                data = json.load(f)
                pages_scraped = data.get('pages_scraped', pages_scraped)
                visited_count = len(data.get('visited', []))
                failed_count = len(data.get('failed', []))
                last_updated = data.get('last_updated', last_updated)
            print(f"✅ JSON checkpoint found: {pages_scraped} pages scraped")
        
        print(f"📊 Status Summary:")
        print(f"   - Pages scraped: {pages_scraped}")
        print(f"   - URLs visited: {visited_count}")
        print(f"   - Failed URLs: {failed_count}")
        if last_updated:
            print(f"   - Last updated: {last_updated}")
            
        return last_updated, pages_scraped, visited_count, failed_count
        
    except Exception as e:
        print(f"❌ Error reading checkpoint: {e}")
        return None, 0, 0, 0

def clean_checkpoints():
    """Remove existing checkpoint files to start fresh."""
    files_to_remove = [
        "crawler_checkpoint.pkl",
        "visited_urls.json"
    ]
    
    removed = 0
    for file_path in files_to_remove:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            removed += 1
            print(f"🗑️ Removed: {file_path}")
    
    if removed > 0:
        print(f"✅ Cleaned {removed} checkpoint files")
    else:
        print("ℹ️ No checkpoint files to clean")

def run_spider_with_recovery():
    """Run the spider with recovery enabled."""
    print("🚀 Starting spider with recovery mode...")
    
    try:
        # Change to crawler/src directory and run scrapy
        result = subprocess.run([
            sys.executable, "-m", "scrapy", "crawl", "nku_info",
            "-o", "../output/scraped_data.json",
            "-s", "LOG_LEVEL=INFO"
        ], 
        cwd="crawler/src",
        text=True
        )
        
        if result.returncode == 0:
            print("✅ Spider completed successfully!")
            return True
        else:
            print(f"❌ Spider failed with return code: {result.returncode}")
            return False
            
    except KeyboardInterrupt:
        print("\n⚠️ Spider interrupted by user. Checkpoint saved.")
        return False
    except Exception as e:
        print(f"❌ Error running spider: {e}")
        return False

def main():
    print("🕷️ CampusGPT Spider Recovery System")
    print("=" * 50)
    
    # Check current status
    last_updated, pages_scraped, visited_count, failed_count = check_checkpoint_status()
    
    if pages_scraped > 0:
        print("\n🔄 Recovery Options:")
        print("1. Continue from checkpoint (recommended)")
        print("2. Start fresh (clears all progress)")
        print("3. Show detailed checkpoint info")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            print(f"\n✅ Continuing from checkpoint ({pages_scraped} pages already scraped)")
            run_spider_with_recovery()
            
        elif choice == "2":
            confirm = input("⚠️ This will delete all progress. Continue? (y/N): ").strip().lower()
            if confirm == 'y':
                clean_checkpoints()
                run_spider_with_recovery()
            else:
                print("❌ Cancelled")
                
        elif choice == "3":
            # Show detailed checkpoint info
            print("\n📋 Detailed Checkpoint Information:")
            try:
                if Path("visited_urls.json").exists():
                    with open("visited_urls.json", 'r') as f:
                        data = json.load(f)
                        print(f"   - Last updated: {data.get('last_updated', 'Unknown')}")
                        print(f"   - Pages scraped: {data.get('pages_scraped', 0)}")
                        print(f"   - Unique URLs visited: {len(data.get('visited', []))}")
                        print(f"   - Failed requests: {len(data.get('failed', []))}")
                        
                        if data.get('failed'):
                            print(f"   - Sample failed URLs:")
                            for i, url_hash in enumerate(list(data.get('failed', []))[:3]):
                                print(f"     {i+1}. Hash: {url_hash[:16]}...")
                                
            except Exception as e:
                print(f"❌ Error reading detailed info: {e}")
                
        elif choice == "4":
            print("👋 Goodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid choice")
    else:
        print("\n🆕 No previous crawl found. Starting fresh...")
        run_spider_with_recovery()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted. Checkpoint files preserved.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
