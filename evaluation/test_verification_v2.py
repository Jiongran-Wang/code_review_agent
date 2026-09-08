import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.example_execution import example_tool_for, execute_sources
from evaluation.fixture_router import FixtureRouter
from evaluation.finalization import FinalizationPolicy, TokenBudgetExceeded
from evaluation.run import RecordedClient, read_jsonl, run_case
from evaluation.runtime import PROJECT, LLMResponse


class VerificationV2Tests(unittest.TestCase):
    def setUp(self):
        self.rows = {r['case_id']: r for r in read_jsonl(PROJECT/'evaluation/data/inputs.jsonl')}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def execute(self, case, calls, **extra):
        r = self.rows[case]
        return execute_sources(r['base_files']['module.py'], r['head_files']['module.py'], {'calls': calls, **extra})

    def test_nested_tool_name_rejected_with_source_guidance(self):
        r = self.execute('85ad40fd5032', [{'function':'execute_example', 'args':[{'function':'collect','args':['x']}]}])
        self.assertEqual(r['head']['error_code'], 'invalid_plan')
        self.assertIn('collect', r['head']['error'])
        self.assertNotIn('observations', r['head'])
        self.assertNotIn('Executed audited', r['basis'])

    def test_source_schema_enumerates_functions_and_real_defaults(self):
        t = example_tool_for(self.rows['85ad40fd5032'])
        self.assertEqual(t['input_schema']['properties']['calls']['items']['properties']['function']['enum'], ['collect'])
        self.assertIn('collect(item, items=[])', t['description'])
        self.assertEqual(t['input_schema']['properties']['path']['enum'], ['module.py'])

    def test_bad_argument_binding_is_not_a_fixture_exception(self):
        for call in ({'function':'read_document','args':[{}, {}, {}, 'alice']},
                     {'function':'read_document','args':[]},
                     {'function':'read_document','args':[{}, 'doc', 'alice'], 'kwargs':{'user_id':'alice'}}):
            r = self.execute('9ec94bab74f0', [call])
            self.assertEqual(r['base']['error_code'], 'invalid_plan')
            self.assertIn('arguments do not bind', r['head']['error'])

    def test_function_body_typeerror_remains_an_observation(self):
        r = self.execute('6acf19efc948', [{'function':'average','args':[['text']]}])
        self.assertNotIn('error', r)
        self.assertEqual(r['head']['observations'][0]['exception'], 'TypeError')

    def test_unknown_reference_is_validation_failure(self):
        r = self.execute('85ad40fd5032', [{'function':'collect','args':['x',{'$ref':'missing'}]}])
        self.assertEqual(r['head']['error_code'], 'invalid_plan')

    def test_fixed_plan_can_follow_rejection(self):
        router = FixtureRouter(self.rows['85ad40fd5032'], execution_enabled=True, verification_version='v2')
        self.addCleanup(router.close)
        common = {'owner':router.owner, 'repo':router.repo, 'path':'module.py'}
        bad = router.execute('execute_example', {**common,'calls':[{'function':'get_file_contents','args':[]}]})
        good = router.execute('execute_example', {**common,'calls':[{'function':'collect','args':['a']},{'function':'collect','args':['b']}]})
        self.assertIn('error', bad)
        self.assertEqual(good['head']['observations'][1]['return'], ['a','b'])

    def test_finalization_reserves_submission_and_final_calls(self):
        # Simulate the observed ~18k input tokens/call. No real model or billing.
        seen = []
        class Model:
            def __init__(self, router): self.router = router
            def complete(self, messages, system=None, tools=None):
                names = {t['name'] for t in (tools or [])};seen.append(names)
                if not names:
                    return LLMResponse([{'type':'text','text':'{"decision":"COMMENT","findings":[]}'}], 'end_turn', {'input_tokens':18000,'output_tokens':100})
                name = 'create_pull_request_review' if names == {'create_pull_request_review'} else 'get_pull_request'
                args = {'owner':self.router.owner,'repo':self.router.repo,'pull_number':1}
                if name == 'create_pull_request_review':args.update(event='COMMENT',body='Protocol test',comments=[])
                return LLMResponse([{'type':'tool_use','id':f'call{len(seen)}','name':name,'input':args}], 'tool_use', {'input_tokens':18000,'output_tokens':100})
        settings = dict(backend='scripted',model='unused',max_output_tokens=2048,max_iterations=8,
                        temperature=0,timeout=60,token_budget=100000,verification_version='v2')
        folder = Path(self.temp.name)/'run'
        result = run_case(self.rows['85ad40fd5032'],'agent-verified',settings,folder,client_factory=Model)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(seen[-2:], [{'create_pull_request_review'}, set()])
        self.assertLess(result['metrics']['input_tokens']+result['metrics']['output_tokens'], 100000)
        self.assertEqual(result['metrics']['submitted_reviews'],1)
        # The harness must not fabricate execution to turn this into a success.
        self.assertFalse(result['workflow']['complete'])
        self.assertEqual([r['phase'] for r in read_jsonl(folder/'requests.jsonl') if r.get('event')=='finalization_phase'], ['submit','final'])

    def test_iteration_reserve_and_explicit_budget_stop(self):
        router = FixtureRouter(self.rows['85ad40fd5032'],execution_enabled=True,verification_version='v2')
        self.addCleanup(router.close)
        class Model:
            def complete(self, **kwargs):
                return LLMResponse([], 'tool_use', {'input_tokens':20,'output_tokens':1})
        policy = FinalizationPolicy(router, 2, 5)
        c = RecordedClient(Model(),Path(self.temp.name)/'requests.jsonl',10,finalization=policy)
        c.complete([],system='test',tools=router.tool_definitions)
        self.assertEqual(policy.phase,'submit')
        with self.assertRaises(TokenBudgetExceeded): c.complete([],system='test',tools=[])
        self.assertEqual(c.records[-1]['reason'],'token_budget_exhausted')
        self.assertIn('error',router.execute('execute_example',{}))

    def test_explicit_termination_reaches_case_artifact(self):
        class Model:
            def complete(self, **kwargs):
                return LLMResponse([], 'tool_use', {'input_tokens':20,'output_tokens':1})
        settings = dict(backend='scripted',model='unused',max_output_tokens=5,max_iterations=8,
                        temperature=0,timeout=60,token_budget=10,verification_version='v2')
        r = run_case(self.rows['85ad40fd5032'],'agent-verified',settings,Path(self.temp.name)/'budget',client_factory=lambda _:Model())
        self.assertEqual(r['termination_reason'],'token_budget_exhausted')
        self.assertEqual(r['error'],'TokenBudgetExceeded')
