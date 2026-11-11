"""CP5: kiểm tra đọc incident liên quan bằng dữ liệu giả lập, không gọi API."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import SCHEMAS
from test_lab import FakeProvider, final, tool_call

ORIGIN = 'https://www.githubstatus.com/incidents/origin-alpha'
RELATED = 'https://www.githubstatus.com/incidents/linked-beta'
QUESTION = 'Điều tra incident GitHub origin-alpha, theo liên kết để tìm nguyên nhân và dẫn nguồn.'


class GraphTools:
    schemas = SCHEMAS

    def __init__(self, body=None, related_body='', fail_related=False):
        self.body = body if body is not None else 'Combined summary: ' + RELATED
        self.related_body = related_body
        self.fail_related = fail_related
        self.calls = []

    def execute(self, name, args):
        self.calls.append((name, dict(args)))
        if name != 'get_incident_details':
            return {'ok': False, 'error': 'UNKNOWN_TOOL'}
        if type(args.get('offset', 0)) is not int:
            return {'ok': False, 'error': 'INVALID_ARGUMENTS'}
        incident_id = args.get('incident_id')
        if incident_id == 'origin-alpha':
            body, url = self.body, ORIGIN
        elif incident_id == 'linked-beta':
            if self.fail_related:
                return {'ok': False, 'error': 'TimeoutError', 'message': 'Offline simulated timeout.'}
            body, url = self.related_body, RELATED
        else:
            return {'ok': False, 'error': 'INCIDENT_NOT_FOUND'}
        if args['provider'] == 'cloudflare':
            url = 'https://www.cloudflarestatus.com/incidents/' + incident_id
        return {'ok': True, 'provider': args['provider'], 'id': incident_id,
                'status': 'resolved', 'url': url, 'updates': [{'body': body}]}


def detail(call_id, incident_id, **extra):
    import json
    return tool_call(call_id, 'get_incident_details', json.dumps({
        'provider': 'github', 'incident_id': incident_id, **extra,
    }))


class RelatedIncidentTests(unittest.TestCase):
    def test_unread_link_requires_another_tool_step_before_final(self):
        provider = FakeProvider([
            detail('a', 'origin-alpha'), final('Nguồn: ' + ORIGIN),
            detail('b', 'linked-beta'), final('Đã đọc nguồn liên quan: ' + RELATED),
        ])
        result = run_agent(QUESTION, provider, GraphTools(), max_steps=4)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(t['event'] == 'validation_missing_related_incident' for t in result['trace']))
        tools = [t for t in result['trace'] if t['event'] == 'tool']
        self.assertEqual([t['arguments']['incident_id'] for t in tools], ['origin-alpha', 'linked-beta'])
        self.assertGreater(tools[1]['step'], tools[0]['step'])
        self.assertIn('linked-beta', provider.histories[2][-1]['content'])

    def test_missing_related_read_at_budget_limit_is_not_completed(self):
        provider = FakeProvider([detail('a', 'origin-alpha'), final('Nguồn: ' + ORIGIN)])
        result = run_agent(QUESTION, provider, GraphTools(), max_steps=2)
        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(result['answer'], '')

    def test_already_read_parallel_calls_do_not_force_extra_steps(self):
        first, second = detail('a', 'origin-alpha'), detail('b', 'linked-beta')
        first['calls'] += second['calls']
        first['message']['tool_calls'] += second['message']['tool_calls']
        provider = FakeProvider([first, final('Nguồn: ' + ORIGIN + ' ' + RELATED)])
        result = run_agent(QUESTION, provider, GraphTools(), max_steps=2)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(t['event'] == 'validation_missing_related_incident' for t in result['trace']))

    def test_link_cycle_does_not_repeat_incidents(self):
        tools = GraphTools(related_body='See original: ' + ORIGIN)
        provider = FakeProvider([
            detail('a', 'origin-alpha'), detail('b', 'linked-beta'), final('Nguồn: ' + RELATED),
        ])
        result = run_agent(QUESTION, provider, tools)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(tools.calls), 2)

    def test_external_or_non_incident_links_are_not_followed(self):
        urls = [
            'https://www.githubstatus.com.evil.invalid/incidents/linked-beta',
            'https://evil.invalid/incidents/linked-beta',
            'https://www.githubstatus.com/settings/linked-beta',
            'https://user:password@www.githubstatus.com/incidents/linked-beta',
            'https://www.githubstatus.com:444/incidents/linked-beta',
            'http://www.githubstatus.com/incidents/linked-beta',
            'https://www.vercel-status.com/incidents/linked-beta',
        ]
        for url in urls:
            with self.subTest(url=url):
                tools = GraphTools(body=url)
                provider = FakeProvider([detail('a', 'origin-alpha'), final('Nguồn: ' + ORIGIN)])
                result = run_agent(QUESTION, provider, tools, max_steps=2)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(len(tools.calls), 1)

    def test_summary_or_explicit_no_follow_request_does_not_force_lookup(self):
        for question in (
            'Xem trạng thái incident GitHub origin-alpha, chỉ tóm tắt bản này.',
            'Điều tra GitHub origin-alpha nhưng đừng theo liên kết.',
            "Investigate GitHub origin-alpha but don't follow links.",
        ):
            with self.subTest(question=question):
                provider = FakeProvider([detail('a', 'origin-alpha'), final('Nguồn: ' + ORIGIN)])
                result = run_agent(question, provider, GraphTools(), max_steps=2)
                self.assertEqual(result['status'], 'completed')

    def test_related_timeout_allows_partial_answer_without_retry_loop(self):
        tools = GraphTools(fail_related=True)
        provider = FakeProvider([
            detail('a', 'origin-alpha'), detail('b', 'linked-beta'),
            final('Không truy cập được incident liên quan, chưa xác minh nguyên nhân. Nguồn: ' + ORIGIN),
        ])
        result = run_agent(QUESTION, provider, tools, max_steps=3)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(tools.calls), 2)
        self.assertEqual([t for t in result['trace'] if t['event'] == 'tool'][-1]['result']['error'], 'TimeoutError')

    def test_invalid_related_arguments_still_require_valid_lookup(self):
        provider = FakeProvider([
            detail('a', 'origin-alpha'), detail('bad', 'linked-beta', offset='wrong'),
            final('Nguồn: ' + ORIGIN), detail('good', 'linked-beta'), final('Nguồn: ' + RELATED),
        ])
        result = run_agent(QUESTION, provider, GraphTools(), max_steps=5)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(t['event'] == 'validation_missing_related_incident' for t in result['trace']))

    def test_related_provider_is_selected_from_supported_url_host(self):
        import json
        cloudflare_url = 'https://www.cloudflarestatus.com/incidents/linked-beta'
        tools = GraphTools(body='Related incident: ' + cloudflare_url)
        provider = FakeProvider([
            detail('a', 'origin-alpha'), final('Nguồn: ' + ORIGIN),
            tool_call('b', 'get_incident_details', json.dumps({'provider': 'cloudflare', 'incident_id': 'linked-beta'})),
            final('Nguồn: ' + ORIGIN + ' ' + cloudflare_url),
        ])
        result = run_agent(QUESTION, provider, tools, max_steps=4)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([args['provider'] for _, args in tools.calls], ['github', 'cloudflare'])


if __name__ == '__main__':
    unittest.main()
