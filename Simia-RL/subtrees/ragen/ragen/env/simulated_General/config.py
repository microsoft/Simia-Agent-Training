from typing import Optional
from dataclasses import dataclass

@dataclass
class SimulatedEnvConfig:
    """Configuration for the general simulated environment."""

    env_id: str = "null"
    output_dir: str = "./simulated_output"

    # Dataset configuration
    train_data_path: str = "./APIGen_5k_processed.json"
    training_dataset_path: Optional[str] = None  # Compatible with old parameter name

    # Training record save path
    training_record_dir: str = "checkpoints/general-simulated-tau2/training_record"

    # API configuration
    api_type: str = "azure"  # "azure" or "openai"
    
    # Azure OpenAI configuration
    azure_endpoint: str = "${AZURE_OPENAI_ENDPOINT}"
    api_version: str = "2025-04-01-preview"
    deployment: str = "gpt-5"
    
    # OpenAI configuration
    openai_api_key: str = "${OPENAI_API_KEY}"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5"
    
    # Common configuration
    temperature: float = 1.0
    max_tokens: int = 60000
    retry_attempts: int = 3
    timeout: int = 200

    # Interaction configuration
    max_simulation_steps: int = 25

    # Default reward values (fallback if model doesn't return reward)
    reward_on_success: float = 1.0
    reward_on_failure: float = 0.0
