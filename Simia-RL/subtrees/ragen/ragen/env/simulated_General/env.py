import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI, OpenAI

from ragen.env.base import BaseEnv
from .config import SimulatedEnvConfig


# Default training record directory
DEFAULT_TRAINING_RECORD_DIR = "/mnt/data/temp/checkpoints/general-simulated-tau2/training_record"


class SimulatedGeneralEnv(BaseEnv):
    """General simulated environment where GPT orchestrates the dialogue with the RL model."""

    name = "simulated_general_env"

    def __init__(self, config: Optional[SimulatedEnvConfig] = None, **kwargs):
        self.kwargs = kwargs
        self.config = config or SimulatedEnvConfig()
        self.logger = logging.getLogger(__name__)

        # Core configuration
        self.env_id = self.config.env_id
        self.max_steps = self.config.max_simulation_steps
        self.dataset_path = Path(getattr(self.config, "train_data_path", getattr(self.config, "training_dataset_path", "")))

        # Token length limit - get from kwargs or use default
        self.max_model_len = kwargs.get('max_model_len', 9000)
        self.tokenizer = kwargs.get('tokenizer', None)
        # Estimate response_length for token limit check (default to 2048 if not in config)
        self.response_length = kwargs.get('response_length', 500)
        # Reserve space for environment messages (estimated)
        self.env_message_reserve = 500
        
        # Runtime state
        self.current_step: int = 0
        self.done: bool = False
        self.final_reward: float = 0.0
        self.observation: str = ""
        self.info: Dict[str, Any] = {}
        self.current_sample: Optional[Dict[str, Any]] = None
        self.system_prompt: str = ""
        self.reference_conversations: List[Dict[str, str]] = []
        self.sample_index: int = 0

        # Histories
        self.conversation_history: List[Dict[str, str]] = []  # role: "human" or "assistant"
        self.gpt_call_history: List[Dict[str, Any]] = []

        # Dataset cache and sampling strategy
        self._dataset: List[Dict[str, Any]] = []
        self._episode_count: int = 0  # Number of episodes processed by current environment
        
        # Parse env_id (could be string "null" or number)
        try:
            self._env_id_int = int(self.env_id) if self.env_id != 'null' else 0
        except (ValueError, TypeError):
            self._env_id_int = 0

        # Training record directory
        self.training_record_dir = Path(getattr(self.config, "training_record_dir", DEFAULT_TRAINING_RECORD_DIR))
        self.training_record_dir.mkdir(parents=True, exist_ok=True)

        # API client setup
        self.client = None
        self.model = None  # Store model name
        self._setup_api_client()

        # Load dataset
        self._ensure_dataset_loaded()

        BaseEnv.__init__(self)

    # ------------------------------------------------------------------
    # Dataset handling
    # ------------------------------------------------------------------
    def _ensure_dataset_loaded(self) -> None:
        if self._dataset:
            return

        if not self.dataset_path:
            raise ValueError("training_dataset_path / train_data_path is not configured in SimulatedEnvConfig")

        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Training dataset not found at {self.dataset_path}")

        with self.dataset_path.open("r", encoding="utf-8") as f:
            try:
                payload = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse dataset JSON: {exc}") from exc

        if isinstance(payload, list):
            self._dataset = payload
        else:
            raise ValueError("Unsupported dataset format: expected a list")

        if not self._dataset:
            raise ValueError(f"Dataset at {self.dataset_path} is empty")

        self.logger.info("Loaded %d samples from %s", len(self._dataset), self.dataset_path)

    def _sample_trajectory(self, seed: Optional[int] = None, mode: str = "train") -> Dict[str, Any]:
        """
        Sample selection strategy (GRPO compatible):
        - train mode: GRPO requires the same sample to be sampled by group_size environments
          Assume 8 groups, group_size=16, total 128 environments
          group_id = env_id // group_size
          All environments in the same group sample the same sample
          E.g.: env_0-15 all sample sample_0, env_16-31 all sample sample_1
        - val mode: Use env_id for sequential assignment, each environment tests a fixed sample
        """
        if not self._dataset:
            self._ensure_dataset_loaded()

        dataset_size = len(self._dataset)
        
        if mode == "train":
            # GRPO training mode: same group samples the same sample
            # group_id determines which sample, episode_count controls cycling
            # Get group_size from kwargs, default to 16
            group_size = self.kwargs.get('group_size', 16)
            group_id = self._env_id_int // group_size
            
            # Each episode, each group samples a new sample
            # group_id as offset, episode_count controls rounds
            idx = (group_id + self._episode_count * (128 // group_size)) % dataset_size
            self._episode_count += 1
        else:
            # Validation mode: each environment tests a fixed sample
            idx = self._env_id_int % dataset_size

        self.sample_index = idx
        sample = self._dataset[idx]
        
        self.logger.debug(
            f"Env {self.env_id} (mode={mode}, episode={self._episode_count}): "
            f"Loading sample {idx}/{dataset_size}"
        )
        
        return dict(sample) if isinstance(sample, dict) else sample

    # ------------------------------------------------------------------
    # API client setup
    # ------------------------------------------------------------------
    def _setup_api_client(self) -> None:
        """Initialize OpenAI or Azure OpenAI client based on config."""
        api_type = getattr(self.config, 'api_type', 'azure').lower()
        
        try:
            if api_type == 'azure':
                credential = AzureCliCredential()
                token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
                self.client = AzureOpenAI(
                    azure_ad_token_provider=token_provider,
                    azure_endpoint=self.config.azure_endpoint,
                    api_version=self.config.api_version,
                )
                self.model = self.config.deployment
                self.logger.info("Azure OpenAI client initialized (deployment=%s)", self.model)
            elif api_type == 'openai':
                api_key = getattr(self.config, 'openai_api_key', '')
                base_url = getattr(self.config, 'openai_base_url', 'https://api.openai.com/v1')
                self.client = OpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
                self.model = getattr(self.config, 'openai_model', 'gpt-4o')
                self.logger.info("OpenAI client initialized (model=%s)", self.model)
            else:
                raise ValueError(f"Invalid api_type: {api_type}. Must be 'azure' or 'openai'")
        except Exception as exc:
            self.logger.error("API client initialization failed: %s", exc)
            self.client = None
            self.model = None

    # ------------------------------------------------------------------
    # Reset & step
    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, mode: str = "train", **kwargs) -> Any:
        self.current_step = 0
        self.done = False
        self.final_reward = 0.0
        self.observation = ""
        self.info = {}
        self.conversation_history = []
        self.gpt_call_history = []

        # Get sample (pass mode parameter to control sampling strategy)
        self.current_sample = self._sample_trajectory(seed, mode=mode)
        if not isinstance(self.current_sample, dict):
            raise ValueError("Each dataset sample must be a JSON object")

        # Extract system and conversations
        self.system_prompt = self.current_sample.get("system", "")
        self.reference_conversations = self.current_sample.get("conversations", [])

        print("=" * 80)
        print(f"🎯 New Episode Started - Sample Index: {self.sample_index}")
        print("=" * 80)
        print(f"📝 System prompt (first 200 chars): {self.system_prompt[:200]}...")
        print(f"📚 Reference conversation rounds: {len(self.reference_conversations)}")
        print("=" * 80)

        # GPT generates first message (simulating human)
        initial_message = self._generate_first_message()
        self.observation = initial_message
        self.conversation_history.append({"role": "human", "content": initial_message})

        print("\n🗣️ GPT First Message (Simulating Human):")
        print(initial_message)
        print("=" * 80)

        # Check if initial prompt is already too long
        if self._check_token_length_exceeded():
            print(f"\n⚠️ Warning: Initial prompt is approaching or exceeding token limit!")
            safe_threshold = self.max_model_len - self.response_length - self.env_message_reserve
            print(f"   Current threshold: {safe_threshold} (max_model_len={self.max_model_len}, reserved={self.response_length + self.env_message_reserve})")
            print(f"   Suggestion: Consider simplifying system_prompt or increasing max_model_len")

        return self.render()

    def _generate_first_message(self) -> str:
        """Extract the first human message directly from the reference conversations"""
        
        # Find the first human message in reference conversations
        for msg in self.reference_conversations:
            if msg.get("from") == "human":
                first_message = msg.get("value", "").strip()
                self.logger.info(f"Using first human message from reference: {first_message[:100]}...")
                return first_message
        
        # Fallback: if no human message found, raise error
        raise ValueError("No human message found in reference conversations")
    
    def _check_token_length_exceeded(self) -> bool:
        """
        Check if the current conversation would exceed max_model_len.
        This checks if there's enough space for:
        - Current conversation history
        - Next environment message (estimated)
        - Agent's response (response_length)
        """
        if self.tokenizer is None:
            # If no tokenizer provided, skip check
            return False

        # Build the full conversation text as it would be formatted
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Apply chat template to get the text that would be tokenized
        text = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

        # Tokenize and check length
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        token_count = len(tokens)

        # Calculate safe threshold: leave space for next env message + agent response
        safe_threshold = self.max_model_len - self.response_length - self.env_message_reserve

        if token_count > safe_threshold:
            self.logger.warning(
                f"Token length {token_count} exceeds safe threshold {safe_threshold} "
                f"(max_model_len={self.max_model_len}, reserved={self.response_length + self.env_message_reserve}), "
                f"terminating conversation"
            )
            return True

        return False

    def step(self, action: str) -> Tuple[Any, float, bool, Dict[str, Any]]:
        if self.done:
            return self.observation, self.final_reward, True, self.info

        action = (action or "").strip()


        print(f"\n{'='*80}")
        print(f"🤖 Model Response (Round {self.current_step + 1}):")
        print(action)
        print("=" * 80)

        self.current_step += 1

        # Add action to history first
        self.conversation_history.append({"role": "assistant", "content": action})

        # Check if max steps reached
        force_termination = self.current_step >= self.max_steps

        # GPT generates next message (simulating human or tool response), letting GPT judge if tool call is correct
        if force_termination:
            # Max steps reached, perform final evaluation
            print(f"\n⏰ Max steps reached ({self.max_steps}), performing final evaluation...")
            reward, reasoning = self._evaluate_final_performance()
            self.observation = f"[Task Ended] Maximum interaction rounds reached.\nFinal evaluation: {reasoning}"
            self.final_reward = reward
            self.done = True
            self.info["termination_reason"] = "max_steps"
            self.info["reasoning"] = reasoning
            
            print(f"\n💰 Final Reward: {reward}")
            print(f"📊 Evaluation Reasoning: {reasoning}")
            print("=" * 80)
            
            return self.observation, reward, True, self.info
        
        # Generate next environment message
        next_message, should_terminate = self._generate_next_environment_message(action)
        self.observation = next_message
        
        # Append GPT response to history (regardless of termination)
        self.conversation_history.append({"role": "human", "content": next_message})
        
        # Check token length before sending to model for response generation
        if self._check_token_length_exceeded():
            print(f"\n⚠️ Token length exceeded (after appending GPT response), failing directly...")
            safe_threshold = self.max_model_len - self.response_length - self.env_message_reserve
            print(f"   Current threshold: {safe_threshold} (max_model_len={self.max_model_len}, reserved={self.response_length + self.env_message_reserve})")
            
            # Give reward 0 directly
            self.observation = f"[Task Ended] Token length exceeded after appending GPT response, detected before sending to model."
            self.final_reward = 0.0
            self.done = True
            self.info["termination_reason"] = "token_limit_exceeded_before_generation"
            self.info["reasoning"] = "Token length exceeded, direct failure"

            print(f"\n💰 Final Reward: 0.0 (failed due to exceeding limit)")
            print(f"📊 Evaluation Reasoning: Token length exceeded")
            print("=" * 80)

            return self.observation, 0.0, True, self.info
        
        if should_terminate:
            print(f"\n🗣️ GPT Final Response (Simulating Human/Tool, Round {self.current_step}):")
            print(next_message)
            print("=" * 80)
            
            # GPT decided to end conversation
            print(f"\n✅ GPT decided to end conversation, performing final evaluation...")
            reward, reasoning = self._evaluate_final_performance()
            self.final_reward = reward
            self.done = True
            self.info["termination_reason"] = "gpt_decision"
            self.info["reasoning"] = reasoning
            
            print(f"\n💰 Final Reward: {reward}")
            print(f"📊 Evaluation Reasoning: {reasoning}")
            print("=" * 80)
            
            return self.observation, reward, True, self.info
        
        # Continue conversation
        print(f"\n🗣️ GPT Response (Simulating Human/Tool, Round {self.current_step}):")
        print(next_message)
        print("=" * 80)
        
        return self.observation, 0.0, False, self.info

    def _generate_next_environment_message(self, agent_message: str) -> Tuple[str, bool]:
        """
        GPT generates the next environment message based on agent's message
        Returns: (message content, whether to terminate the conversation)
        """
        ref_conv_text = self._format_reference_conversations()
        history_text = self._format_history_for_prompt()
        
        prompt = f"""You are a simulation environment. Based on the RL model's response, you need to simulate the human or tool response.

System prompt (task description and rules):
{self.system_prompt}

Reference conversation examples (use this as reference data):
{ref_conv_text}

Current conversation history:
{history_text}

RL model's latest response:
{agent_message}

Requirements:
1. Based on the reference conversation and system prompt, determine how to respond
2. **Important for tool call format checking**: 
   - If the RL model is attempting to call a tool, check if it is properly wrapped in <tool_call></tool_call> tags
   - If the tool call is NOT in <tool_call> tags or has incorrect format (e.g., malformed JSON, wrong structure), return an error message like: "Error: Tool call must be wrapped in <tool_call></tool_call> tags with proper JSON format"
   - Only if the tool call format is correct, proceed to generate the tool response
3. **Important for tool responses**: 
   - If the RL model called a tool correctly, check if related results exist in the reference conversation
   - If YES: Include the related results from the reference conversation in the tool response
   - If NO: Generate reasonable results for the tool response based on the query parameters
   - If the format is incorrect, return an error message explaining why
3. If the RL model is waiting for human input, simulate the human's next message based on the reference conversation flow
4. Follow the pattern in the reference conversation examples, but adjust appropriately to fit the current conversation
5. If the task is completed or the conversation should end, output the "[TERMINATE]" marker

Output format:
- If continuing the conversation, output the message content directly
- If should end, output "[TERMINATE]"

Please directly generate the next message without the prefix "User/Tool response":"""

        response = self._call_gpt([{"role": "user", "content": prompt}])
        
        self._save_gpt_call_info(
            prompt=prompt,
            response=response,
            metadata={"step": self.current_step, "type": "environment_response", "agent_message": agent_message}
        )
        
        # Check if should terminate
        should_terminate = "[TERMINATE]" in response
        message = response.strip()
        
        return message, should_terminate

    def _evaluate_final_performance(self) -> Tuple[float, str]:
        """
        GPT evaluates RL model performance based on system prompt and complete conversation history
        Returns: (reward: 0 or 1, reasoning: evaluation reasoning)
        """
        history_text = self._format_history_for_prompt()
        
        prompt = f"""You need to evaluate the RL model's performance in this task and provide a reward.

System prompt (rules and policies):
{self.system_prompt}

Complete conversation history:
{history_text}

Evaluation criteria:
1. Did the RL model correctly understand the task requirements
2. Did the RL model follow the rules and procedures in the system prompt
3. **Tool call format check**: If the RL model attempted to call tools, were they properly wrapped in <tool_call></tool_call> tags with correct JSON format? If tool calls were malformed or not properly tagged, this should be considered a FAILURE.
4. Did the RL model handle tool responses correctly

**IMPORTANT**: 
- Simply completing the user's request is NOT sufficient if policies were violated
- Incorrect tool call format (missing <tool_call> tags or malformed JSON) should result in reward = 0

Output requirement:
Please output the evaluation result in JSON format:
{{
    "reasoning": "Detailed evaluation reasoning, explaining why this reward was given"
    "reward": 0 or 1,  // 0 means failure, 1 means success
}}

Please perform the evaluation:"""

        response = self._call_gpt([{"role": "user", "content": prompt}])
        
        self._save_gpt_call_info(
            prompt=prompt,
            response=response,
            metadata={"step": self.current_step, "type": "final_evaluation"}
        )
        
        # Parse evaluation result
        evaluation = self._parse_evaluation_response(response)
        reward = evaluation.get("reward", 0)
        reasoning = evaluation.get("reasoning", "No evaluation reasoning provided")
        
        # Save trajectory and reward to file
        self._save_trajectory_record(reward, reasoning)
        
        return float(reward), reasoning

    def _parse_evaluation_response(self, response: str) -> Dict[str, Any]:
        """Parse evaluation response"""
        # Try to extract JSON
        candidates = [response]
        
        if "```" in response:
            for fence in ("```json", "```"):
                start = response.find(fence)
                if start != -1:
                    end = response.find("```", start + len(fence))
                    if end != -1:
                        candidates.append(response[start + len(fence):end].strip())
        
        # Try to find JSON object
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if json_match:
            candidates.append(json_match.group(0))
        
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Parse failed, return default value
        self.logger.error("Failed to parse evaluation response: %s", response)
        return {"reward": 0, "reasoning": f"Failed to parse evaluation: {response[:100]}..."}

    def _format_reference_conversations(self) -> str:
        """Format reference conversations as text"""
        if not self.reference_conversations:
            return "No reference conversation"
        
        lines = []
        for msg in self.reference_conversations:
            role = msg.get("from", "unknown")
            content = msg.get("value", "").strip()
            if content:
                if role == "human":
                    lines.append(f"User/Tool response: {content}")
                elif role == "gpt" or role == "assistant":
                    lines.append(f"Assistant: {content}")
                else:
                    lines.append(f"{role}: {content}")
        
        return "\n\n".join(lines) if lines else "No reference conversation"

    def _format_history_for_prompt(self) -> str:
        """Format conversation history as text"""
        if not self.conversation_history:
            return "No conversation history"
        
        lines = []
        for turn in self.conversation_history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "").strip()
            if role == "human":
                lines.append(f"User/Tool response: {content}")
            elif role == "assistant":
                lines.append(f"Assistant: {content}")
            else:
                lines.append(f"{role}: {content}")
        
        return "\n\n".join(lines)

    def render(self, mode: str = "text") -> Any:
        return self.observation

    # ------------------------------------------------------------------
    # GPT interaction helpers
    # ------------------------------------------------------------------
    def _call_gpt(self, messages: List[Dict[str, str]]) -> str:
        if not self.client:
            raise RuntimeError("API client is not initialized")

        last_error: Optional[Exception] = None
        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                # Prepare API call parameters
                call_params = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "timeout": self.config.timeout,
                }
                
                # Always use max_completion_tokens (works for both Azure and new OpenAI models)
                call_params["max_completion_tokens"] = self.config.max_tokens
                
                completion = self.client.chat.completions.create(**call_params)
                content = completion.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from API")
                
                # If response contains <think> tags, extract only content after </think>
                if "</think>" in content:
                    # Find the position of </think>
                    think_end = content.find("</think>")
                    if think_end != -1:
                        # Extract content after </think>
                        after_think = content[think_end + len("</think>"):]
                        # Remove leading newlines if present
                        after_think = after_think.lstrip('\n')
                        content = after_think
                
                return content.strip()
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "GPT call failed (attempt %s/%s): %s", attempt, self.config.retry_attempts, exc
                )
                time.sleep(min(2**attempt, 8))

        # raise RuntimeError(f"Unable to get response from Azure OpenAI: {last_error}")

    def _save_gpt_call_info(self, prompt: str, response: str, metadata: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt": prompt,
            "response": response,
            "metadata": metadata,
            "deployment": self.config.deployment,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        self.gpt_call_history.append(record)

    def _save_trajectory_record(self, reward: float, reasoning: str) -> None:
        """
        Save trajectory and reward to organized directory structure
        Structure: training_record/sample_{sample_index}/env_{env_id}_ep{episode_count}_{timestamp}.json
        """
        try:
            # Create sample-specific directory
            sample_dir = self.training_record_dir / f"sample_{self.sample_index}"
            sample_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with env_id, episode count, and timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"env_{self.env_id}_ep{self._episode_count - 1}_{timestamp}.json"
            filepath = sample_dir / filename
            
            # Prepare trajectory record
            trajectory_record = {
                "env_id": self.env_id,
                "sample_index": self.sample_index,
                "episode_count": self._episode_count - 1,
                "timestamp": datetime.utcnow().isoformat(),
                "reward": reward,
                "reasoning": reasoning,
                "num_steps": self.current_step,
                "max_steps": self.max_steps,
                "termination_reason": self.info.get("termination_reason", "unknown"),
                "system_prompt": self.system_prompt,
                "reference_conversations": self.reference_conversations,
                "conversation_history": self.conversation_history,
                "gpt_call_history": self.gpt_call_history,
                "config": {
                    "deployment": self.config.deployment,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "azure_endpoint": self.config.azure_endpoint,
                }
            }
            
            # Save to file
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(trajectory_record, f, indent=2, ensure_ascii=False)
            
            self.logger.info(
                f"Trajectory saved: sample={self.sample_index}, env={self.env_id}, "
                f"episode={self._episode_count - 1}, reward={reward}, file={filepath}"
            )
        except Exception as e:
            self.logger.error(f"Failed to save trajectory record: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Logging & utilities
    # ------------------------------------------------------------------
    def get_current_status(self) -> Dict[str, Any]:
        return {
            "current_step": self.current_step,
            "max_steps": self.max_steps,
            "done": self.done,
            "final_reward": self.final_reward,
            "history_length": len(self.conversation_history),
            "sample_index": self.sample_index,
        }

    def dump_history(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        history_file = Path(output_dir) / "conversation_history.json"
        gpt_history_file = Path(output_dir) / "gpt_call_history.json"
        status_file = Path(output_dir) / "env_status.json"
        sample_file = Path(output_dir) / "current_sample.json"

        with history_file.open("w", encoding="utf-8") as f:
            json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)

        with gpt_history_file.open("w", encoding="utf-8") as f:
            json.dump(self.gpt_call_history, f, indent=2, ensure_ascii=False)

        with status_file.open("w", encoding="utf-8") as f:
            json.dump(self.get_current_status(), f, indent=2, ensure_ascii=False)
        
        with sample_file.open("w", encoding="utf-8") as f:
            json.dump(self.current_sample, f, indent=2, ensure_ascii=False)

        self.logger.info("History records saved to: %s", output_dir)

    def get_reward(self) -> Tuple[float, Dict[str, Any]]:
        """Get current reward (force evaluation if not done)"""
        if not self.done:
            reward, reasoning = self._evaluate_final_performance()
            self.final_reward = reward
            self.done = True
            self.info["termination_reason"] = "forced_evaluation"
            self.info["reasoning"] = reasoning
        
        return self.final_reward, self.info

    def close(self) -> None:
        pass
