
#!/bin/bash

# Define the list of models to test
models=(
    "Simia-Agent/Simia-Tau-SFT-Qwen3-8B"
)


mkdir -p logs

# Load OPENAI_API_KEY from .env file (used for user-llm gpt-4.1)
source .env 2>/dev/null || true

# Local vLLM server address (used for agent-llm openai/xxx models)
export VLLM_API_BASE="http://localhost:8000/v1"

# Iterate over each model
for model in "${models[@]}"; do
    echo "=========================================="
    echo "Starting to test model: $model"
    echo "=========================================="

    # Extract model name for log file name
    model_name=$(echo "$model" | sed 's/\//_/g')

    # Update model name in vllm_server_config.yaml
    echo "Updating vllm server configuration..."
    sed -i "s|^model:.*|model: $model|" vllm_server_config.yaml
    
    # Update tool-call-parser based on model name
    if [[ "$model" == *"xlam"* || "$model" == *"xLAM"* ]]; then
        echo "Detected xlam model, setting tool-call-parser to xlam..."
        sed -i "/^tool-call-parser:/d" vllm_server_config.yaml
        sed -i "/^tool-parser-plugin:/d" vllm_server_config.yaml
        echo "tool-call-parser: xlam" >> vllm_server_config.yaml
        sed -i "/^chat-template:/d" vllm_server_config.yaml
    elif [[ "$model" == *"llama"* || "$model" == *"Llama"* ]]; then
        echo "Detected Llama model, using fixed llama3_json parser..."
        sed -i "/^tool-call-parser:/d" vllm_server_config.yaml
        sed -i "/^tool-parser-plugin:/d" vllm_server_config.yaml
        echo "tool-call-parser: llama3_json" >> vllm_server_config.yaml
        sed -i "/^chat-template:/d" vllm_server_config.yaml
        if [[ "$model" == *"llama"*"3.1"* || "$model" == *"Llama"*"3.1"* || "$model" == *"llama3-8B"* ]]; then
            echo "Detected Llama 3.1 model, adding chat-template..."
            echo "chat-template: tool_chat_template_llama3.1_json.jinja" >> vllm_server_config.yaml
        elif [[ "$model" == *"llama"*"3.2"* || "$model" == *"Llama"*"3.2"* ]]; then
            echo "Detected Llama 3.2 model, adding chat-template..."
            echo "chat-template: tool_chat_template_llama3.2_json.jinja" >> vllm_server_config.yaml
        fi
    elif [[ "$model" == *"qwen"* || "$model" == *"Qwen"* ]]; then
        echo "Detected Qwen model, setting tool-call-parser to hermes..."
        sed -i "/^tool-parser-plugin:/d" vllm_server_config.yaml
        sed -i "/^tool-call-parser:/d" vllm_server_config.yaml
        echo "tool-call-parser: hermes" >> vllm_server_config.yaml
        if [[ "$model" == *"qwen3-8b"* || "$model" == *"Qwen3-8B"* ]]; then
            echo "Detected Qwen3 model, adding chat-template..."
            sed -i "/^chat-template:/d" vllm_server_config.yaml
            echo "chat-template: qwen3_nonthinking.jinja" >> vllm_server_config.yaml
        else
            sed -i "/^chat-template:/d" vllm_server_config.yaml
        fi
    fi

    # Stop existing vllm processes
    echo "Stopping existing vllm processes..."
    pkill vllm
    sleep 5

    # Start new vllm server
    echo "Starting vllm server..."
    bash host_server.sh &

    # Wait for server to start
    echo "Waiting for server to start..."
    sleep 30

    # Check server status
    echo "Checking server status..."
    for i in {1..50}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "Server is ready"
            break
        else
            echo "Waiting for server to start... ($i/50)"
            sleep 10
        fi
    done



    # Run airline domain evaluation
    # Agent: local vLLM model (openai/$model) -> localhost:8000
    # User:  OpenAI gpt-4.1 -> api.openai.com
    echo "Running airline domain evaluation..."
    tau2 run \
    --domain airline \
    --agent-llm openai/$model \
    --user-llm gpt-4.1 \
    --num-trials 4 \
    --max-concurrency 6 2>&1 | tee logs/airline_${model_name}_tau2_$(date +%Y%m%d_%H%M%S).log

    # Run retail domain evaluation
    # Agent: local vLLM model (openai/$model) -> localhost:8000
    # User:  OpenAI gpt-4.1 -> api.openai.com
    echo "Running retail domain evaluation..."
    tau2 run \
    --domain retail \
    --agent-llm openai/$model \
    --user-llm gpt-4.1 \
    --num-trials 4 \
    --max-concurrency 6 2>&1 | tee logs/retail_${model_name}_tau2_$(date +%Y%m%d_%H%M%S).log




    echo "All evaluations for model $model completed"
    echo ""
done

echo "=========================================="
echo "All model evaluations completed!"
echo "=========================================="
