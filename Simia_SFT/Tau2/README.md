# Tau2 Data Processing and Generation Tool

Tau2 is a toolkit for generating and processing Agent Airline and Retail training data, supporting data cleaning, format conversion, and conversation generation.

## Quick Start



### 1. Configuration File

Unzip the pre-processed seed data
```python
cd Simia_SFT/Tau2
unzip APIGen_5k_preprocessed_zip.zip
cd ..
cd ..
```


Edit `config.json` to set generation parameters:

```json
{
  "azure_endpoint": "your-endpoint",
  "api_version": "2025-04-01-preview",
  "deployment": "gpt-5",
  "sample_data_path": "APIGen_5k_preprocessed.json",
  "generation_settings": {
    "max_conversations": 10,
    "temperature": 1,
    "parallel_workers": 200,
    "batch_size": 2500
  }
}
```

### 2. Conversation Generation

Use `main.py` to generate Agent multi-turn conversation data. Features include checkpoint resumption, log saving, and progress tracking by default.

```bash
# Use default configuration, will enter interactive mode
python main.py

# Specify configuration file
python main.py --config config.json

# Force restart
python main.py --force-new

# Check progress
python main.py --status
```


### 3. Post-processing Pipeline

Use `process_data_pipeline.sh` to batch process raw data:

```bash
# Basic usage
bash process_data_pipeline.sh <input_file>

# Specify output file
bash process_data_pipeline.sh <input_file> <output_file>
```

Processing workflow includes:
1. `fix_arguments.py` - Fix function argument formats
2. `tool2hermes.py` - Convert to Hermes format
3. `tool_correct.py` - Correct tool calls
4. `remove_think_tag.py` - Remove thinking tags
5. `replace_system_prompt_Hermes.py` - Replace system prompts



## Output Files

- Processed data: `*_processed.json`
- Generated conversations: `output/tau2_100k_gpt5.json`
- GPT logs: `gpt_log_tau2_100k_gpt5_*.jsonl`
- Progress files: `progress_*.json`

## Notes

- Ensure Azure OpenAI API key is configured
- Processing pipeline will automatically clean up intermediate files
