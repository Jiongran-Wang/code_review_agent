"""Evaluation-only v2 request policy; no fabricated reviews or extra calls."""
import json
import math


class TokenBudgetExceeded(RuntimeError):
    pass


class FinalizationPolicy:
    def __init__(self, router, max_iterations, max_output_tokens):
        self.router = router
        self.max_iterations = max_iterations
        self.max_output_tokens = max_output_tokens
        self.phase = 'investigate'

    def prepare(self, client, system, tools, messages=None):
        responses = [r['response'] for r in client.records if 'response' in r]
        used = client.input_tokens + client.output_tokens
        # Observed input includes the large rubric and tool schemas. Reserve two
        # more calls, with 20% growth allowance, before doing further investigation.
        estimate = (responses[-1]['usage'].get('input_tokens', 0) * 1.2
                    + self.max_output_tokens) if responses else 0
        remaining_iterations = self.max_iterations - len(responses)
        if self.router.reviews:
            self.phase = 'final'
        elif remaining_iterations <= 1:
            self.phase = 'final'
        elif self.phase == 'investigate' and (remaining_iterations <= 2 or
                (responses and client.token_budget - used < 3 * estimate)):
            self.phase = 'submit'
        if self.phase == 'investigate':
            return system, tools
        allowed = {'create_pull_request_review'} if self.phase == 'submit' else set()
        self.router.allowed_tools = allowed
        tools = [t for t in (tools or []) if t['name'] in allowed]
        instruction = (
            'Investigation is closed to reserve budget for finalization. Submit one review now '
            'using create_pull_request_review. Consolidate repeated evidence for the same defect. '
            'Include only introduced defects supported under the PR preconditions. '
            'Do not claim an example executed if it was rejected.' if self.phase == 'submit' else
            'Return the required final review JSON now, preserving all distinct submitted defect '
            'claims. No tools remain. Do not invent a submission or successful test execution.')
        return system + '\n\nRuntime finalization instruction:\n' + instruction, tools


class InsufficientWorkflowBudget(RuntimeError):
    pass


class StagedVerificationPolicy:
    """V3: explicit required stages with observed, phase-specific estimates."""
    ALLOWED = {
        'context': {'get_pull_request', 'get_pull_request_files', 'get_file_contents'},
        'execute': {'execute_example'},
        'submit': {'create_pull_request_review'},
        'final': set(),
    }
    INSTRUCTIONS = {
        'context': 'Fetch the PR contract and changed code, preferably in one parallel tool-call response. Do not submit or finalize yet.',
        'execute': 'Call execute_example now. Batch useful contract-valid normal and boundary examples in one plan. Use source function names. References are JSON objects such as {"$ref":"items"}, never strings such as "$ref: items". For cross-call default-state checks, repeat calls omitting the optional argument. Correct a rejected plan using its error. Do not submit or finalize yet.',
        'submit': 'Interpret the observations against the contract and both revisions. One finding per introduced defect; multiple witnesses are not separate defects. A passing normal example does not establish boundary correctness. Shared failures or invalid inputs do not establish an introduced defect. Submit exactly one review using create_pull_request_review now. Praise and style suggestions are not findings. If no actionable defects were found, submit an empty review.',
        'final': 'Return only the required final review JSON now. APPROVE requires findings: []. Every findings entry must allege an actionable introduced defect, never praise or a neutral summary. If no defects were found, use an empty findings array. Preserve every distinct submitted defect allegation; do not drop genuine claims to obtain APPROVE. Do not invent successful tests or a submission. No tools remain.',
    }

    def __init__(self, router, max_iterations, max_output_tokens, finalization_prompt):
        self.router, self.max_iterations = router, max_iterations
        self.max_output_tokens = max_output_tokens
        self.finalization_prompt = finalization_prompt
        self.phase = 'context'

    def system_for(self, phase, system):
        # Keep the full review rubric during context collection and execution.
        # Submission/final JSON use the output contract and verification guidance;
        # the complete conversation, source and observations remain available.
        base = self.finalization_prompt if phase in ('submit', 'final') else system
        return base + '\n\nRequired workflow stage: ' + phase + '\n' + self.INSTRUCTIONS[phase]

    @staticmethod
    def request_size(system, tools, messages):
        return len(json.dumps({'system': system, 'tools': tools, 'messages': messages}, ensure_ascii=False))

    def prepare(self, client, system, tools, messages=None):
        messages = messages or []
        successful = {c['tool'] for c in self.router.calls if 'error' not in c['result']}
        context_ready = {'get_pull_request', 'get_pull_request_files'} <= successful
        if self.router.reviews:
            self.phase = 'final'
        elif 'execute_example' in successful:
            self.phase = 'submit'
        elif context_ready:
            self.phase = 'execute'
        else:
            self.phase = 'context'
        sequence = ['context', 'execute', 'submit', 'final']
        remaining = sequence[sequence.index(self.phase):]
        responses = [r for r in client.records if 'response' in r]
        reason = None
        if self.max_iterations - len(responses) < len(remaining):
            reason = 'Not enough iterations for the remaining required workflow stages'
        estimates = {}
        if responses:
            last = responses[-1]
            old = last['request']
            ratio = last['response']['usage'].get('input_tokens', 0) / max(1, self.request_size(old['system'], old['tools'], old['messages']))
            for offset, phase in enumerate(remaining):
                phase_tools = [t for t in (tools or []) if t['name'] in self.ALLOWED[phase]]
                size = self.request_size(self.system_for(phase, system), phase_tools, messages)
                # Calibrate to reported input usage, expose only phase tools,
                # allow 15% estimation error and 1,024 growing context tokens
                # per intervening stage. This is not a provider token counter.
                estimates[phase] = math.ceil(size * ratio * 1.15 + offset * 1024 + self.max_output_tokens)
            if sum(estimates.values()) > client.token_budget - client.input_tokens - client.output_tokens:
                reason = 'Estimated remaining token budget cannot support the required workflow stages'
        client._save({'event':'workflow_budget_check', 'phase':self.phase,
                      'remaining_stages':remaining, 'estimated_stage_tokens':estimates})
        if reason:
            client._save({'event':'termination', 'reason':'insufficient_workflow_budget', 'detail':reason})
            raise InsufficientWorkflowBudget(reason)
        self.router.allowed_tools = self.ALLOWED[self.phase]
        return (self.system_for(self.phase, system),
                [t for t in (tools or []) if t['name'] in self.router.allowed_tools])
