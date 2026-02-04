# RAFT Dataset Generator Guide

## Overview

The RAFT (Retrieval Augmented Fine-Tuning) dataset generator creates high-quality training data in the proper RAFT format with Oracle and Distractors.

## Proper RAFT Format

Each training example contains:

- **Question**: Natural student query
- **Oracle (P\*)**: The chunk that contains the answer
- **Distractors (D_i)**: 3 similar chunks from ChromaDB that DON'T contain the answer
- **Thought Process**: Chain-of-Thought explaining why Oracle is right and Distractors are wrong
- **Answer**: Concise response based on Oracle

## Features

### Oracle + Distractors

- Uses ChromaDB to find semantically similar but incorrect chunks
- Ensures questions are answerable ONLY by the Oracle
- Creates realistic training scenarios

### Smart Filtering

- **All valid content**: Web pages, PDFs, FAQs
- **Error pages filtered**: No 404 or "Page Not Found" pages
- **Quality checks**: Text length (200-3000 chars), no boilerplate
- **Metadata enrichment**: Deep-linked URLs, personas, sections, PDF pages

## Prerequisites

1. **ChromaDB populated**:

   ```bash
   uv run python 02_rag_system/main.py ingest
   ```

2. **OPENROUTER_API_KEY** set in `.env`

## Usage

```bash
cd 03_fine_tuning
uv run python generate_raft_focused.py
```

The script will:

1. Connect to ChromaDB
2. Analyze dataset and show statistics
3. Ask for confirmation
4. Generate RAFT examples with progress tracking
5. Save to `raft_dataset.jsonl`

## Output Format

```json
{
  "question": "What are the CS major requirements?",
  "oracle": "Computer Science majors must complete CSC 174, 175, 260...",
  "distractors": [
    "CS students are encouraged to participate in internships...",
    "The CS department offers concentrations in...",
    "Computer Science maintains partnerships with..."
  ],
  "thought_process": "The Oracle directly lists required courses. Distractor 1 discusses internships, not requirements. Distractor 2 mentions concentrations, not core requirements. Distractor 3 talks about partnerships, irrelevant to requirements.",
  "answer": "CS majors need CSC 174, 175, 260, 340, and 475 as core courses...",
  "source_url": "https://nku.edu/...",
  "title": "Computer Science - Requirements",
  "persona": "prospective,student",
  "source_type": "pdf",
  "pdf_page": 142
}
```

## Performance

- **~200-300 examples** from ~1100 valid entries (after error filtering)
- **30-40 minutes** runtime (with free model)
- **$0** cost (using free tier model)
- **Processes all valid content** (error pages and boilerplate excluded)

## Error Handling

- Automatic retry on rate limits
- Error page filtering at multiple levels
- Null safety for missing fields
- Batch processing with progress saves

## Next Steps

After generation:

1. **Review output**:

   ```bash
   head -n 1 raft_dataset.jsonl | python -m json.tool
   ```

2. **Fine-tune model**:
   Use in `train_unsloth.ipynb` for model fine-tuning

3. **Evaluate**:
   Test fine-tuned model vs base model on held-out questions
