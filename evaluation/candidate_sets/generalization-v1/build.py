"""Build and validate authored candidate fixtures; never call a model.

Run from this directory or the project root. Only source authored below executes.
This is process isolation, not a sandbox for arbitrary user-supplied source.
"""
import difflib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parent
VERSION = 'generalization-candidate-v1'

def code(s):
    return dedent(s).strip() + '\n'


SEEDS = [
dict(family='weighted_mean_denominator', category='numerical_correctness',
 title='Refactor weighted summary calculation',
 contract='weighted_mean(values, weights): equally sized nonempty lists of finite numbers; weights are nonnegative and their sum is positive. Return sum(value * weight) / sum(weights). Do not mutate either input.',
 base='''
 def weighted_mean(values, weights):
     return sum(v * w for v, w in zip(values, weights)) / sum(weights)
 ''', clean='''
 def weighted_mean(values, weights):
     weighted_total = sum(v * w for v, w in zip(values, weights))
     denominator = sum(weights)
     return weighted_total / denominator
 ''', good='denominator = sum(weights)', bad='denominator = len(weights)',
 description='Dividing by the number of weights rather than their sum mis-scales a weighted mean with non-unit total weight.',
 regression='assert m.weighted_mean([10, 20], [1, 1]) == 15',
 trigger='assert m.weighted_mean([10, 20], [1, 3]) == 17.5\nassert m.weighted_mean([10, 20], [2, 6]) == 17.5'),
dict(family='sample_variance_ddof', category='numerical_correctness',
 title='Separate variance calculation steps',
 contract='sample_variance(values): at least two finite numeric observations. Return unbiased sample variance, dividing the sum of squared deviations by n - 1. Preserve the input.',
 base='''
 def sample_variance(values):
     mean = sum(values) / len(values)
     return sum((x - mean) ** 2 for x in values) / (len(values) - 1)
 ''', clean='''
 def sample_variance(values):
     count = len(values)
     mean = sum(values) / count
     squared_error = sum((x - mean) ** 2 for x in values)
     return squared_error / (count - 1)
 ''', good='return squared_error / (count - 1)', bad='return squared_error / count',
 description='Dividing by n computes population variance instead of the required unbiased sample variance, underestimating nonzero sample variance.',
 regression='assert m.sample_variance([3, 3, 3]) == 0',
 trigger='assert m.sample_variance([1, 3]) == 2\nassert m.sample_variance([2, 4, 6]) == 4'),
dict(family='confusion_matrix_recall', category='ml_metric_correctness',
 title='Name binary classification counts',
 contract='positive_recall(matrix): a 2x2 matrix of nonnegative integer counts, with rows=true class and columns=predicted class, ordered negative then positive. At least one actual positive exists. Return TP / (TP + FN).',
 base='''
 def positive_recall(matrix):
     return matrix[1][1] / (matrix[1][0] + matrix[1][1])
 ''', clean='''
 def positive_recall(matrix):
     true_positive = matrix[1][1]
     false_negative = matrix[1][0]
     return true_positive / (true_positive + false_negative)
 ''', good='false_negative = matrix[1][0]', bad='false_negative = matrix[0][1]',
 description='Reads false positives instead of false negatives, computing precision rather than recall and potentially dividing by zero despite actual positives.',
 regression='assert m.positive_recall([[5, 0], [0, 4]]) == 1',
 trigger='assert m.positive_recall([[8, 2], [3, 7]]) == 0.7\nassert m.positive_recall([[8, 0], [3, 0]]) == 0'),
dict(family='drawdown_running_peak', category='temporal_correctness',
 title='Refactor drawdown accumulation',
 contract='max_drawdown(values): a nonempty chronological sequence of finite positive portfolio values. Return the largest fractional fall from a peak seen at or before each observation; future peaks cannot be used for earlier observations.',
 base='''
 def max_drawdown(values):
     peak = values[0]
     worst = 0.0
     for value in values:
         if value > peak:
             peak = value
         worst = max(worst, (peak - value) / peak)
     return worst
 ''', clean='''
 def max_drawdown(values):
     peak = values[0]
     worst = 0.0
     for value in values:
         peak = max(peak, value)
         decline = (peak - value) / peak
         worst = max(worst, decline)
     return worst
 ''', good='peak = max(peak, value)', bad='peak = max(values)',
 description='Uses the full-series peak for earlier observations, introducing future information and overstating drawdown before a later peak.',
 regression='assert m.max_drawdown([100, 80, 60]) == 0.4',
 trigger='assert m.max_drawdown([100, 90, 120]) == 0.1\nassert m.max_drawdown([100, 110, 120]) == 0'),
dict(family='asof_latest_observation', category='temporal_correctness',
 title='Separate historical quote filtering',
 contract='asof_value(observations, timestamp): observations are [time, value] pairs sorted by unique increasing finite numeric time; values and timestamp are finite numbers. Return the value at the latest time <= timestamp, or None if there is no eligible observation.',
 base='''
 def asof_value(observations, timestamp):
     for time, value in reversed(observations):
         if time <= timestamp:
             return value
     return None
 ''', clean='''
 def asof_value(observations, timestamp):
     eligible = [pair for pair in observations if pair[0] <= timestamp]
     if not eligible:
         return None
     return eligible[-1][1]
 ''', good='return eligible[-1][1]', bad='return eligible[0][1]',
 description='Returns the oldest eligible quote instead of the latest, yielding stale values whenever multiple observations precede the query time.',
 regression='assert m.asof_value([[1, 10], [3, 30]], 2) == 10\nassert m.asof_value([], 2) is None',
 trigger='assert m.asof_value([[1, 10], [3, 30], [5, 50]], 4) == 30\nassert m.asof_value([[1, 10], [3, 30]], 3) == 30'),
dict(family='sql_literal_prefix', category='query_correctness',
 title='Separate prefix query preparation',
 contract='prefix_users(connection, prefix): users has integer id and text name columns. Names and nonempty prefix use uppercase ASCII letters, digits, _, %, ! only. Return [(id,), ...] in ascending id order for names starting with the literal prefix; %, _ and ! in input are ordinary characters, not pattern operators.',
 base='''
 def prefix_users(connection, prefix):
     pattern = prefix.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
     return connection.execute("SELECT id FROM users WHERE name LIKE ? ESCAPE '!' ORDER BY id", (pattern,)).fetchall()
 ''', clean='''
 def prefix_users(connection, prefix):
     escaped = prefix.replace('!', '!!').replace('%', '!%').replace('_', '!_')
     pattern = escaped + '%'
     query = "SELECT id FROM users WHERE name LIKE ? ESCAPE '!' ORDER BY id"
     return connection.execute(query, (pattern,)).fetchall()
 ''', good="pattern = escaped + '%'", bad="pattern = prefix + '%'",
 description='Drops LIKE escaping, so literal underscore and percent prefixes match unrelated names even though SQL parameters remain bound.',
 setup='''
 import sqlite3
 connection = sqlite3.connect(':memory:')
 connection.execute('CREATE TABLE users (id INTEGER, name TEXT)')
 connection.executemany('INSERT INTO users VALUES (?, ?)', [(1,'A_ONE'), (2,'AXONE'), (3,'BETA'), (4,'A%TWO'), (5,'A!THREE')])
 ''', regression="assert m.prefix_users(connection, 'B') == [(3,)]",
 trigger="assert m.prefix_users(connection, 'A_') == [(1,)]\nassert m.prefix_users(connection, 'A%') == [(4,)]\nassert m.prefix_users(connection, 'A!') == [(5,)]"),
dict(family='scoped_permission_conjunction', category='authorization',
 title='Simplify scoped access decision',
 contract='can_access(same_tenant, has_read_permission): both arguments are booleans. Grant access only when the requester belongs to the same tenant AND has read permission; otherwise deny. Return a bool.',
 base='''
 def can_access(same_tenant, has_read_permission):
     if not same_tenant:
         return False
     return has_read_permission
 ''', clean='''
 def can_access(same_tenant, has_read_permission):
     allowed = same_tenant and has_read_permission
     return allowed
 ''', good='allowed = same_tenant and has_read_permission', bad='allowed = same_tenant or has_read_permission',
 description='OR grants access when only one required permission condition holds, permitting cross-tenant or unprivileged access.',
 regression='assert m.can_access(True, True) is True\nassert m.can_access(False, False) is False',
 trigger='assert m.can_access(False, True) is False\nassert m.can_access(True, False) is False'),
dict(family='ranking_input_mutation', category='state_management',
 title='Separate score ranking steps',
 contract='rank_scores(scores): scores is a list of finite numbers, possibly empty. Return a new list sorted descending and leave the caller input unchanged.',
 base='''
 def rank_scores(scores):
     return sorted(scores, reverse=True)
 ''', clean='''
 def rank_scores(scores):
     ranked = list(scores)
     ranked.sort(reverse=True)
     return ranked
 ''', good='ranked = list(scores)', bad='ranked = scores',
 description='Aliases the caller list before an in-place sort, mutating the input and returning the same list instead of an independent ranked copy.',
 regression='assert m.rank_scores([3, 2, 1]) == [3, 2, 1]\nassert m.rank_scores([]) == []',
 trigger='scores = [1, 3, 2]\nresult = m.rank_scores(scores)\nassert result == [3, 2, 1]\nassert scores == [1, 3, 2]\nassert result is not scores'),
]


