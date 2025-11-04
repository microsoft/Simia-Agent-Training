#!/bin/bash
# Please set these environment variables before running the script:
export AZURE_OPENAI_ENDPOINT=""
export WANDB_API_KEY=""

set -e

echo "Starting General Simulated Environment PPO training..."

if [ -z "$AZURE_OPENAI_ENDPOINT" ]; then
    echo "Error: AZURE_OPENAI_ENDPOINT environment variable not set"
    exit 1
fi


if [ -z "$WANDB_API_KEY" ]; then
    echo "Error: WANDB_API_KEY environment variable not set"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OUTPUT_DIR="$SCRIPT_DIR/outputs"
CHECKPOINTS_DIR="$OUTPUT_DIR/checkpoints/Simia-RL-8B-tau2-APIGen-MT"
RESULTS_DIR="$OUTPUT_DIR/training_records/Simia-RL-8B-tau2-APIGen-MT"

mkdir -p "$CHECKPOINTS_DIR"
mkdir -p "$RESULTS_DIR"

echo "Output directory created: $OUTPUT_DIR"

echo "Cleaning Ray processes..."
pkill -f ray || echo "No Ray processes found"
sleep 2
CONFIG_FILE="$SCRIPT_DIR/simulated_env_config.yaml"
cat > "$CONFIG_FILE" << EOF
defaults:
  - base
  - _self_


model_path: Simia-Agent/Simia-Tau-SFT-Qwen3-8B
micro_batch_size_per_gpu: 1
ppo_mini_batch_size: 8

actor_rollout_ref:
  actor:
    use_ref: True
    use_kl_loss: True
    kl_loss_coef: 0.001
    
    kl_loss_type: low_var_kl
    fsdp_config:
      model_dtype: bfloat16
      param_offload: False
      optimizer_offload: False
  rollout:
    max_model_len: 9000
    max_num_batched_tokens: 9000
    tensor_model_parallel_size: 1
    tp_size_check: False
    gpu_memory_utilization: 0.5
    temperature: 0.7
    rollout_filter_ratio: 1.0
    val_kwargs:
      do_sample: True
      temperature: 0.7
  ref:
    fsdp_config:
      model_dtype: bfloat16
      param_offload: False
      optimizer_offload: False

algorithm:
  adv_estimator: grpo

trainer:
  project_name: "simulated_env_tau2"
  experiment_name: "qwen-8b-SFT"
  n_gpus_per_node: 8
  val_before_train: False
  test_freq: 10000
  total_training_steps: 64
  save_freq: 4
  default_local_dir: "$CHECKPOINTS_DIR"
  logger: ['console', 'wandb']
  generations_to_log_to_wandb:
    train: 32
    val: 20

agent_proxy:
  max_turn: 40
  max_actions_per_turn: 1
  use_turn_scores: False
  reward_normalization:
    grouping: "state"
    method: "identity"

es_manager:
  train:
    env_groups: 16
    group_size: 8
    env_configs:
      tags: ["GeneralSimulated"]
      n_groups: [16]
  val:
    env_groups: 8
    group_size: 4
    env_configs:
      tags: ["GeneralSimulated"]
      n_groups: [8]

custom_envs:
  GeneralSimulated:
    env_type: simulated_general
    max_actions_per_traj: 60
    env_instruction: ""
    env_config:
      env_id: "null"
      output_dir: "$RESULTS_DIR/simulated_env_tau2/output"
      train_data_path: "$SCRIPT_DIR/APIGen_5k_processed.json"
      training_record_dir: "$CHECKPOINTS_DIR/simulated_env_tau2/training_record"
      azure_endpoint: "$AZURE_OPENAI_ENDPOINT"
      api_version: "2025-04-01-preview"
      deployment: "gpt-5"
      temperature: 1.0
      max_tokens: 60000
      retry_attempts: 3
      timeout: 600
      max_simulation_steps: 100
      reward_on_success: 1.0
      reward_on_failure: 0.0

aml_checkpoints_path: "$CHECKPOINTS_DIR"
aml_output_dir: "$RESULTS_DIR"
EOF

echo "Config file created: $CONFIG_FILE"

mkdir -p "$SCRIPT_DIR/components/ragen/src/default_config"
cp "$CONFIG_FILE" "$SCRIPT_DIR/components/ragen/src/default_config/user_config.yaml"
echo "Config file copied to: $SCRIPT_DIR/components/ragen/src/default_config/user_config.yaml"

export CUDA_VISIBLE_DEVICES="0,1,2,3,4,5,6,7"
export PYTHONPATH="${PYTHONPATH}:${REPO_ROOT}:${REPO_ROOT}/subtrees/ragen"
export WANDB_PROJECT="simulated_env_RL"

if ! python -c "import gymnasium" 2>/dev/null; then
    echo "Installing gymnasium..."
    pip install gymnasium
fi

if ! python -c "import wandb" 2>/dev/null; then
    echo "Installing wandb..."
    pip install wandb
fi

echo "Initializing wandb..."
wandb login $WANDB_API_KEY
cd "$SCRIPT_DIR/components/ragen/src"
python train.py \
    --config-name=user_config 




