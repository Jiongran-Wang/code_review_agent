import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.fixture_router import digest
from evaluation.run import (main, read_jsonl, run_case, prompt_addendum,
                            BASELINE_INSTRUCTIONS, AGENT_INSTRUCTIONS, OUTPUT_PROTOCOL)
from evaluation.runtime import PROJECT, SkillLoader


class PromptVariantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_control_is_byte_compatible_and_revised_variant_reaches_both_systems(self):
        row = read_jsonl(PROJECT / "evaluation/data/inputs.jsonl")[0]
        rubric = SkillLoader().load_combined("code-review", "code-review-triage", "code-review-analyze",
                                            "code-review-act", "code-review-memory")
        for variant in ("control", "evidence-v1"):
            for system, instruction in (("baseline", BASELINE_INSTRUCTIONS), ("agent", AGENT_INSTRUCTIONS)):
                settings = dict(backend="scripted", model="gpt-4o-mini", max_output_tokens=2048,
                                max_iterations=8, temperature=0, timeout=60, token_budget=100000,
                                prompt_variant=variant)
                folder = self.root / variant / system
                with contextlib.redirect_stdout(io.StringIO()):
                    result = run_case(row, system, settings, folder)
                self.assertEqual(result["status"], "ok")
                expected = rubric + "\n" + instruction + OUTPUT_PROTOCOL + prompt_addendum(settings)
                for record in read_jsonl(folder / "requests.jsonl"):
                    self.assertEqual(record["request"]["system"], expected)
        self.assertEqual(prompt_addendum({}), "")

    def test_manifest_hashes_actual_requested_prompts(self):
        output = self.root / "run"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--prompt-variant", "evidence-v1", "--limit", "1", "--output", str(output)]), 0)
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(manifest["settings"]["prompt_variant"], "evidence-v1")
        for path in output.glob("*/repeat-1/*/requests.jsonl"):
            system = path.parts[-4]
            prompt = read_jsonl(path)[0]["request"]["system"]
            self.assertEqual(digest(prompt), manifest["prompt_hashes"][system])

    def test_resume_preserves_variant_and_completed_work(self):
        original, resumed = self.root / "original", self.root / "resumed"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--prompt-variant", "evidence-v1", "--limit", "1", "--output", str(original)]), 0)
            self.assertEqual(main(["--resume-from", str(original), "--output", str(resumed)]), 0)
        before = json.loads((original / "manifest.json").read_text())
        after = json.loads((resumed / "manifest.json").read_text())
        self.assertEqual(before["prompt_hashes"], after["prompt_hashes"])
        self.assertEqual(after["settings"]["prompt_variant"], "evidence-v1")
        self.assertEqual(after["resumed_from"]["reused_successes"], 2)

    def test_unknown_variant_rejected(self):
        with self.assertRaises(ValueError):
            prompt_addendum({"prompt_variant": "untracked"})

    def test_verified_agent_has_tracked_prompt_tool_and_workflow(self):
        output = self.root / "verified"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--systems", "agent", "agent-verified", "--limit", "1", "--output", str(output)]), 0)
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertNotEqual(manifest['prompt_hashes']['agent'],manifest['prompt_hashes']['agent-verified'])
        for path in output.glob('*/repeat-1/*/requests.jsonl'):
            system = path.parts[-4]
            record = read_jsonl(path)[0]['request']
            names = {d['name'] for d in record['tools']}
            self.assertEqual('execute_example' in names, system=='agent-verified')
            self.assertEqual(digest(record['system']),manifest['prompt_hashes'][system])
        result = next(r for r in read_jsonl(output/'results.jsonl') if r['system']=='agent-verified')
        self.assertTrue(result['workflow']['complete'])
        self.assertEqual(result['metrics']['example_execution_successes'],1)
