import json
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
INPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "campus_data.jsonl")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "raft_dataset.jsonl")
MODEL_NAME = "arcee-ai/trinity-large-preview:free"

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file. Please add it.")
    
# Debug Key Format Warning
if OPENROUTER_API_KEY.startswith("v1-"):
    print("⚠️ WARNING: Your API Key starts with 'v1-'. OpenRouter keys typically start with 'sk-or-v1-'. "
          "If you are seeing 401 errors, please check your key.")

# Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def generate_raft_example(text_chunk, retry_count=3):
    """
    Generates a RAFT example using Arcee-AI via OpenRouter with reasoning enabled.
    """
    time.sleep(1)

    prompt = f"""
    You are an expert educational dataset generator. 
    Your task is to create a high-quality training example for a RAG system based on the following text.
    
    Text Context:
    \"\"\"{text_chunk}\"\"\"
    
    Generate a JSON object with the following keys:
    - "question": A likely student question that can be answered using the text.
    - "thought_process": A chain-of-thought step-by-step reasoning on how to find the answer in the text.
    - "answer": A clear, concise, and helpful answer to the question, based ONLY on the text.
    
    Ensure the output is valid JSON. Do not wrap in markdown code blocks.
    """

    for attempt in range(retry_count):
        try:
            # First API call with reasoning
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                extra_body={"reasoning": {"enabled": True}}
            )
            
            # The model should output the JSON in the content
            content = response.choices[0].message.content
            
            # Optional: Capture reasoning details if we wanted to use them specifically
            # reasoning = getattr(response.choices[0].message, 'reasoning_details', None)
            
            if not content:
                print("⚠️ Empty content received.")
                return None
            
            # Clean up markdown if present
            clean_text = content.replace("```json", "").replace("```", "").strip()
            
            try:
                return json.loads(clean_text)
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
                 return None # Don't retry on Auth error
            else:
                print(f"❌ Error generating data: {e}")
                # Retry on other errors just in case
                time.sleep(2)
    
    return None

def main():
    print(f"🚀 Starting RAFT Dataset Generation using {MODEL_NAME}...")
    print(f"📖 Reading from: {INPUT_FILE}")
    print(f"💾 Writing to: {OUTPUT_FILE}")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Input file not found: {INPUT_FILE}")
        return

    generated_count = 0
    mode = "a" if os.path.exists(OUTPUT_FILE) else "w"
    
    with open(INPUT_FILE, "r", encoding="utf-8") as infile, \
         open(OUTPUT_FILE, mode, encoding="utf-8") as outfile:
        
        for line in infile:
            if not line.strip():
                continue
                
            try:
                data = json.loads(line)
                text_chunk = data.get("text", "")
                
                if len(text_chunk) < 100:
                    continue

                print(f"Processing chunk from: {data.get('url', 'Unknown URL')}...")
                
                raft_entry = generate_raft_example(text_chunk)
                
                if raft_entry and isinstance(raft_entry, dict):
                    raft_entry["context"] = text_chunk
                    raft_entry["source_url"] = data.get("url")
                    
                    outfile.write(json.dumps(raft_entry) + "\n")
                    outfile.flush()
                    generated_count += 1
                    print(f"✅ Generated entry #{generated_count}")
                    
                    # Batch Rate Limit: Sleep 60s every 60 pages
                    if generated_count > 0 and generated_count % 60 == 0:
                        print("⏳ Batch limit reached. Sleeping 60s...")
                        time.sleep(60)

                else:
                    print("⚠️ Skipping chunk.")

            except json.JSONDecodeError:
                continue

    print(f"\n🎉 Generation Complete! {generated_count} examples saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
