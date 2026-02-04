"""
RAFT Dataset Generator - Proper Format with Oracle + Distractors
=================================================================

Generates RAFT examples in proper format:
- Oracle: The chunk that contains the answer
- Distractors: 3 similar chunks from ChromaDB that DON'T have the answer
- Question: Answerable ONLY by Oracle
- Thought Process: Chain-of-Thought comparing Oracle vs Distractors

Processes all valid content (error pages and boilerplate filtered).

Usage:
    python generate_raft_focused.py
"""

import json
import os
import time
import chromadb
import random
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
INPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "01_crawling", "combined_campus_data.jsonl")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "raft_dataset.jsonl")
CHROMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "02_rag_system", "chroma_db")
MODEL_NAME = "arcee-ai/trinity-large-preview:free"

# Quality filters
MIN_TEXT_LENGTH = 200  # Skip very short content
MAX_TEXT_LENGTH = 3000  # Skip extremely long content (likely noise)

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file. Please add it.")

# Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Initialize ChromaDB for finding distractors
print("🔧 Connecting to ChromaDB...")
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_collection(name="nku_docs")
    print(f"✓ Connected to ChromaDB ({chroma_collection.count()} documents)")
except Exception as e:
    print(f"❌ Failed to connect to ChromaDB: {e}")
    print("💡 Run ingestion first: uv run python 02_rag_system/main.py ingest")
    exit(1)


def get_distractors(oracle_text, num_distractors=3):
    """
    Find similar but incorrect chunks from ChromaDB.
    
    Args:
        oracle_text: The Oracle document text
        num_distractors: Number of distractors to return
    
    Returns:
        List of distractor texts
    """
    try:
        # Query ChromaDB for similar chunks
        results = chroma_collection.query(
            query_texts=[oracle_text],
            n_results=num_distractors + 10  # Get extras to filter out oracle
        )
        
        distractors = []
        for doc in results['documents'][0]:
            # Skip the oracle itself (exact match)
            if doc == oracle_text:
                continue
            
            # Skip very similar chunks (might be duplicates)
            if len(doc) < 100:
                continue
            
            distractors.append(doc)
            
            if len(distractors) >= num_distractors:
                break
        
        # If we don't have enough, pad with random chunks
        while len(distractors) < num_distractors:
            random_result = chroma_collection.get(
                limit=1,
                offset=random.randint(0, chroma_collection.count() - 1)
            )
            if random_result['documents'] and random_result['documents'][0] != oracle_text:
                distractors.append(random_result['documents'][0])
        
        return distractors[:num_distractors]
    
    except Exception as e:
        print(f"⚠️ Error getting distractors: {e}")
        return []


def should_process(entry):
    """
    Filter for valid content (excludes error pages and boilerplate).
    
    Returns:
        bool: True if entry should be processed
    """
    source_type = entry.get("source_type", "web")
    faq_category = entry.get("faq_category")
    text = entry.get("text", "")
    title = entry.get("title", "") or ""  # Handle None
    
    # Quality check: text length
    if len(text) < MIN_TEXT_LENGTH or len(text) > MAX_TEXT_LENGTH:
        return False
    
    # CRITICAL: Skip error pages (404, etc.)
    error_indicators = ["page not found", "404", "error", "not available", "does not exist", "could not be found"]
    if any(ind in title.lower() for ind in error_indicators):
        return False
    if any(ind in text.lower()[:200] for ind in error_indicators):  # Check first 200 chars
        return False
    
    # Skip boilerplate
    boilerplate_indicators = [
        "skip to content",
        "cookie policy", 
        "toggle navigation",
        "all rights reserved",
        "copyright"
    ]
    text_lower = text.lower()
    if any(ind in text_lower for ind in boilerplate_indicators):
        return False
    
    # Accept all valid content (PDFs, FAQs, and regular web pages)
    return True


