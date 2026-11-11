import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import providers


class ProviderLimitTests(unittest.TestCase):
    def test_429_preserves_retry_hint_without_exposing_response_body(self):
        body = {'error': {'message': 'private-request-data',
                          'metadata': {'limit_source': 'upstream_provider_shared_pool'}}}
        error = urllib.error.HTTPError('https://example.invalid', 429, 'rate limited',
                                       {'Retry-After': '30'}, io.BytesIO(json.dumps(body).encode()))
        with patch.object(providers.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(providers.ProviderHTTPError) as failure:
                providers.post_json('https://example.invalid', {}, {})
        self.assertEqual(failure.exception.status_code, 429)
        self.assertEqual(failure.exception.retry_after, '30')
        self.assertEqual(failure.exception.limit_source, 'upstream_provider_shared_pool')
        self.assertNotIn('private-request-data', str(failure.exception))
        error.close()

    def test_non_json_429_still_returns_controlled_error(self):
        error = urllib.error.HTTPError('https://example.invalid', 429, 'rate limited', {}, io.BytesIO(b'not json'))
        with patch.object(providers.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(providers.ProviderHTTPError) as failure:
                providers.post_json('https://example.invalid', {}, {})
        self.assertEqual(failure.exception.status_code, 429)
        error.close()

    def test_free_agent_and_judge_share_request_spacing(self):
        with patch.object(providers, '_next_free_request_at', 0.0), \
                patch.object(providers.time, 'monotonic', side_effect=[100.0, 100.0, 101.0, 103.1]), \
                patch.object(providers.time, 'sleep') as sleep:
            providers._wait_for_free_request()
            providers._wait_for_free_request()
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 2.1)


if __name__ == '__main__':
    unittest.main()
