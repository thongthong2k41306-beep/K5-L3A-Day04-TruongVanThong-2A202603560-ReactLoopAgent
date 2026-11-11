"""Tests cho công cụ đọc file offline; dùng file tạm, không import provider."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import review_results


def report(scores, ids=None):
    ids = ids or [f'E{index + 1}' for index in range(len(scores))]
    return {'config': {'provider': 'openrouter', 'model': 'test-model', 'judge_provider': 'openrouter',
                       'judge_model': 'test-model', 'max_steps': 8, 'dataset': 'core'},
            'cases': [{'id': case_id, 'result': {'status': 'completed' if score is not None else 'not_run',
                                               'answer': 'offline', 'trace': [], 'usage': []},
                       'grade': {'score': score, 'status': 'scored' if score is not None else 'unscored',
                                 'reason': 'offline', 'judge_usage': {}}}
                      for case_id, score in zip(ids, scores)]}


class ReviewResultsTests(unittest.TestCase):
    def load(self, contents):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            path.write_text(json.dumps(contents), encoding='utf-8-sig')
            original = path.read_bytes()
            result = review_results.load_report(path)
            self.assertEqual(path.read_bytes(), original)
            return result

    def full_report(self, score=80):
        cases = json.loads((ROOT / 'evals/cases.json').read_text(encoding='utf-8'))
        return report([score] * len(cases), [case['id'] for case in cases])

    def test_partial_results_do_not_become_full_score(self):
        data = report([100, None])
        data['summary'] = {'score_0_100': 100}
        stats = review_results.analyze_report(self.load(data))
        self.assertEqual(stats['scored_cases'], 1)
        self.assertEqual(stats['partial_mean'], 100)
        self.assertIsNone(stats['score_full_dataset'])
        self.assertEqual(stats['pending_ids'], ['E2'])

    def test_one_scored_case_is_not_a_complete_dataset(self):
        stats = review_results.analyze_report(self.load(report([97], ['E2'])))
        self.assertEqual(stats['score_in_file'], 97)
        self.assertFalse(stats['complete'])
        self.assertIsNone(stats['score_full_dataset'])

    def test_full_dataset_with_zero_score_is_complete(self):
        data = self.full_report(0)
        stats = review_results.analyze_report(self.load(data))
        self.assertTrue(stats['complete'])
        self.assertEqual(stats['score_full_dataset'], 0)

    def test_duplicate_ids_and_invalid_scores_are_rejected(self):
        invalid = [report([80, 90], ['E1', 'E1']), report([True]), report([101]), report([-1])]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.load(data)

    def test_cost_is_unknown_without_cost_fields(self):
        data = report([80])
        data['cases'][0]['result']['usage'] = [{'total_tokens': 12}]
        stats = review_results.analyze_report(self.load(data))
        self.assertEqual(stats['total_tokens'], 12)
        self.assertIsNone(stats['reported_cost'])

    def test_unscored_status_cannot_be_counted_as_scored(self):
        data = report([100])
        data['cases'][0]['grade']['status'] = 'unscored'
        with self.assertRaises(ValueError):
            self.load(data)

    def test_malformed_answer_and_tool_trace_are_rejected(self):
        invalid_answer = report([80])
        invalid_answer['cases'][0]['result']['answer'] = None
        invalid_trace = report([80])
        invalid_trace['cases'][0]['result']['trace'] = [{'event': 'tool', 'result': None}]
        for data in (invalid_answer, invalid_trace):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.load(data)

    def test_agent_and_judge_tokens_are_counted(self):
        data = report([80])
        data['cases'][0]['result']['usage'] = [{'input_tokens': 10, 'output_tokens': 2,
                                              'cache_read_input_tokens': 3, 'cost': 0}]
        data['cases'][0]['grade']['judge_usage'] = {'total_tokens': 20, 'cost': 0}
        stats = review_results.analyze_report(self.load(data))
        self.assertEqual(stats['total_tokens'], 35)
        self.assertEqual(stats['agent_calls_with_usage'], 1)
        self.assertEqual(stats['judge_calls_with_usage'], 1)
        self.assertEqual(stats['reported_cost'], 0)

    def test_comparison_rejects_different_models(self):
        before, after = self.full_report(), self.full_report()
        after['config']['model'] = 'different'
        with self.assertRaises(ValueError):
            review_results.compare_reports(before, after)

    def test_comparison_rejects_incomplete_dataset(self):
        with self.assertRaises(ValueError):
            review_results.compare_reports(report([100, None]), report([100, 100]))

    def test_comparison_uses_same_cases_in_different_order(self):
        before, after = self.full_report(80), self.full_report(90)
        after['cases'].reverse()
        comparison = review_results.compare_reports(before, after)
        self.assertEqual(comparison['score_delta'], 10)
        self.assertTrue(all(delta == 10 for delta in comparison['case_deltas'].values()))
        self.assertEqual(len(comparison['case_deltas']), 22)

    def test_cli_reads_existing_file_without_changing_it(self):
        data = copy.deepcopy(report([98], ['A1']))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            original = path.read_bytes()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(review_results.main([str(path), '--case', 'A1']), 0)
            self.assertIn('CHƯA CÓ', output.getvalue())
            self.assertIn('Case A1', output.getvalue())
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