def generate_raft_example(data_entry, retry_count=3):
    """
    Generate RAFT example with Oracle + Distractors format.
    """
    time.sleep(1)
    
    oracle_text = data_entry.get("text", "")
    title = data_entry.get("title", "")
    section_header = data_entry.get("section_header", "")
    persona = data_entry.get("persona", "all")
    source_type = data_entry.get("source_type", "web")
    
    # Get distractors from ChromaDB
    distractors = get_distractors(oracle_text, num_distractors=3)
    
    if len(distractors) < 2:
        print("⚠️ Not enough distractors found, skipping...")
        return None
    
    # Format context
    context_info = f"Title: {title}\n"
    if section_header:
        context_info += f"Section: {section_header}\n"
    if source_type == "pdf":
        pdf_page = data_entry.get("pdf_page", "unknown")
        context_info += f"Source: PDF (Page {pdf_page})\n"
    context_info += f"Target Audience: {persona}\n"
    
    # Format distractors for prompt
    distractor_text = ""
    for i, d in enumerate(distractors, 1):
        distractor_text += f"\nDistractor {i}:\n\"\"\"{d[:500]}\"\"\"" # Limit length
    
    prompt = f"""
    You are an expert educational dataset generator following the RAFT (Retrieval Augmented Fine-Tuning) format.
    
    Your task: Generate a training example where the ORACLE contains the answer and the DISTRACTORS do not.
    
    Document Metadata:
    {context_info}
    
    ORACLE DOCUMENT (Contains the Answer):
    \"\"\"{oracle_text}\"\"\"
    
    DISTRACTOR DOCUMENTS (Look relevant but DON'T contain the answer):
    {distractor_text}
    
    Generate a JSON object with:
    1. "question": A natural question that can ONLY be answered using the Oracle, not the Distractors.
                  Make it sound like a real {persona} would ask it.
    
    2. "thought_process": Chain-of-Thought reasoning that:
       - Explains WHY the Oracle contains the answer
       - Explains WHY each Distractor does NOT contain the answer
       - Shows how to distinguish the Oracle from Distractors
    
    3. "answer": A clear, concise answer based ONLY on the Oracle document.
    
    CRITICAL: The question must be answerable ONLY by the Oracle. If the Distractors could answer it, generate a different question.
    
    Output valid JSON without markdown code blocks.
    """

    for attempt in range(retry_count):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                extra_body={"reasoning": {"enabled": True}}
            )
            
            content = response.choices[0].message.content
            
            if not content:
                print("⚠️ Empty content received.")
                return None
            
            # Clean up markdown
            clean_text = content.replace("```json", "").replace("```", "").strip()
            
            try:
                generated = json.loads(clean_text)
                
                # Return proper RAFT format with Oracle + Distractors
                return {
                    "question": generated.get("question"),
                    "oracle": oracle_text,
                    "distractors": distractors,
                    "thought_process": generated.get("thought_process"),
                    "answer": generated.get("answer"),
                    
                    # Metadata
                    "source_url": data_entry.get("anchor_url", data_entry.get("url")),
                    "title": title,
                    "section_header": section_header,
                    "persona": persona,
                    "source_type": source_type,
                    "pdf_page": data_entry.get("pdf_page") if source_type == "pdf" else None
                }
            
            except json.JSONDecodeError:
                print(f"⚠️ Failed to parse JSON: {clean_text[:50]}...")
                return None

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                wait_time = (2 ** attempt) * 5
                print(f"🛑 Quota/Rate Limit hit. Waiting {wait_time}s...")
                time.sleep(wait_time)
            elif "402" in error_msg or "credit" in error_msg.lower():
                print(f"💸 Out of Credits/Payment Required: {error_msg}")
                print("Waiting 60 seconds... (You might need to top up)")
                time.sleep(60)
            elif "401" in error_msg:
                print(f"❌ Authentication Error (401): {error_msg}")
                print("Your API Key is likely invalid. Please check .env")
                return None
            else:
                print(f"❌ Error generating data: {e}")
                time.sleep(2)
    
    return None


