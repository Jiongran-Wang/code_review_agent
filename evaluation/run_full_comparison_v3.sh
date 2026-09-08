#!/bin/bash
# Fresh 16-case, three-system development comparison. No previous results reused.
set -eu
cd -- "$(dirname -- "$0")/.."
.venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path

spec = json.loads(Path('evaluation/comparison-v3-freeze.json').read_text())
changed = [name for name, expected in spec['file_sha256'].items()
           if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected]
if changed:
    raise SystemExit('Frozen comparison files changed; create a new experiment version before running: ' + ', '.join(changed))
print('Verified frozen comparison sources, inputs, scoring policy and launch script.', flush=True)
PY
exec .venv/bin/python -m evaluation.run \
  --backend live --model gpt-4o-mini --prompt-api-key \
  --systems baseline agent agent-verified --verification-version v3 \
  --prompt-variant control --inputs evaluation/data/inputs.jsonl \
  --repeats 1 --max-iterations 8 --max-output-tokens 2048 \
  --token-budget 100000 --temperature 0 --order-seed 42 \
  --min-call-interval 30 --target-tpm 48000 \
  --rate-limit-retries 3 --max-retry-wait 180 \
  --output "${1:-evaluation/runs/gpt4omini-full-comparison-v3-v1}"
