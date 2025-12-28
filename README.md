# LMServer

OpenAI-compatible local LLM API gateway for Tailscale networks.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  leviathan (AMD AI 395 MAX / 128GB)                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ llama-server (localhost:8080)                       │   │
│  │ - Vulkan acceleration on Radeon 8060S               │   │
│  │ - Serves GPT-OSS-20B model                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ▲                                  │
│                          │                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ LMServer Gateway (0.0.0.0:8000)                     │   │
│  │ - OpenAI-compatible /v1/chat/completions            │   │
│  │ - Concurrency limiting (semaphore)                  │   │
│  │ - Request queue for batch jobs                      │   │
│  │ - DNS registration on startup                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ▲                                  │
└──────────────────────────│──────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │  chat.internal.jerkytreats.dev      │
        │  (Tailscale DNS)                    │
        └─────────────────────────────────────┘
```

## Quick Start

### 1. Set up Python environment

```bash
cd /home/jerkytreats/ai/lmserver
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start llama-server

```bash
# Make the script executable
chmod +x scripts/run-llama-server.sh

# Run llama-server (in a separate terminal or background)
./scripts/run-llama-server.sh
```

### 3. Start LMServer gateway

```bash
# Development mode
source .venv/bin/activate
uvicorn lmserver.main:app --host 0.0.0.0 --port 8000 --reload

# Or run directly
python -m lmserver.main
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'

# List models
curl http://localhost:8000/v1/models

# Queue status (for batch job monitoring)
curl http://localhost:8000/v1/queue/status
```

## Systemd Services (Production)

### Install services

```bash
# Copy service files
sudo cp systemd/llama-server.service /etc/systemd/system/
sudo cp systemd/lmserver.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable llama-server lmserver
sudo systemctl start llama-server
sudo systemctl start lmserver

# Check status
sudo systemctl status llama-server lmserver
```

### View logs

```bash
# llama-server logs
journalctl -u llama-server -f

# LMServer gateway logs
journalctl -u lmserver -f
```

## Configuration

All settings can be configured via environment variables with `LMSERVER_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `LMSERVER_HOST` | `0.0.0.0` | API server bind host |
| `LMSERVER_PORT` | `8000` | API server port |
| `LMSERVER_LLAMA_SERVER_URL` | `http://127.0.0.1:8080` | llama-server backend URL |
| `LMSERVER_MAX_CONCURRENT_REQUESTS` | `4` | Max parallel inferences |
| `LMSERVER_REQUEST_TIMEOUT` | `300.0` | Request timeout (seconds) |
| `LMSERVER_DNS_API_URL` | `https://dns.internal.jerkytreats.dev` | DNS API server |
| `LMSERVER_DNS_SERVICE_NAME` | `chat` | Service name for DNS |
| `LMSERVER_DNS_REGISTER_ON_STARTUP` | `false` | Register with DNS on start (only needed once) |
| `LMSERVER_DEFAULT_MODEL` | `gpt-oss-20b` | Default model name |

You can also create a `.env` file:

```bash
LMSERVER_MAX_CONCURRENT_REQUESTS=8
LMSERVER_DEFAULT_MODEL=gpt-oss-20b
```

## llama-server Configuration

The `scripts/run-llama-server.sh` script accepts environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLAMA_HOST` | `127.0.0.1` | Bind host (keep internal) |
| `LLAMA_PORT` | `8080` | Port |
| `LLAMA_CTX_SIZE` | `4096` | Context window size |
| `LLAMA_GPU_LAYERS` | `99` | Layers to offload to GPU |
| `LLAMA_THREADS` | `8` | CPU threads |

## Concurrency Tuning

With 128GB RAM and ~12GB model size:
- **Conservative:** `MAX_CONCURRENT_REQUESTS=4` (~60GB with context)
- **Aggressive:** `MAX_CONCURRENT_REQUESTS=8` (~100GB with context)

The merkle project batch workloads will queue behind the semaphore automatically.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check with backend status |
| `/v1/chat/completions` | POST | OpenAI-compatible chat |
| `/v1/models` | GET | List available models |
| `/v1/queue/status` | GET | Queue status for monitoring |
| `/v1/{path}` | * | Fallback proxy to llama-server |

## Using with OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://chat.internal.jerkytreats.dev/v1",
    api_key="not-needed",  # No auth required
)

response = client.chat.completions.create(
    model="gpt-oss-20b",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

## Switching Models

To use a different model, edit `scripts/run-llama-server.sh`:

```bash
# GPT-OSS-120B (needs more RAM)
MODEL_PATH="/home/jerkytreats/.lmstudio/models/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4-00001-of-00002.gguf"

# DeepSeek-V3 Q3 (very large)
MODEL_PATH="/home/jerkytreats/models/deepseek-v3-q3/DeepSeek-V3-Q3_K_M/DeepSeek-V3-Q3_K_M-00001-of-00008.gguf"
```

Then restart the service:

```bash
sudo systemctl restart llama-server
```

