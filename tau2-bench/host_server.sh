#!/bin/bash

# Note: vLLM cleanup is now handled by test_models.sh with GPU-aware logic

# Resolve vllm binary robustly
VLLM_BIN="${VLLM_BIN:-}"
if [ -z "$VLLM_BIN" ]; then
  VLLM_BIN="$(command -v vllm 2>/dev/null || true)"
fi
if [ -z "$VLLM_BIN" ] && [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/vllm" ]; then
  VLLM_BIN="$CONDA_PREFIX/bin/vllm"
fi
if [ -z "$VLLM_BIN" ]; then
  echo "Error: vllm not found in PATH and CONDA_PREFIX/bin."
  echo "Hint: export VLLM_BIN=/path/to/conda/envs/tau2/bin/vllm"
  exit 1
fi

# Create log directory
mkdir -p logs

echo "Using vllm path: $VLLM_BIN"
echo "Starting vLLM server..."

# Generate timestamp for log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Start vLLM server and configure logging (with timestamp)
"$VLLM_BIN" serve --config vllm_server_config.yaml \
  --enable-request-id-headers \
  > logs/vllm_server_${TIMESTAMP}.log 2>&1 &



# Record server PID
VLLM_PID=$!
echo $VLLM_PID > logs/vllm_server.pid

echo "vLLM server has started, logs saved to logs/vllm_server_${TIMESTAMP}.log"
echo "Server PID saved to logs/vllm_server.pid"