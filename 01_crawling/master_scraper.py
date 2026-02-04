"""
Master Scraper - Unified Web + PDF Scraping with Parallel Processing
=====================================================================

This orchestrator runs both web scraping and PDF extraction in parallel,
then combines the results into a single comprehensive dataset.

Usage:
    python master_scraper.py

Features:
- Parallel execution of web and PDF scrapers
- Real-time progress monitoring
- Automatic result merging
- Comprehensive logging
"""

import asyncio
import json
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

# Import our scrapers
from scraper import main as web_scraper_main
from pdf_scraper import main as pdf_scraper_main


def run_web_scraper():
    """Run the web scraper in a separate process."""
    print("\n" + "="*60)
    print("STARTING WEB SCRAPER")
    print("="*60)
    start_time = time.time()
    
    try:
        # Run the web scraper
        asyncio.run(web_scraper_main())
        
        elapsed = time.time() - start_time
        print(f"\nWeb scraper completed in {elapsed:.2f} seconds")
        return {"status": "success", "type": "web", "time": elapsed}
    
    except Exception as e:
        print(f"\nWeb scraper failed: {str(e)}")
        return {"status": "error", "type": "web", "error": str(e)}


def run_pdf_scraper():
    """Run the PDF scraper in a separate process."""
    print("\n" + "="*60)
    print("STARTING PDF SCRAPER")
    print("="*60)
    start_time = time.time()
    
    try:
        # Run the PDF scraper
        pdf_scraper_main()
        
        elapsed = time.time() - start_time
        print(f"\nPDF scraper completed in {elapsed:.2f} seconds")
        return {"status": "success", "type": "pdf", "time": elapsed}
    
    except Exception as e:
        print(f"\nPDF scraper failed: {str(e)}")
        return {"status": "error", "type": "pdf", "error": str(e)}


def merge_outputs(web_file="campus_data.jsonl", pdf_file="campus_pdfs.jsonl", output_file="combined_campus_data.jsonl"):
    """
    Merge web scraping and PDF extraction outputs into a single file.
    Filters out error pages (404, etc.) during the merge process.
    
    Args:
        web_file: Path to web scraping output
        pdf_file: Path to PDF extraction output
        output_file: Path to combined output file
        
    Returns:
        Dictionary with merge statistics
    """
    print("\n" + "="*60)
    print("MERGING OUTPUTS")
    print("="*60)
    
    def is_error_page(entry):
        """Check if entry is an error page (404, etc.)."""
        title = entry.get("title", "").lower()
        text = entry.get("text", "").lower()[:200]  # Check first 200 chars
        
        error_indicators = [
            "page not found", "404", "error", 
            "not available", "does not exist", 
            "could not be found", "page you requested could not be found"
        ]
        
        return any(ind in title for ind in error_indicators) or \
               any(ind in text for ind in error_indicators)
    
    web_entries = []
    pdf_entries = []
    filtered_web = 0
    filtered_pdf = 0
    
    # Load web scraping data with filtering
    if Path(web_file).exists():
        with open(web_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                if not is_error_page(entry):
                    web_entries.append(entry)
                else:
                    filtered_web += 1
        print(f"Loaded {len(web_entries)} entries from web scraper ({filtered_web} error pages filtered)")
    else:
        print(f"Warning: {web_file} not found")
    
    # Load PDF data (PDFs typically don't have error pages, but check anyway)
    if Path(pdf_file).exists():
        with open(pdf_file, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                if not is_error_page(entry):
                    pdf_entries.append(entry)
                else:
                    filtered_pdf += 1
        print(f"Loaded {len(pdf_entries)} entries from PDF scraper ({filtered_pdf} error pages filtered)")
    else:
        print(f"Warning: {pdf_file} not found")
    
    # Combine
    all_entries = web_entries + pdf_entries
    
    # Save combined output
    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in all_entries:
            f.write(json.dumps(entry) + '\n')
    
    print(f"\nSaved {len(all_entries)} total entries to {output_file}")
    print(f"Filtered out {filtered_web + filtered_pdf} error pages")
    
    return {
        "web_count": len(web_entries),
        "pdf_count": len(pdf_entries),
        "total_count": len(all_entries),
        "filtered_count": filtered_web + filtered_pdf,
        "output_file": output_file
    }


def print_summary(results, merge_stats, total_time):
    """Print final summary of scraping operation."""
    print("\n" + "="*60)
    print("SCRAPING COMPLETE - SUMMARY")
    print("="*60)
    
    # Scraper results
    for result in results:
        status_icon = "✓" if result["status"] == "success" else "✗"
        print(f"\n{result['type'].upper()} Scraper: {status_icon} {result['status'].upper()}")
        if result["status"] == "success":
            print(f"  Time: {result['time']:.2f} seconds")
        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")
    
    # Merge statistics
    print(f"\nDATA COLLECTED:")
    print(f"  Web entries: {merge_stats['web_count']}")
    print(f"  PDF entries: {merge_stats['pdf_count']}")
    print(f"  Error pages filtered: {merge_stats.get('filtered_count', 0)}")
    print(f"  Total valid entries: {merge_stats['total_count']}")
    
    print(f"\nOUTPUT FILES:")
    print(f"  Web: campus_data.jsonl")
    print(f"  PDF: campus_pdfs.jsonl")
    print(f"  Combined (clean): {merge_stats['output_file']}")
    
    print(f"\nTOTAL TIME: {total_time:.2f} seconds")
    print("="*60)


def main():
    """Main orchestrator: run scrapers in parallel and merge results."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Campus GPT Master Scraper")
    parser.add_argument("--merge-only", action="store_true", 
                       help="Only merge existing files (skip scraping)")
    args = parser.parse_args()
    
    if args.merge_only:
        # Just merge existing files with error filtering
        print("\n" + "="*60)
        print("MERGE-ONLY MODE: Regenerating Combined Dataset")
        print("="*60)
        
        merge_stats = merge_outputs()
        
        print("\n" + "="*60)
        print("✅ MERGE COMPLETE")
        print("="*60)
        print(f"Web entries: {merge_stats['web_count']}")
        print(f"PDF entries: {merge_stats['pdf_count']}")
        print(f"Error pages filtered: {merge_stats.get('filtered_count', 0)}")
        print(f"Total valid entries: {merge_stats['total_count']}")
        print(f"\n💾 Saved to: {merge_stats['output_file']}")
        print("="*60)
        
        print("\n💡 Next steps:")
        print("   1. Re-ingest into ChromaDB: uv run python 02_rag_system/main.py ingest")
        print("   2. Generate RAFT dataset: cd 03_fine_tuning && python generate_raft_focused.py")
        return
    
    # Normal mode: run scrapers then merge
    print("\n" + "="*60)
    print("CAMPUS GPT MASTER SCRAPER")
    print("Running Web + PDF Scrapers in Parallel")
    print("="*60)
    
    overall_start = time.time()
    
    # Run both scrapers in parallel using ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        future_web = executor.submit(run_web_scraper)
        future_pdf = executor.submit(run_pdf_scraper)
        
        # Collect results as they complete
        results = []
        for future in as_completed([future_web, future_pdf]):
            result = future.result()
            results.append(result)
    
    # Merge outputs
    merge_stats = merge_outputs()
    
    # Calculate total time
    total_time = time.time() - overall_start
    
    # Print summary
    print_summary(results, merge_stats, total_time)
    
    # Exit with error code if any scraper failed
    if any(r["status"] == "error" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
