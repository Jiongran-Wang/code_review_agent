"""Regression for separate context reads starving execution in the live v2 pilot."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.run import run_case, read_jsonl
from evaluation.runtime import PROJECT, LLMResponse


class SeparateReadsModel:
    def __init__(self, router, bad_final=False, reject_first=False):
        self.router = router
        self.bad_final, self.reject_first = bad_final, reject_first
        self.seen, self.systems = [], []
        self.execution_attempts = 0

    def complete(self, messages, system=None, tools=None):
        names = {t['name'] for t in (tools or [])}
        self.seen.append(names)
        self.systems.append(system)
        # Simulate the live rubric cost, but smaller submission/final prompts.
        usage = {'input_tokens':18000 if len(system)>20000 else 3500, 'output_tokens':100}
        common = {'owner':self.router.owner,'repo':self.router.repo,'pull_number':1}
        if 'get_pull_request' in names:
            name = 'get_pull_request' if len(self.seen)==1 else 'get_pull_request_files'
            args = common
        elif names == {'execute_example'}:
            self.execution_attempts += 1
            name = 'execute_example'
            function = 'get_file_contents' if self.reject_first and self.execution_attempts==1 else 'is_expired'
            args = {'owner':self.router.owner,'repo':self.router.repo,'path':'module.py',
                    'calls':[{'function':function,'args':[1,1]}]}
        elif names == {'create_pull_request_review'}:
            name = 'create_pull_request_review'
            args = {**common,'event':'APPROVE','body':'No actionable defects found.'}
        else:
            findings = [{'file':'module.py','line':1,'description':'This refactor improves readability.'}] if self.bad_final else []
            return LLMResponse([{'type':'text','text':json.dumps({'decision':'APPROVE','findings':findings})}], 'end_turn', usage)
        return LLMResponse([{'type':'tool_use','id':f'call{len(self.seen)}','name':name,'input':args}], 'tool_use', usage)


class VerificationV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.row = next(r for r in read_jsonl(PROJECT/'evaluation/data/inputs.jsonl') if r['case_id']=='c85a607a54b5')
        self.models = []

    def run_model(self, **options):
        settings = dict(backend='scripted',model='unused',max_output_tokens=2048,
                        max_iterations=options.pop('max_iterations',8),temperature=0,
                        timeout=60,token_budget=options.pop('token_budget',100000),verification_version='v3')
        def factory(router):
            model = SeparateReadsModel(router, **options)
            self.models.append(model)
            return model
        self.folder = Path(self.temp.name)/'case'
        return run_case(self.row,'agent-verified',settings,self.folder,client_factory=factory)

    def test_separate_metadata_and_diff_reads_leave_execution_and_finalization(self):
        result = self.run_model()
        self.assertTrue(result['workflow']['complete'])
        self.assertEqual(result['metrics']['llm_responses'],5)
        self.assertEqual(result['metrics']['example_execution_successes'],1)
        self.assertEqual(self.models[0].seen[2:], [{'execute_example'},{'create_pull_request_review'},set()])
        self.assertLess(result['metrics']['input_tokens']+result['metrics']['output_tokens'],100000)
        self.assertLess(len(self.models[0].systems[-1]),10000)
        checks = [r for r in read_jsonl(self.folder/'requests.jsonl') if r.get('event')=='workflow_budget_check']
        execute = next(r for r in checks if r['phase']=='execute')
        self.assertLess(execute['estimated_stage_tokens']['final'],execute['estimated_stage_tokens']['execute'])

    def test_rejected_execution_gets_correction_opportunity(self):
        result = self.run_model(reject_first=True)
        self.assertTrue(result['workflow']['complete'])
        self.assertEqual(result['metrics']['example_execution_calls'],2)
        self.assertEqual(result['metrics']['example_execution_successes'],1)
        self.assertEqual(self.models[0].seen[2:4],[{'execute_example'},{'execute_example'}])

    def test_not_enough_iterations_is_explicit_failure_not_skipped_execution(self):
        result = self.run_model(max_iterations=4)
        self.assertEqual(result['termination_reason'],'insufficient_workflow_budget')
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['metrics']['submitted_reviews'],0)
        self.assertFalse(result['workflow']['complete'])

    def test_too_small_token_budget_does_not_synthesize_completion(self):
        result = self.run_model(token_budget=20000)
        self.assertEqual(result['termination_reason'],'insufficient_workflow_budget')
        self.assertFalse(result['workflow']['complete'])
        self.assertEqual(result['metrics']['example_execution_calls'],0)

    def test_inconsistent_approve_is_preserved_and_rejected(self):
        result = self.run_model(bad_final=True)
        self.assertEqual(result['error'],'invalid_final_review')
        self.assertFalse(result['workflow']['complete'])
        raw = json.loads((self.folder/'raw.json').read_text())
        self.assertEqual(len(json.loads(raw['final_response'])['findings']),1)
        self.assertIn('APPROVE requires findings: []',self.models[0].systems[-1])

    def test_premature_final_output_stays_incomplete(self):
        class EarlyFinal:
            def complete(self, **kwargs):
                return LLMResponse([{'type':'text','text':'{"decision":"APPROVE","findings":[]}'}], 'end_turn', {'input_tokens':1,'output_tokens':1})
        settings = dict(backend='scripted',model='unused',max_output_tokens=2048,max_iterations=8,
                        temperature=0,timeout=60,token_budget=100000,verification_version='v3')
        r = run_case(self.row,'agent-verified',settings,Path(self.temp.name)/'early',client_factory=lambda _:EarlyFinal())
        self.assertEqual(r['status'],'ok')
        self.assertFalse(r['workflow']['complete'])
        self.assertEqual(r['metrics']['example_execution_calls'],0)
