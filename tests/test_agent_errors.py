"""Kiểm tra lỗi ở ranh giới model/tool bằng test doubles, không gọi API."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class AgentErrorTests(unittest.TestCase):
    def test_provider_failure_keeps_usage_and_redacts_key(self):
        response = tool_call('a', 'get_status', '{"provider":"github"}')
        response['usage'] = {'total_tokens': 12}
        provider = Mock()
        provider.key = 'test-secret-key'
        provider.complete.side_effect = [response, RuntimeError('Rejected test-secret-key')]
        result = run_agent('Kiểm tra', provider, StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['usage'], [{'total_tokens': 12}])
        self.assertNotIn(provider.key, json.dumps(result))
        self.assertIn('RuntimeError', result['error'])
        self.assertEqual(result['trace'][-1]['step'], 2)

    def test_non_object_arguments_are_observations(self):
        for arguments in ('[]', 'null', '42', '"text"', None):
            with self.subTest(arguments=arguments):
                provider = FakeProvider([tool_call('a', 'get_status', arguments), final()])
                tools = Mock(spec=StatusTools)
                result = run_agent('Kiểm tra', provider, tools)
                self.assertEqual(result['status'], 'completed')
                tools.execute.assert_not_called()
                observation = json.loads(provider.histories[1][-1]['content'])
                self.assertEqual(observation['error'], 'INVALID_ARGUMENTS')

    def test_bad_call_does_not_skip_another_call(self):
        response = tool_call('bad', 'get_status', '{')
        good = tool_call('good', 'get_status', '{"provider":"github"}')
        response['calls'] += good['calls']
        response['message']['tool_calls'] += good['message']['tool_calls']
        provider = FakeProvider([response, final()])
        result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=2)
        self.assertEqual(result['status'], 'completed')
        observations = provider.histories[1][-2:]
        self.assertEqual([m['tool_call_id'] for m in observations], ['bad', 'good'])
        self.assertEqual(json.loads(observations[0]['content'])['error'], 'INVALID_ARGUMENTS')
        self.assertEqual(json.loads(observations[1]['content'])['provider'], 'github')

    def test_tool_exception_is_returned_to_model(self):
        provider = FakeProvider([
            tool_call('a', 'get_status', '{"provider":"github"}'), final('Không lấy được dữ liệu.'),
        ])
        tools = StatusTools()
        with patch.object(tools, 'execute', side_effect=TimeoutError('offline timeout')):
            result = run_agent('Kiểm tra', provider, tools)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['trace'][1]['result']['error'], 'TimeoutError')
        self.assertEqual(json.loads(provider.histories[1][-1]['content'])['error'], 'TimeoutError')

    def test_truncated_response_does_not_execute_tools(self):
        response = tool_call('a', 'get_status', '{"provider":"github"}')
        response['finish'] = 'length'
        tools = Mock(spec=StatusTools)
        result = run_agent('Kiểm tra', FakeProvider([response]), tools)
        self.assertEqual(result['status'], 'error')
        tools.execute.assert_not_called()

    def test_invalid_tool_results_are_returned_as_errors(self):
        for observation in (None, {'data': {1, 2}}):
            with self.subTest(observation=observation):
                provider = FakeProvider([
                    tool_call('a', 'get_status', '{"provider":"github"}'), final(),
                ])
                tools = StatusTools()
                with patch.object(tools, 'execute', return_value=observation):
                    result = run_agent('Kiểm tra', provider, tools)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(json.loads(provider.histories[1][-1]['content'])['error'],
                                 'INVALID_TOOL_RESULT')
                json.dumps(result)

    def test_invalid_budget_does_not_call_provider(self):
        for budget in (0, -1, True, 1.5):
            with self.subTest(budget=budget):
                provider = Mock()
                result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=budget)
                self.assertEqual(result['status'], 'error')
                provider.complete.assert_not_called()

    def test_invalid_or_empty_model_output_is_not_completed(self):
        responses = [None, {}, {'message': {'role': 'user'}, 'finish': 'stop'},
                     final(''), final('   ')]
        no_calls = final()
        no_calls['finish'] = 'tool_calls'
        responses.append(no_calls)
        for response in responses:
            with self.subTest(response=response):
                result = run_agent('Kiểm tra', FakeProvider([response]), StatusTools())
                self.assertEqual(result['status'], 'error')


if __name__ == '__main__':
    unittest.main()
