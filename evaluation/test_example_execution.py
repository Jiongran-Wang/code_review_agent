import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.example_execution import execute_sources
from evaluation.fixture_router import FixtureRouter
from evaluation.run import read_jsonl, run_case
from evaluation.runtime import PROJECT, LLMResponse
from evaluation.workflow import assess_workflow, summarize_workflow


class ExampleExecutionTests(unittest.TestCase):
    def setUp(self):
        self.rows = {r['case_id']:r for r in read_jsonl(PROJECT / 'evaluation/data/inputs.jsonl')}

    def router(self, case_id, enabled=True):
        router = FixtureRouter(self.rows[case_id], execution_enabled=enabled)
        self.addCleanup(router.close)
        return router

    def execute(self, router, calls, **kwargs):
        return router.execute('execute_example', {'owner':router.owner,'repo':router.repo,
                              'path':'module.py','calls':calls, **kwargs})

    def test_base_head_difference_and_exception_capture(self):
        r = self.router('6acf19efc948')
        result = self.execute(r, [{'function':'average','args':[[]]}])
        self.assertIsNone(result['base']['observations'][0]['return'])
        self.assertEqual(result['head']['observations'][0]['exception'], 'ZeroDivisionError')
        self.assertNotIn('error', result)

    def test_concrete_boundary_and_data_witnesses(self):
        examples = [
            ('ebc8d8481ffc', 'page', [[10,20,30,40],1,2], [30,40], [30]),
            ('ca048d6a497e', 'prior_mean', [[1,2,3,4],2,2], 1.5, 2.5),
            ('c85a607a54b5', 'is_expired', [10,10], True, False),
            ('bca9b18b8e18', 'center', [[2,4],[100]], [[-1,1],[97]],
             [[2-106/3,4-106/3],[100-106/3]]),
        ]
        for case, function, args, expected_base, expected_head in examples:
            with self.subTest(case=case):
                result = self.execute(self.router(case), [{'function':function,'args':args}])
                self.assertEqual(result['base']['observations'][0]['return'], expected_base)
                self.assertEqual(result['head']['observations'][0]['return'], expected_head)
        result = self.execute(self.router('29d8d7cb5d4c'), [{'function':'read_document',
                              'args':[{'report':{'owner_id':'alice','body':'private'}},'report','bob']}])
        self.assertEqual(result['base']['observations'][0]['exception'],'PermissionError')
        self.assertEqual(result['head']['observations'][0]['return'],'private')

    def test_shared_default_state_and_revision_isolation(self):
        r = self.router('85ad40fd5032')
        calls = [{'function':'collect','args':['first']}, {'function':'collect','args':['second']}]
        result = self.execute(r, calls)
        self.assertEqual([x['return'] for x in result['base']['observations']], [['first'],['second']])
        self.assertEqual([x['return'] for x in result['head']['observations']], [['first'],['first','second']])
        self.assertEqual(self.execute(r, calls), result)

    def test_named_state_mutation_and_snapshot_returns(self):
        r = self.router('b3e1a991158b')
        result = self.execute(r, [{'function':'collect','args':['a',{'$ref':'items'}]},
                                 {'function':'collect','args':['b',{'$ref':'items'}]}], values={'items':[]})
        observations = result['head']['observations']
        self.assertEqual(observations[0]['return'], ['a'])
        self.assertEqual(observations[1]['values_after']['items'], ['a','b'])

    def test_sql_injection_only_uses_in_memory_rows(self):
        r = self.router('6a75289b0733')
        result = self.execute(r, [{'function':'lookup','args':[{'$ref':'connection'}, "' OR 1=1 --"]}],
                              sqlite_rows=[[1,'alice'],[2,'bob']])
        self.assertEqual(result['base']['observations'][0]['return'], [])
        self.assertEqual(result['head']['observations'][0]['return'], [[1],[2]])

    def test_sql_file_extension_functions_denied(self):
        r = self.router('6a75289b0733')
        result = self.execute(r, [{'function':'lookup','args':[{'$ref':'connection'},
                              "' UNION SELECT load_extension('/not/allowed') --"]}], sqlite_rows=[[1,'alice']])
        self.assertEqual(result['head']['observations'][0]['exception'], 'OperationalError')

    def test_unknown_source_never_starts_worker(self):
        with patch('evaluation.example_execution.subprocess.run') as process:
            result = execute_sources("import os; os.system('false')", 'def x(): return 1', {'calls':[]})
        process.assert_not_called()
        self.assertIn('error', result)

    def test_no_generated_code_or_introspection_calls(self):
        r = self.router('6acf19efc948')
        result = self.execute(r, [{'function':'__import__','args':['os']}])
        self.assertIn('error', result)
        result = self.execute(r, [{'function':'average','args':[[1]]}], values={'x':'__import__("os")'})
        self.assertEqual(result['head']['observations'][0]['return'], 1)

    def test_unadvertised_tool_and_cross_case_access_rejected(self):
        r = self.router('6acf19efc948', False)
        self.assertNotIn('execute_example', {d['name'] for d in r.tool_definitions})
        self.assertIn('error', self.execute(r, [{'function':'average','args':[[1]]}]))
        enabled = self.router('6acf19efc948')
        with patch('evaluation.fixture_router.execute_sources') as execute:
            result = enabled.execute('execute_example', {'owner':'benchmark','repo':'wrong',
                             'path':'module.py','calls':[{'function':'average','args':[[1]]}]})
        execute.assert_not_called()
        self.assertIn('error', result)

    def test_plan_count_and_call_limits(self):
        r = self.router('6acf19efc948')
        result = self.execute(r, [{'function':'average','args':[[1]]}]*13)
        self.assertIn('error', result)
        for _ in range(3):
            self.assertNotIn('error', self.execute(r, [{'function':'average','args':[[1]]}]))
        self.assertIn('four plans', self.execute(r, [{'function':'average','args':[[1]]}])['error'])

    def test_empty_env_and_time_limit(self):
        row = self.rows['6acf19efc948']
        with patch.dict(os.environ, {'OPENAI_API_KEY':'sentinel-secret'}), \
             patch('evaluation.example_execution.subprocess.run', side_effect=subprocess.TimeoutExpired('worker',3)) as process:
            result = execute_sources(row['base_files']['module.py'], row['head_files']['module.py'],
                                     {'calls':[{'function':'average','args':[[1]]}]})
        for call in process.call_args_list:
            self.assertEqual(set(call.kwargs['env']), {'PATH','PYTHONHASHSEED'})
            self.assertEqual(call.kwargs['timeout'],3)
            self.assertNotIn('sentinel-secret',str(call))
        self.assertIn('error',result)

    def test_tool_never_exposes_hidden_labels_or_oracles(self):
        r = self.router('6acf19efc948')
        result=self.execute(r,[{'function':'average','args':[[2,4]]}])
        text=json.dumps(result)
        for forbidden in ('gold_issue','oracle','reference_head','variant','trigger'):
            self.assertNotIn(forbidden,text)


