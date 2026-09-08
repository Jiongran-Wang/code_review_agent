# Published development comparison

This directory contains the completed `gpt4omini-full-comparison-v3-v1` experiment:
16 synthetic development fixtures, three systems, and one sample per fixture and
system. All 48 reviews were attempted; two required workflows failed. All model
responses report `gpt-4o-mini-2024-07-18`.

Start with [the results and failure analysis](comparison.md).

## Inspect the evidence

- [Machine-readable comparison](comparison.json): quality, usage, paired cases,
  execution assessments, and provenance.
- [Run manifest](manifest.json), [input snapshot](inputs.jsonl), and
  [per-review results](results.jsonl): original settings and measured outcomes.
- `baseline/`, `agent/`, `agent-verified/`: original model/tool transcripts,
  submitted reviews, execution records, and structured outputs.
- [Assistant assessment](assistant-assessment.json): semantic decisions and rationales.
- [Original skill prompts](original-skills.json): exact Chinese-language skill
  contents used by the historical run, retained after the active skills were translated.
- `assistant-adjudication-strict-v1/` and
  `assistant-adjudication-sensitivity-v1/`: normalized claims, matching decisions,
  and frozen scoring-policy snapshots for all 48 reviews.
- `adjudication/`: original human-review packets, still pending.
- [Priority reviews](human-review-priority/START-HERE.md): six packets completed
  by an AI assistant; they are not independent human judgments.

The synthetic inputs and semantic judgments were authored/reviewed with an AI
assistant. The reported scores are **provisional and non-blinded**. Executable
reference checks support the authored fixture behavior; they do not independently
validate every semantic judgment or establish production review accuracy.

## Reproduce without API calls

From the repository root after installing `requirements.txt`:

```bash
.venv/bin/python scripts/verify_published_results.py
```

This verifies file hashes and recomputes both complete score reports. It also
checks the 51 frozen inference/fixture/policy files, using the archived skill
contents for the 15 translated prompt files. To write a score report:

```bash
.venv/bin/python -m evaluation.adjudicate report \
  --packets evaluation/published/full-comparison-v3/assistant-adjudication-strict-v1 \
  --output evaluation/runs/reproduced-strict.json
```

## Publication provenance

[publication-manifest.json](publication-manifest.json) records SHA-256 byte hashes
for both the original files and the publication copies. The three `mapping.json`
files use a repository-relative `run_path`. Publication documentation edits are
listed separately in the manifest.
The original-skills snapshot is a packaging addition checked against the original
freeze. Inference outputs, judgments, labels, and saved scores are unchanged. The original
local run remains separate. This README and the publication manifest are packaging
additions, not historical experiment artifacts.

The original manifest includes historical hashes of documentation. Packaging
updated the top-level evaluation documentation; those historical documentation
hashes are retained as provenance. The separate inference freeze remains intact.
