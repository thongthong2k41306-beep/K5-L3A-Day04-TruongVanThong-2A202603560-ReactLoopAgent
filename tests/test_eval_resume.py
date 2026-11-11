"""Checkpoint/resume dùng kết quả giả lập, không tiêu tốn LLM requests."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evals'))
import run_evals


def scored(case, args, score=80):
    item = run_evals.pending_case(case, args)
    item['result'] = {'status': 'completed', 'answer': 'Offline answer',
                      'trace': [], 'usage': [{'total_tokens': 10}]}
    item['grade'] = {'score': score, 'status': 'scored', 'reason': 'offline', 'judge_usage': {}}
    return item


class ResumeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name) / 'eval.json'
        hashes = patch.object(run_evals, 'source_hashes', return_value={'agent.py': 'version-one'})
        self.hashes = hashes.start()
        self.addCleanup(hashes.stop)

    def invoke(self, *extra):
        argv = ['run_evals.py', '--provider', 'openrouter', '--model', 'test-model',
                '--judge-provider', 'openrouter', '--judge-model', 'test-model',
                '--output', str(self.output), *extra]
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return run_evals.main()

    def report(self):
        return json.loads(self.output.read_text(encoding='utf-8'))

    def test_resume_preserves_scored_cases_and_finishes_remaining(self):
        with patch.object(run_evals, 'run_case', side_effect=scored) as run:
            self.assertEqual(self.invoke('--max-cases', '1'), 1)
            self.assertEqual(run.call_count, 1)
        first = self.report()['cases'][0]
        self.assertEqual(self.report()['summary']['total_cases'], 22)
        self.assertIsNone(self.report()['summary']['score_0_100'])
        with patch.object(run_evals, 'run_case', side_effect=scored) as run:
            self.assertEqual(self.invoke('--resume'), 0)
            self.assertEqual(run.call_count, 21)
            self.assertNotIn('E1', [call.args[0]['id'] for call in run.call_args_list])
        self.assertEqual(self.report()['cases'][0], first)
        self.assertEqual(self.report()['summary']['scored_cases'], 22)

    def test_zero_score_is_kept_instead_of_retried(self):
        with patch.object(run_evals, 'run_case', side_effect=lambda case, args: scored(case, args, 0)):
            self.invoke('--max-cases', '1')
        with patch.object(run_evals, 'run_case', side_effect=scored) as run:
            self.invoke('--resume', '--max-cases', '1')
            self.assertEqual(run.call_args.args[0]['id'], 'E2')
        self.assertEqual(self.report()['cases'][0]['grade']['score'], 0)

    def test_429_stops_without_running_other_21_cases(self):
        def limited(case, args):
            item = run_evals.pending_case(case, args)
            item['result']['status'] = 'error'
            item['result']['error'] = 'ProviderHTTPError: Provider trả HTTP 429.'
            return item
        with patch.object(run_evals, 'run_case', side_effect=limited) as run:
            self.assertEqual(self.invoke(), 1)
            self.assertEqual(run.call_count, 1)
        report = self.report()
        self.assertEqual(report['summary']['unscored_cases'], 22)
        self.assertEqual(sum(c['result']['status'] == 'not_run' for c in report['cases']), 21)

    def test_judge_retry_reuses_completed_agent_answer(self):
        def judge_limited(case, args):
            item = scored(case, args)
            item['grade'] = {'score': None, 'status': 'unscored', 'reason': 'Judge lỗi: HTTP 429'}
            return item
        with patch.object(run_evals, 'run_case', side_effect=judge_limited):
            self.invoke()
        answer = self.report()['cases'][0]['result']
        judge = Mock()
        judge.complete.return_value = {'finish': 'stop', 'calls': [], 'usage': {}, 'message': {'content': json.dumps({
            'factuality': 35, 'completeness': 20, 'evidence': 15, 'boundaries': 10,
            'reason': 'offline', 'improvement': 'offline',
        })}}
        with patch.object(run_evals, 'Provider', return_value=judge), patch.object(run_evals, 'run_case') as run:
            self.invoke('--resume', '--max-cases', '1')
            run.assert_not_called()
        self.assertEqual(self.report()['cases'][0]['result'], answer)
        self.assertEqual(self.report()['cases'][0]['grade']['score'], 80)
        judge.complete.assert_called_once()

    def test_changed_model_cannot_be_mixed_into_checkpoint(self):
        with patch.object(run_evals, 'run_case', side_effect=scored):
            self.invoke('--max-cases', '1')
        original = self.output.read_bytes()
        with self.assertRaises(SystemExit) as failure:
            self.invoke('--resume', '--model', 'another-model')
        self.assertEqual(failure.exception.code, 2)
        self.assertEqual(self.output.read_bytes(), original)

    def test_changed_source_cannot_be_mixed_into_checkpoint(self):
        with patch.object(run_evals, 'run_case', side_effect=scored):
            self.invoke('--max-cases', '1')
        original = self.output.read_bytes()
        self.hashes.return_value = {'agent.py': 'version-two'}
        with self.assertRaises(SystemExit):
            self.invoke('--resume')
        self.assertEqual(self.output.read_bytes(), original)

    def test_changed_case_selection_cannot_overwrite_checkpoint(self):
        with patch.object(run_evals, 'run_case', side_effect=scored):
            self.invoke('--max-cases', '1')
        original = self.output.read_bytes()
        with self.assertRaises(SystemExit):
            self.invoke('--resume', '--case', 'E2')
        self.assertEqual(self.output.read_bytes(), original)

    def test_interruption_preserves_completed_case(self):
        def interrupted(case, args):
            if case['id'] == 'E1':
                return scored(case, args)
            raise KeyboardInterrupt()
        with patch.object(run_evals, 'run_case', side_effect=interrupted):
            self.assertEqual(self.invoke(), 1)
        self.assertEqual(self.report()['summary']['scored_cases'], 1)
        self.assertEqual(self.report()['cases'][0]['grade']['score'], 80)

    def test_write_failure_preserves_previous_valid_file(self):
        original = '{"saved": true}\n'
        self.output.write_text(original, encoding='utf-8')
        with patch.object(run_evals.json, 'dump', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                run_evals.save_report(self.output, {'new': True})
        self.assertEqual(self.output.read_text(encoding='utf-8'), original)
        self.assertEqual(list(self.output.parent.glob('*.tmp')), [])

    def make_seed(self):
        seed_path = self.output.parent / 'e2.json'
        with patch.object(run_evals, 'run_case', side_effect=scored):
            self.assertEqual(self.invoke('--case', 'E2', '--output', str(seed_path)), 0)
        return seed_path

    def test_seed_reuses_e2_without_calling_agent_again(self):
        seed_path = self.make_seed()
        original = seed_path.read_bytes()
        source_case = json.loads(original)['cases'][0]
        with patch.object(run_evals, 'run_case', side_effect=scored) as run:
            self.assertEqual(self.invoke('--seed', str(seed_path)), 0)
            self.assertEqual(run.call_count, 21)
            self.assertNotIn('E2', [call.args[0]['id'] for call in run.call_args_list])
        copied = next(case for case in self.report()['cases'] if case['id'] == 'E2')
        self.assertEqual(copied, source_case)
        self.assertEqual(copied['grade']['score'], 80)
        self.assertEqual(seed_path.read_bytes(), original)
        self.assertEqual(self.report()['summary']['scored_cases'], 22)

    def test_seed_rejects_another_model_before_any_api_call(self):
        seed_path = self.make_seed()
        with patch.object(run_evals, 'run_case') as run, self.assertRaises(SystemExit):
            self.invoke('--seed', str(seed_path), '--model', 'different-model')
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_seed_rejects_another_source_version(self):
        seed_path = self.make_seed()
        self.hashes.return_value = {'agent.py': 'version-two'}
        with patch.object(run_evals, 'run_case') as run, self.assertRaises(SystemExit):
            self.invoke('--seed', str(seed_path))
        run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_seed_cannot_replace_an_existing_checkpoint(self):
        seed_path = self.make_seed()
        with patch.object(run_evals, 'run_case', side_effect=scored):
            self.invoke('--max-cases', '1')
        original = self.output.read_bytes()
        with patch.object(run_evals, 'run_case') as run, self.assertRaises(SystemExit):
            self.invoke('--seed', str(seed_path))
        run.assert_not_called()
        self.assertEqual(self.output.read_bytes(), original)

    def test_overlapping_seeds_are_rejected_instead_of_choosing_a_score(self):
        seed_path = self.make_seed()
        with patch.object(run_evals, 'run_case') as run, self.assertRaises(SystemExit):
            self.invoke('--seed', str(seed_path), '--seed', str(seed_path))
        run.assert_not_called()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
