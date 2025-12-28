#!/usr/bin/env bash
# Run llama-server with GPT-OSS-20B model
# Adjust paths and parameters as needed

set -euo pipefail

# Paths
LLAMA_SERVER="/home/jerkytreats/ai/llama.cpp/build/bin/llama-server"
MODEL_PATH="/home/jerkytreats/.lmstudio/models/lmstudio-community/gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf"

# Server settings
HOST="${LLAMA_HOST:-127.0.0.1}"
PORT="${LLAMA_PORT:-8080}"

# Model settings
CTX_SIZE="${LLAMA_CTX_SIZE:-4096}"        # Context window size
N_GPU_LAYERS="${LLAMA_GPU_LAYERS:-99}"    # Layers to offload to GPU (99 = all)
THREADS="${LLAMA_THREADS:-8}"             # CPU threads for prompt processing

# Check if server binary exists
if [[ ! -x "$LLAMA_SERVER" ]]; then
    echo "Error: llama-server not found at $LLAMA_SERVER"
    echo "Build it with: cd /home/jerkytreats/ai/llama.cpp && cmake -B build -DGGML_VULKAN=ON && cmake --build build -j\$(nproc)"
    exit 1
fi

# Check if model exists
if [[ ! -f "$MODEL_PATH" ]]; then
    echo "Error: Model not found at $MODEL_PATH"
    echo "Available models:"
    find /home/jerkytreats -name "*.gguf" -size +100M 2>/dev/null | head -10
    exit 1
fi

echo "Starting llama-server..."
echo "  Model: $MODEL_PATH"
echo "  Host: $HOST:$PORT"
echo "  Context: $CTX_SIZE"
echo "  GPU Layers: $N_GPU_LAYERS"
echo ""

exec "$LLAMA_SERVER" \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --ctx-size "$CTX_SIZE" \
    --n-gpu-layers "$N_GPU_LAYERS" \
    --threads "$THREADS" \
    --flash-attn auto \
    "$@"