def records():
    inputs, labels = [], []
    for s in SEEDS:
        base, clean = code(s['base']), code(s['clean'])
        assert clean.count(s['good']) == 1
        buggy = clean.replace(s['good'], s['bad'])
        for variant, head in [('clean', clean), ('defect', buggy)]:
            case = hashlib.sha256((VERSION+s['family']+variant).encode()).hexdigest()[:12]
            patch = ''.join(difflib.unified_diff(base.splitlines(True), head.splitlines(True),fromfile='a/module.py',tofile='b/module.py'))
            inputs.append(dict(case_id=case, pr={'title':s['title'],'body':s['contract']},base_files={'module.py':base},head_files={'module.py':head},changed_files=[{'filename':'module.py','status':'modified','patch':patch}]))
            line = next((i for i,t in enumerate(head.splitlines(),1) if t.strip()==s['bad']),None)
            issues = [] if variant=='clean' else [dict(issue_id=case+':1',file='module.py',line_start=line,line_end=line,category=s['category'],severity='medium',description=s['description'])]
            labels.append(dict(case_id=case,version=VERSION,split='candidate_unrun',group_id=s['family'],variant=variant,provenance='assistant-authored candidate; human validation pending; not an independent holdout',issues=issues,oracle={'setup':code(s.get('setup','')),'regression':code(s['regression']),'trigger':code(s['trigger'])},reference_head_files={'module.py':clean}))
    return sorted(inputs,key=lambda x:x['case_id']), sorted(labels,key=lambda x:x['case_id'])


