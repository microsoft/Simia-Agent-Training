# Tau2-Bench

Tau2-Bench is a benchmark for evaluating tool call of Agent models.

This evaluation used the [official tau2-bench repository](https://github.com/sierra-research/tau2-bench).

## Installation

```bash
pip install -e .
```

## Configuration

Configure the API in the `.env` file:

- Set `USE_AZURE_OPENAI="true"` to use Azure OpenAI API
- Set `USE_AZURE_OPENAI="false"` to use standard OpenAI API

Fill in the corresponding API Key and Endpoint based on your choice.

## Evaluation

1. Modify the models list in `eval.sh`:
   ```bash
   models=(
       "your-model-name"
   )
   ```

2. Run evaluation:
   ```bash
   bash eval.sh
   ```

Main parameters:
```bash
tau2 run \
    --domain retail \           # Domain: retail or airline
    --agent-llm openai/$model \ # Agent model
    --user-llm gpt-4.1 \        # User simulation model
    --num-trials 4 \            # Number of trials
    --max-concurrency 6         # Concurrency
```

## Notes

⚠️ Tau2-Bench evaluation results have high variance. It is recommended to run **4 repeated trials and take the average** for stable and converged results.

## Citation

```bibtex
@misc{barres2025tau2,
      title={$\tau^2$-Bench: Evaluating Conversational Agents in a Dual-Control Environment}, 
      author={Victor Barres and Honghua Dong and Soham Ray and Xujie Si and Karthik Narasimhan},
      year={2025},
      eprint={2506.07982},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2506.07982}, 
}
```
