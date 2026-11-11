"""Hồi quy: model không được bỏ qua tra cứu rồi tự nêu dữ liệu status."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from bonus.tools import BonusTools
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class StatusEvidenceTests(unittest.TestCase):
    def test_unverified_answer_gets_lookup_before_completion(self):
        provider = FakeProvider([
            final('Snapshot 2026-03-06: GitHub Actions partially_degraded, incident 3gffp5yydkar.'),
            tool_call('lookup', 'get_status', '{"provider":"github","component":"Actions"}'),
            final('GitHub Actions operational theo snapshot. Nguồn: https://www.githubstatus.com'),
        ])
        result = run_agent('GitHub Actions hiện có sự cố không?', provider, StatusTools(), max_steps=3)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(t['event'] == 'validation_missing_tool' for t in result['trace']))
        observations = [t for t in result['trace'] if t['event'] == 'tool']
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]['result']['overall']['indicator'], 'none')
        self.assertNotIn('3gffp5yydkar', json.dumps(result))
        self.assertEqual(len(provider.histories), 3)

    def test_no_lookup_within_budget_is_not_completed(self):
        provider = FakeProvider([final('GitHub đang operational.'), final('GitHub đang operational.')])
        result = run_agent('Kiểm tra trạng thái GitHub.', provider, StatusTools(), max_steps=2)
        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(result['answer'], '')
        self.assertEqual(sum(t['event'] == 'validation_missing_tool' for t in result['trace']), 2)

    def test_explicit_no_tool_request_is_respected(self):
        for question in (
            'Hãy viết bài thơ về biển, đừng kiểm tra trạng thái GitHub hay Cloudflare.',
            "Write a poem; don't check GitHub status.",
        ):
            with self.subTest(question=question):
                provider = FakeProvider([final('Biển xanh, sóng vỗ bờ cát.')])
                result = run_agent(question, provider, StatusTools())
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(len(provider.histories), 1)

    def test_explanation_does_not_force_lookup(self):
        provider = FakeProvider([final('Status API cung cấp dữ liệu trạng thái của dịch vụ.')])
        result = run_agent('Status API của GitHub là gì?', provider, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(provider.histories), 1)

    def test_unsupported_provider_does_not_force_unrelated_tools(self):
        provider = FakeProvider([final('Không có tool kiểm tra Linear và Slack, chưa xác nhận được.')])
        result = run_agent('Xác nhận Linear và Slack đang outage.', provider, BonusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(provider.histories), 1)

    def test_bonus_provider_requires_lookup(self):
        provider = FakeProvider([
            final('Vercel đang operational.'),
            tool_call('lookup', 'get_vercel_status', '{}'),
            final('Theo snapshot, Vercel operational. Nguồn: https://www.vercel-status.com'),
        ])
        result = run_agent('Vercel Builds hiện có sự cố không?', provider, BonusTools(), max_steps=3)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(t.get('name') == 'get_vercel_status' for t in result['trace']))

    def test_failed_lookup_allows_honest_unavailability_answer(self):
        provider = FakeProvider([
            tool_call('lookup', 'get_status', '{"provider":"github"}'),
            final('Tool timeout, không xác nhận được trạng thái GitHub.'),
        ])
        tools = StatusTools()
        with patch.object(tools, 'execute', side_effect=TimeoutError('offline timeout')):
            result = run_agent('GitHub Actions hiện có sự cố không?', provider, tools)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(t['event'] == 'validation_missing_tool' for t in result['trace']))

    def test_unknown_tool_does_not_count_as_status_lookup(self):
        provider = FakeProvider([
            tool_call('unknown', 'unavailable_tool', '{}'),
            final('GitHub đang operational.'),
        ])
        result = run_agent('Kiểm tra trạng thái GitHub.', provider, StatusTools(), max_steps=2)
        self.assertEqual(result['status'], 'max_steps')
        self.assertTrue(any(t['event'] == 'validation_missing_tool' for t in result['trace']))


if __name__ == '__main__':
    unittest.main()
