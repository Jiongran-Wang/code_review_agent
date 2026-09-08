#!/bin/bash
# Paired fresh comparison: original agent and agent with executable examples.
set -eu
cd -- "$(dirname -- "$0")/.."
exec .venv/bin/python -m evaluation.run \
  --backend live --model gpt-4o-mini --prompt-api-key --prompt-variant control \
  --systems agent agent-verified --repeats 1 \
  --max-iterations 8 --max-output-tokens 2048 --temperature 0 \
  --min-call-interval 30 --target-tpm 48000 \
  --rate-limit-retries 3 --max-retry-wait 180 \
  --output "${1:-evaluation/runs/gpt4omini-verification-v1}"
