# LMServer

OpenAI-compatible local LLM API gateway for Tailscale networks.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host Machine (configured via DNS_TARGET_DEVICE)           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ llama-server (localhost:8080)                       │   │
│  │ - Local LLM inference server                        │   │
│  │ - Serves configured model                           │   │
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
        │  {DNS_SERVICE_NAME}.{DNS_DOMAIN_BASE} │
        │  (Tailscale DNS - configurable)      │
        └─────────────────────────────────────┘
```

## Quick Start

### 1. Set up Python environment

```bash
# Clone or navigate to the project directory
cd /path/to/lmserver

# Create virtual environment
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

**Important:** The systemd service files contain user-specific paths (e.g., `/home/jerkytreats/...`) that must be customized for your deployment environment before installation.

### Customize service files

Before installing, edit the service files to match your environment:

- `systemd/lmserver.service`: Update `User`, `Group`, `WorkingDirectory`, and `ExecStart` paths
- `systemd/llama-server.service`: Update `User`, `Group`, `WorkingDirectory`, and script paths
- `scripts/run-llama-server.sh`: Update `LLAMA_SERVER` and `MODEL_PATH` variables

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
| `LMSERVER_DNS_DOMAIN_BASE` | `internal.jerkytreats.dev` | Base domain for DNS registration (customize for your network) |
| `LMSERVER_DNS_API_URL` | `https://dns.internal.jerkytreats.dev` | DNS API server URL (customize for your network) |
| `LMSERVER_DNS_SERVICE_NAME` | `chat` | Service name for DNS (combined with DNS_DOMAIN_BASE) |
| `LMSERVER_DNS_REGISTER_ON_STARTUP` | `false` | Register with DNS on start (only needed once) |
| `LMSERVER_DNS_TARGET_DEVICE` | `leviathan` | Tailscale device name where service runs (customize for your device) |
| `LMSERVER_DEFAULT_MODEL` | `gpt-oss-20b` | Default model name |

You can also create a `.env` file:

```bash
# Server settings
LMSERVER_HOST=0.0.0.0
LMSERVER_PORT=8000

# Backend
LMSERVER_LLAMA_SERVER_URL=http://127.0.0.1:8080

# Concurrency
LMSERVER_MAX_CONCURRENT_REQUESTS=8
LMSERVER_REQUEST_TIMEOUT=300.0

# DNS registration (network topology - customize for your environment)
LMSERVER_DNS_DOMAIN_BASE=internal.example.com
LMSERVER_DNS_API_URL=https://dns.internal.example.com
LMSERVER_DNS_SERVICE_NAME=chat
LMSERVER_DNS_REGISTER_ON_STARTUP=false
LMSERVER_DNS_TARGET_DEVICE=your-device-name

# Model
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
    base_url="http://{LMSERVER_DNS_SERVICE_NAME}.{LMSERVER_DNS_DOMAIN_BASE}/v1",
    # Example: http://chat.internal.example.com/v1
    api_key="not-needed",  # No auth required
)

response = client.chat.completions.create(
    model="gpt-oss-20b",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

## Switching Models

To use a different model, edit `scripts/run-llama-server.sh` and update the `MODEL_PATH` variable:

```bash
# Set the path to your model file
MODEL_PATH="/path/to/your/model.gguf"
```

You can also set it via environment variable:

```bash
export MODEL_PATH="/path/to/your/model.gguf"
./scripts/run-llama-server.sh
```

Then restart the service:

```bash
sudo systemctl restart llama-server
```

**Note:** The systemd service files and scripts contain user-specific paths that should be customized for your deployment environment.

