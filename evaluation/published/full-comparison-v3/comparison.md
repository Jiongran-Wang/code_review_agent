# Frozen full v3 development comparison

V3 detected more planted defects under the frozen strict policy and used fewer
input tokens than the original agent, but it also produced more false alarms on
clean cases. This is a recall/false-alarm tradeoff, not a general reliability win.

All 48 scheduled reviews were attempted: 16 fixtures per system, one fresh sample
per fixture. These are **provisional, non-blinded coding-assistant judgments**.
Independent human validation remains pending. The 16 small fixtures are development
data that have repeatedly informed the implementation, not a held-out benchmark.

## Primary results

| Metric | Single-call baseline | Original agent | V3 agent |
|---|---:|---:|---:|
| Required workflows completed | 16/16 | 15/16 | 15/16 |
| True-positive defect claims | 5 | 4 | 7 |
| False-positive defect claims | 10 | 4 | 7 |
| Missed planted defects | 3 | 4 | 1 |
| Precision | 33.3% | 50.0% | 50.0% |
| Recall | 62.5% | 50.0% | 87.5% |
| F1 | 43.5% | 50.0% | 63.6% |
| Exact gold-line localized recall | 62.5% | 25.0% | 50.0% |
| Clean cases with semantic false alarms | 5/8 | 2/7 completed | 5/7 completed |
| Failed clean cases | 0 | 1 | 1 |
| Raw final positive clean cases, before praise exclusion | 5/8 | 4/7 completed | 5/7 completed |

Semantic and exact-line correctness are separate. Pure praise is excluded from
semantic predictions and preserved in normalization notes; speculative warnings
and style complaints presented as issues remain false positives. Original failures
are preserved and are not converted into successful clean reviews.

The strict F1 increase over the original agent is 13.6 percentage points in this
run. It comes with three additional planted defects detected and three additional
completed clean cases falsely flagged. Both agents completed the same number of
required workflows. The configurations have different prompts, tools and compute;
this experiment does not isolate execution alone as the cause of any difference.

## Which planted defects were found

| Family | Baseline | Original agent | V3 |
|---|---|---|---|
| Ownership authorization | Detected | Detected | Detected |
| Shared mutable default | Detected | Detected | Detected |
| SQL parameterization | Detected | Detected | Detected |
| Preprocessing leakage | Detected | Detected | Detected |
| Empty aggregate | Cause-only partial | Cause-only partial | Detected |
| Pagination | Wrong consequence; partial | Incomplete/contradictory consequence; partial | Detected |
| Expiration equality | Miss | Miss | Detected |
| Historical-price window | Detected | Miss | Mixed/contradictory explanation; partial |

V3 adds empty-input handling, pagination and expiration detection over the original
agent without losing its four strict matches. Against the baseline, it gains those
three families but loses strict credit for the historical-price explanation.

## Scoring sensitivity and human-review priorities

The frozen policy requires the introduced cause and a correct concrete consequence.
Under its separate cause-only sensitivity rule, F1 is **60.9% baseline, 75.0%
original agent, 72.7% v3**. The original agent slightly leads v3 under that alternate
rule. These are alternate semantic judgments, not confidence intervals. The strict
ranking should not be presented without this sensitivity result.

The v3 historical-price review needs particular human attention. Final f2 names
the shifted slice but describes an out-of-contract empty-list/division failure.
The submitted body reverses observed values for `(index=0, window=1)`, yet also
correctly states that the mean is wrong at `index == window`. That latter statement
is preserved as context for the same changed-mean allegation, not discarded or
counted as a third duplicate claim. The frozen policy withholds primary credit
for mixed/contradictory consequences and credits its cause in sensitivity. A human
reviewer should check that normalization and judgment explicitly.

Other priorities: the original agent supplies a correct pagination repair without
a correct consequence explanation; the baseline preprocessing finding explicitly
describes test-data fitting violating the train-only rule without using the word
leakage. Their rationales and original outputs are preserved in the assessment.

## Execution evidence and false alarms

