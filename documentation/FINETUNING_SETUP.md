# Fine-tuning Setup Instructions

## Prerequisites

1. **CUDA-capable GPU** (12GB+ VRAM recommended)
2. **CUDA Toolkit** installed (check with `nvcc --version`)
3. **Python 3.10+**
4. **uv** package manager

## Installation

### 1. Install Dependencies

```bash
cd 03_fine_tuning

# Install unsloth and all dependencies with uv
uv add unsloth

# This will automatically install:
# - unsloth with CUDA support
# - transformers, trl, datasets
# - accelerate, bitsandbytes
# - All required dependencies
```

### 2. Verify Installation

```python
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
```

## Training

### 1. Generate RAFT Dataset

```bash
# Make sure you have generated RAFT data
uv run python generate_raft_focused.py
```

This creates `raft_dataset.jsonl` with 200-300 examples.

### 2. Open Notebook

```bash
# Start Jupyter
uv run jupyter notebook train_unsloth.ipynb
```

Or use VS Code with Jupyter extension.

### 3. Run All Cells

The notebook will:

1. Load Llama 3.1 8B with 4-bit quantization
2. Apply LoRA adapters
3. Format RAFT dataset
4. Train for ~300 steps (~30-60 minutes)
5. Save fine-tuned model

## Training Configuration

### Memory-Efficient Settings (12GB VRAM)

- **4-bit quantization**: Reduces model size ~4x
- **LoRA r=16**: Fine-tune only 1-10% of parameters
- **Batch size 2**: Per-device batch size
- **Gradient accumulation 4**: Effective batch = 8
- **adamw_8bit**: Saves ~2GB VRAM

### For More VRAM (24GB+)

Update in notebook:

```python
per_device_train_batch_size = 4,  # Increase batch size
gradient_accumulation_steps = 2,  # Reduce accumulation
```

## Output

### LoRA Adapters

Saved to `campus_gpt_lora/`:

- Small files (~100-500MB)
- Require base model to use
- Can be loaded with `FastLanguageModel.from_pretrained()`

### Merged Model

Saved to `campus_gpt_merged/` (optional):

- Standalone model (~16GB)
- No base model needed
- Ready for Ollama or deployment

## Using with Ollama

### Option 1: LoRA Adapters

```bash
# Create Modelfile
echo 'FROM llama3.1:8b' > Modelfile
echo 'ADAPTER ./campus_gpt_lora' >> Modelfile

# Create model
ollama create campus-gpt -f Modelfile
```

### Option 2: Merged Model

```bash
# Export to GGUF format first
# Then create Modelfile pointing to GGUF
```

## Troubleshooting

### CUDA Out of Memory

1. Reduce batch size: `per_device_train_batch_size = 1`
2. Reduce sequence length: `max_seq_length = 2048`
3. Use gradient checkpointing (already enabled)

### Slow Training

Expected: ~1-2 minutes per 10 steps with 12GB GPU

Speed up:

- Use mixed precision (bf16 on newer GPUs)
- Reduce max_steps for testing
- Use smaller dataset

### Import Errors

```bash
# Reinstall with correct CUDA version
uv pip uninstall unsloth
uv pip install "unsloth[cu124] @ git+https://github.com/unslothai/unsloth.git"
```

## Next Steps

After training:

1. Test model with sample questions
2. Deploy with Ollama
3. Integrate with RAG system
4. Evaluate vs base model