class WorkflowTests(unittest.TestCase):
    def test_valid_json_is_not_agent_workflow_completion(self):
        self.assertFalse(assess_workflow('agent','ok',0)['complete'])
        self.assertFalse(assess_workflow('agent-verified','error',1)['complete'])
        self.assertFalse(assess_workflow('agent-verified','ok',1)['complete'])
        self.assertTrue(assess_workflow('agent-verified','ok',1,1)['complete'])
        self.assertTrue(assess_workflow('baseline','ok',0)['complete'])

    def test_missing_submission_keeps_detection_output_but_flags_workflow(self):
        row=read_jsonl(PROJECT/'evaluation/data/inputs.jsonl')[0]
        class FinalOnly:
            def complete(self, **kwargs):
                return LLMResponse([{'type':'text','text':'{"decision":"APPROVE","findings":[]}'}],
                                   'end_turn',{'input_tokens':1,'output_tokens':1})
        settings={'backend':'scripted','model':'gpt-4o-mini','max_output_tokens':2048,
                  'max_iterations':8,'temperature':0,'timeout':60,'token_budget':100000}
        with tempfile.TemporaryDirectory() as temp:
            result=run_case(row,'agent',settings,Path(temp)/'case',client_factory=lambda r:FinalOnly())
        self.assertEqual(result['status'],'ok')
        self.assertFalse(result['workflow']['complete'])
        self.assertEqual(summarize_workflow([{'system':'agent',**result}])['agent']['workflow_complete'],0)
