# Priority review: assistant answers completed

The six packets contain assistant judgments and supporting evidence. The first
three are particularly sensitive to semantic scoring. These are not independent human judgments.

For each packet, check the contract and source, then read the entire review:
final findings, submitted body and inline comments. Apply the existing
[scoring policy](../../../scoring-policy-v1.md).

Record whether each distinct claim is a strict match, a cause-only partial match,
an unmatched defect claim, or praise/neutral text. Explain the exact supporting
sentence. Identify claims that should be split or merged and any incorrect gold
labels. Do not infer missing explanations from your own knowledge of the code.
A correct repair alone does not establish a correct diagnosis.

System labels are withheld here, but text and prior discussion may reveal them;
this is not guaranteed blinded review. Your review can be recorded as human
review, but independent validation requires a reviewer independent of construction
and prior assistant judgments. Leave uncertain decisions pending.

The completed assistant answers are in answers.json and the Markdown packets.
For a later independent human pass, use the original blank packets in ../adjudication
and keep these assistant answers separate to avoid anchoring the reviewer.
Do not modify the original run or original adjudication packets. Completing this
subset does not validate all 48 reviews. The full packet set remains in
../adjudication; its mapping.json reveals system identities and should be kept
separate while reviewing.

1. [review-0038](priority-01.md)
2. [review-0012](priority-02.md)
3. [review-0039](priority-03.md)
4. [review-0010](priority-04.md)
5. [review-0025](priority-05.md)
6. [review-0034](priority-06.md)
