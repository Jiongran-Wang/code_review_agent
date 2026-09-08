#!/bin/bash
# Six selected development cases; tool/workflow diagnostic, not a benchmark.
set -eu
cd -- "$(dirname -- "$0")/.."
exec .venv/bin/python -m evaluation.run \
  --backend live --model gpt-4o-mini --prompt-api-key \
  --systems agent-verified --verification-version v2 \
  --inputs evaluation/data/verification-v2-diagnostic-inputs.jsonl \
  --repeats 1 --max-iterations 8 --max-output-tokens 2048 \
  --token-budget 100000 --temperature 0 \
  --min-call-interval 30 --target-tpm 48000 \
  --rate-limit-retries 3 --max-retry-wait 180 \
  --output "${1:-evaluation/runs/gpt4omini-verification-v2-diagnostic-v1}"