def main():
    print("="*60)
    print("RAFT DATASET GENERATOR - PROPER FORMAT")
    print("Format: Oracle + Distractors | All Valid Content")
    print("="*60)
    print(f"\n📖 Reading from: {INPUT_FILE}")
    print(f"💾 Writing to: {OUTPUT_FILE}")
    print(f"🤖 Using model: {MODEL_NAME}\n")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Input file not found: {INPUT_FILE}")
        print(f"💡 Tip: Make sure you've run the master scraper to generate combined_campus_data.jsonl")
        return

    # Statistics
    total_entries = 0
    filtered_entries = 0
    pdf_count = 0
    faq_count = 0
    generated_count = 0
    skipped_count = 0
    
    mode = "a" if os.path.exists(OUTPUT_FILE) else "w"
    
    # First pass: count entries to estimate
    print("📊 Analyzing dataset...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total_entries += 1
            
            data = json.loads(line)
            if should_process(data):
                filtered_entries += 1
                if data.get("source_type") == "pdf":
                    pdf_count += 1
                if data.get("faq_category"):
                    faq_count += 1
    
    print(f"\n📈 Dataset Analysis:")
    print(f"   Total entries: {total_entries}")
    print(f"   PDF entries: {pdf_count}")
    print(f"   FAQ entries: {faq_count}")
    print(f"   Selected for processing: {filtered_entries}")
    print(f"   Estimated time: {filtered_entries * 1.2 / 60:.1f} minutes")
    print(f"   Estimated cost: ~${filtered_entries * 0.02:.2f}\n")
    
    confirm = input("Proceed with generation? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    print("\n🚀 Starting generation...\n")
    start_time = time.time()
    
    # Second pass: generate RAFT examples
    with open(INPUT_FILE, "r", encoding="utf-8") as infile, \
         open(OUTPUT_FILE, mode, encoding="utf-8") as outfile:
        
        for line in infile:
            if not line.strip():
                continue
                
            try:
                data = json.loads(line)
                
                # Apply filter
                if not should_process(data):
                    continue
                
                text_chunk = data.get("text", "")
                
                # Display progress with structured info
                title = data.get('title', 'Unknown')
                section = data.get('section_header', '')
                source_type = data.get('source_type', 'web')
                
                progress_msg = f"[{generated_count + skipped_count + 1}/{filtered_entries}] "
                if source_type == "pdf":
                    progress_msg += f"📄 PDF: {title}"
                    if section:
                        progress_msg += f" - {section}"
                    progress_msg += f" (Page {data.get('pdf_page', '?')})"
                else:
                    progress_msg += f"❓ FAQ: {title}"
                
                print(progress_msg)
                
                raft_entry = generate_raft_example(data)
                
                if raft_entry and isinstance(raft_entry, dict):
                    # Include enhanced metadata in RAFT dataset
                    raft_entry["context"] = text_chunk
                    raft_entry["source_url"] = data.get("anchor_url", data.get("url"))
                    raft_entry["title"] = data.get("title")
                    raft_entry["section_header"] = data.get("section_header")
                    raft_entry["persona"] = data.get("persona", "all")
                    raft_entry["source_type"] = data.get("source_type", "web")
                    
                    if data.get("source_type") == "pdf":
                        raft_entry["pdf_page"] = data.get("pdf_page")
                    
                    outfile.write(json.dumps(raft_entry) + "\n")
                    outfile.flush()
                    generated_count += 1
                    print(f"   ✅ Generated entry #{generated_count}\n")
                    
                    # Batch Rate Limit: Sleep 60s every 60 pages
                    if generated_count > 0 and generated_count % 60 == 0:
                        print("⏳ Batch limit reached. Sleeping 60s...")
                        time.sleep(60)
                else:
                    skipped_count += 1
                    print(f"   ⚠️ Skipped (generation failed)\n")

            except json.JSONDecodeError:
                continue
            except KeyboardInterrupt:
                print("\n\n⚠️ Interrupted by user. Progress saved.")
                break

    elapsed_time = time.time() - start_time
    
    print("\n" + "="*60)
    print("🎉 GENERATION COMPLETE!")
    print("="*60)
    print(f"✅ Generated entries: {generated_count}")
    print(f"⚠️  Skipped entries: {skipped_count}")
    print(f"📝 Output file: {OUTPUT_FILE}")
    print(f"⏱️  Time taken: {elapsed_time / 60:.1f} minutes")
    print(f"💰 Estimated cost: ~${generated_count * 0.02:.2f}")
    print("="*60)
    print("\n📊 Dataset format:")
    print("   - Oracle: The chunk that contains the answer")
    print("   - Distractors: 3 similar chunks from ChromaDB (don't have answer)")
    print("   - Thought Process: Explains why Oracle is correct")
    print("   - Enhanced metadata: URLs, personas, sections, PDF pages")
    print("\n💡 Use this for fine-tuning with proper RAFT format!")
    print(f"   File: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