def check(source, oracle, name):
    script = 'import types\nm = types.ModuleType("subject")\n'
    script += f'exec(compile({source!r}, "module.py", "exec"), m.__dict__)\n'
    script += oracle['setup'] + '\n' + oracle[name]
    with tempfile.TemporaryDirectory(prefix='candidate-oracle-') as temp:
        result = subprocess.run([sys.executable,'-I','-c',script],cwd=temp,
            env={'PATH':os.defpath,'PYTHONHASHSEED':'0'},capture_output=True,text=True,timeout=5)
    return result.returncode==0, result.stderr


def main():
    inputs, labels = records()
    # Validate all output before writing it. Existing differing artifacts require
    # an explicit new candidate version, rather than silently replacing labels.
    old = Path(__file__).resolve().parents[2]/'data/inputs.jsonl'
    existing = [json.loads(s) for s in old.read_text().splitlines()]
    assert not {r['case_id'] for r in inputs} & {r['case_id'] for r in existing}
    old_sources = {s for r in existing for v in ('base_files','head_files') for s in r[v].values()}
    checks = []
    by = {r['case_id']:r for r in inputs}
    for label in labels:
        row = by[label['case_id']]
        for revision, source in [('base',row['base_files']['module.py']),('head',row['head_files']['module.py']),('reference',label['reference_head_files']['module.py'])]:
            assert source not in old_sources
            compile(source,'module.py','exec')
            for name in ('regression','trigger'):
                passed, stderr = check(source,label['oracle'],name)
                expected = not (revision=='head' and label['variant']=='defect' and name=='trigger')
                assert passed==expected, (label['case_id'],revision,name,stderr)
                if not passed: assert 'AssertionError' in stderr, stderr
                checks.append({'case_id':label['case_id'],'revision':revision,'check':name,'passed':passed,'expected_pass':expected})
    for filename, rows in [('inputs.jsonl',inputs),('labels.jsonl',labels)]:
        text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
        target=ROOT/filename
        if target.exists(): assert target.read_text()==text, 'Existing candidate data differs; version the change'
        else: target.write_text(text)
    sources = sorted({hashlib.sha256(s.encode()).hexdigest() for r in inputs for v in ('base_files','head_files') for s in r[v].values()})
    payload = {'status':'reference_checks_passed','cases':len(inputs),'families':len(SEEDS),'revision_checks':len(checks),'agent_evaluated':False,'human_validated':False,'execution_registry_integrated':False,'source_hashes':sources,'checks':checks}
    (ROOT/'validation.json').write_text(json.dumps(payload,indent=2)+'\n')
    (ROOT/'human-review.json').write_text(json.dumps({'status':'PENDING','reviewer':None,'cases':[{'case_id':r['case_id'],'contract_correct':None,'label_correct':None,'oracle_correct':None,'additional_defects':None,'notes':''} for r in labels]},indent=2)+'\n') if not (ROOT/'human-review.json').exists() else None
    print(json.dumps({k:v for k,v in payload.items() if k not in ('checks','source_hashes')},indent=2))


if __name__=='__main__': main()