V3 returned observations from 18 execution plans across 15 cases. It produced an
in-contract behavioral witness for **6 of 8 planted defects**. Five of its seven
strictly correct diagnoses have such a witness. The sixth reproduced defect,
historical-price leakage, was not explained consistently in the review.

- **Authorization and SQL:** correct prose diagnoses, no valid executed witness.
  Authorization examples pass a document record instead of an ID-to-document map,
  raising KeyError in both versions. SQL examples use ordinary names and an empty
  database; all return empty lists.
- **Clean expiration:** the model claims equality changed even though source and
  executed observations show True at equality in both versions. This is a direct
  failure to use the available evidence.
- **Clean mutable default:** the model passes the literal string `existing_list`,
  observes AttributeError in both versions, then blames the return-copy refactor.
- **Clean ownership:** a missing-document KeyError is shared by both versions and
  outside the existing-document contract; it is incorrectly called a new defect.
- **Clean preprocessing:** the tested empty training list violates the nonempty
  contract; both versions raise the same exception.
- **Clean historical mean:** the failing `index < window` test violates explicit
  preconditions, while the valid examples agree. An identical plan is executed
  twice; both calls remain in usage/tool counts.

Some buggy-case plans also include invalid inputs (zero page size, empty training
data, insufficient price history). Valid witnesses are counted separately; invalid
examples are not silently treated as evidence of an introduced defect.

## Completion failures

The original agent's clean empty-aggregate case uses `repo="benchmark"`; v3's clean
pagination case uses `repo="repo"`. Both differ from the supplied fixture IDs.
The router rejects these arguments. The models then claim the repository is
inaccessible and return a finding with `file:null` and no line, violating the
output schema. Neither submits a review; v3 does not execute that case. These
are model argument/output failures, not unavailable repositories, billing errors
or token exhaustion.

## Usage and duration

| Metric | Baseline | Original agent | V3 |
|---|---:|---:|---:|
| Model responses | 16 | 57 | 62 |
| Reported input tokens | 261,603 | 995,289 | 606,880 |
| Reported output tokens | 1,078 | 4,631 | 6,182 |
| Tool calls / errors | 0 / 0 | 73 / 4 | 65 / 2 |
| API time, summed | 28.1 seconds | 97.4 seconds | 117.8 seconds |
| Pacing wait, summed | 7.2 minutes | 26.8 minutes | 29.0 minutes |
| Case duration, summed | 7.6 minutes | 28.5 minutes | 31.0 minutes |

V3 uses **39.0% fewer input tokens than the original agent**, but approximately
2.32 times the baseline's input tokens. It makes more model calls and takes longer
than the original agent in this run. The lower input count comes with compact
finalization prompts, not fewer calls. There were no rate-limit retries; all three
systems together took about 67.1 minutes including pacing. No dollar-cost estimate
is inferred from token counts alone.

## Provenance and next steps

The frozen file hashes and run source hashes were verified. Baseline/original-agent
prompts and v3 stage prompts match the frozen configuration. All 135 responses
report `gpt-4o-mini-2024-07-18`. Baseline and original agent report fingerprint
`fp_8c60972de7`; v3 reports 32 responses with that fingerprint and 30 with
`fp_4abd59899c`. These records do not explain the difference or isolate its effect.

Both scoring reports reproduce from the saved assistant adjudication packets.
The separate **48 human-review packets remain unfilled**. `comparison.json`
contains paired cases, metrics, evidence assessments and provenance hashes;
`assistant-assessment.json` contains the detailed provisional judgments. No
inference code, original run result or gold label was changed during analysis.

The next useful work is independent review of these judgments and new-case
collection, rather than another paid rerun after tuning to these same fixtures.
Future improvements should test whether the reviewer checks preconditions and
uses base/head evidence to reject unsupported claims. New cases should include
clean controls and meaningful test setup, especially for authorization and SQL.
Keep development and new evaluation cases separate and freeze the next comparison
before examining its results. Do not present this small development result as
production accuracy or independently validated resume performance.
