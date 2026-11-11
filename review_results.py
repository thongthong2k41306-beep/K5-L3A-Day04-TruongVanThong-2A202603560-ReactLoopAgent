"""Đọc/so sánh file eval offline. Không import provider, đọc .env hay gọi mạng."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_report(path):
    report = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(report, dict) or not isinstance(report.get('config'), dict):
        raise ValueError('File cần có config và cases của eval runner.')
    cases = report.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('Danh sách cases phải là list không rỗng.')
    ids = set()
    for item in cases:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
            raise ValueError('Case thiếu ID hợp lệ.')
        if item['id'] in ids:
            raise ValueError(f'ID case bị trùng: {item["id"]}.')
        ids.add(item['id'])
        if not isinstance(item.get('grade'), dict) or 'score' not in item['grade']:
            raise ValueError(f'Case {item["id"]} thiếu grade.score.')
        score = item['grade']['score']
        if score is not None and (not is_number(score) or not 0 <= score <= 100):
            raise ValueError(f'Điểm case {item["id"]} không hợp lệ.')
        grade_status = item['grade'].get('status')
        if grade_status not in ('scored', 'unscored') or ((score is None) != (grade_status == 'unscored')):
            raise ValueError(f'Điểm và trạng thái chấm của case {item["id"]} không khớp.')
        result = item.get('result', {})
        if not isinstance(result, dict):
            raise ValueError(f'Result của case {item["id"]} phải là dict.')
        if not isinstance(result.get('answer', ''), str):
            raise ValueError(f'Answer của case {item["id"]} phải là string.')
        trace = result.get('trace', [])
        if not isinstance(trace, list) or not all(isinstance(event, dict) for event in trace):
            raise ValueError(f'Trace của case {item["id"]} phải là list các dict.')
        if any(event.get('event') == 'tool' and not isinstance(event.get('result'), dict) for event in trace):
            raise ValueError(f'Tool result trong case {item["id"]} phải là dict.')
        usage = result.get('usage', [])
        if not isinstance(usage, list) or not all(isinstance(entry, dict) for entry in usage):
            raise ValueError(f'Usage của case {item["id"]} phải là list các dict.')
        if not isinstance(item['grade'].get('judge_usage', {}), dict):
            raise ValueError(f'Judge usage của case {item["id"]} phải là dict.')
    return report


def token_count(usage):
    if is_number(usage.get('total_tokens')):
        return usage['total_tokens']
    # Usage Anthropic tách input, output và cache thay vì total_tokens.
    return sum(usage.get(name, 0) for name in (
        'input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'
    ) if is_number(usage.get(name, 0)))


def usage_totals(report):
    agent = [entry for case in report['cases'] for entry in case.get('result', {}).get('usage', [])]
    judge = [case['grade']['judge_usage'] for case in report['cases'] if case['grade'].get('judge_usage')]
    entries = agent + judge
    costs = [entry['cost'] for entry in entries if is_number(entry.get('cost'))]
    return {'agent_calls_with_usage': len(agent), 'judge_calls_with_usage': len(judge),
            'total_tokens': sum(token_count(entry) for entry in entries),
            'reported_cost': sum(costs) if costs else None, 'cost_responses': len(costs)}


def analyze_report(report):
    dataset = report['config'].get('dataset')
    if dataset not in ('core', 'bonus'):
        raise ValueError('config.dataset phải là core hoặc bonus.')
    definition = ROOT / ('evals/cases.json' if dataset == 'core' else 'bonus/cases.json')
    expected_ids = {case['id'] for case in json.loads(definition.read_text(encoding='utf-8'))}
    cases = report['cases']
    ids = {case['id'] for case in cases}
    if not ids <= expected_ids:
        raise ValueError('File chứa case không thuộc dataset đã chọn.')
    scores = [case['grade']['score'] for case in cases if case['grade']['score'] is not None]
    all_scored = len(scores) == len(cases)
    full_dataset = ids == expected_ids
    mean = round(sum(scores) / len(scores), 2) if scores else None
    return {'total_cases': len(cases), 'expected_cases': len(expected_ids), 'scored_cases': len(scores),
            'pending_ids': [case['id'] for case in cases if case['grade']['score'] is None],
            'score_in_file': mean if all_scored else None,
            'score_full_dataset': mean if all_scored and full_dataset else None,
            'partial_mean': mean if not all_scored else None,
            'complete': all_scored and full_dataset, **usage_totals(report)}


def compare_reports(before, after):
    if before['config'] != after['config']:
        raise ValueError('Hai file khác cấu hình; không so sánh như một thí nghiệm trước/sau.')
    first, second = analyze_report(before), analyze_report(after)
    if not first['complete'] or not second['complete']:
        raise ValueError('Cần chấm đủ toàn bộ dataset ở cả hai file trước khi so sánh điểm tổng.')
    old = {case['id']: case['grade']['score'] for case in before['cases']}
    new = {case['id']: case['grade']['score'] for case in after['cases']}
    return {'before': first, 'after': second,
            'score_delta': round(second['score_full_dataset'] - first['score_full_dataset'], 2),
            'case_deltas': {case_id: round(new[case_id] - old[case_id], 2) for case_id in old}}


def show_report(path, report):
    stats = analyze_report(report)
    print(f'File: {path}')
    print(f'Model: {report["config"].get("model")} | Judge: {report["config"].get("judge_model")}')
    print(f'Đã chấm {stats["scored_cases"]}/{stats["total_cases"]} case trong file; dataset có {stats["expected_cases"]} case.')
    print(f'Điểm toàn bộ dataset: {stats["score_full_dataset"] if stats["complete"] else "CHƯA CÓ"}')
    if stats['partial_mean'] is not None:
        print(f'Trung bình tạm của các case đã chấm: {stats["partial_mean"]} (không phải điểm toàn bộ).')
    elif not stats['complete'] and stats['score_in_file'] is not None:
        print(f'Điểm trong file chạy riêng lẻ: {stats["score_in_file"]} (chưa đủ dataset).')
    print('Case chưa chấm: ' + (', '.join(stats['pending_ids']) or 'không có trong file'))
    print(f'Lượt model có usage: agent={stats["agent_calls_with_usage"]}, judge={stats["judge_calls_with_usage"]}.')
    print(f'Tổng token có ghi nhận: {stats["total_tokens"]}.')
    if stats['reported_cost'] is None:
        print('Chi phí: file không có thông tin cost; không suy ra là miễn phí.')
    else:
        print(f'Chi phí API ghi nhận: {stats["reported_cost"]:.6f} USD, từ {stats["cost_responses"]} usage records có cost.')
    print('Các số liệu usage không bao gồm yêu cầu lỗi không trả usage; đây không phải quota tài khoản.')
    for case in report['cases']:
        if case['grade']['score'] is None:
            result = case.get('result', {})
            detail = result.get('error') or case['grade'].get('reason', 'Chưa chấm.')
            print(f'  {case["id"]}: {result.get("status", "unknown")} — {detail}')
    scored = sorted((case for case in report['cases'] if case['grade']['score'] is not None),
                    key=lambda case: case['grade']['score'])
    if scored:
        print('Case điểm thấp để đọc trace: ' + ', '.join(f'{case["id"]}={case["grade"]["score"]}' for case in scored[:5]))


def show_case(report, case_id):
    case = next((item for item in report['cases'] if item['id'] == case_id.upper()), None)
    if case is None:
        raise ValueError(f'Không có case {case_id} trong file.')
    result, grade = case.get('result', {}), case['grade']
    print(f'\nCase {case["id"]} — score={grade["score"]}, status={result.get("status")}:')
    print('Câu hỏi:', case.get('question', ''))
    print('Nhận xét judge:', grade.get('reason', ''))
    print('Gợi ý judge (cần đối chiếu evidence):', grade.get('improvement', ''))
    print('Câu trả lời:\n' + result.get('answer', ''))
    for event in result.get('trace', []):
        if event.get('event') != 'tool':
            continue
        observation = event.get('result', {})
        print('Tool evidence:', json.dumps({
            'step': event.get('step'), 'name': event.get('name'), 'arguments': event.get('arguments'),
            'provider': observation.get('provider'), 'id': observation.get('id'),
            'status': observation.get('status'), 'captured_at': observation.get('captured_at'),
            'source': observation.get('url') or observation.get('source'), 'error': observation.get('error'),
        }, ensure_ascii=False))


def main(argv=None):
    # PowerShell/redirect trên Windows có thể dùng encoding không hỗ trợ tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Đọc/so sánh eval hoàn toàn offline, không gọi API.')
    parser.add_argument('report', help='Ví dụ eval_before.json')
    parser.add_argument('--case', help='Xem câu trả lời và tool evidence của một case')
    parser.add_argument('--compare', help='File lần hai, ví dụ eval_after.json')
    args = parser.parse_args(argv)
    try:
        report = load_report(args.report)
        show_report(args.report, report)
        if args.case:
            show_case(report, args.case)
        if args.compare:
            other = load_report(args.compare)
            comparison = compare_reports(report, other)
            print(f'\nĐiểm trước/sau: {comparison["before"]["score_full_dataset"]} → {comparison["after"]["score_full_dataset"]}')
            print(f'Chênh lệch điểm tổng: {comparison["score_delta"]:+.2f}')
            print(f'Token trước/sau: {comparison["before"]["total_tokens"]} → {comparison["after"]["total_tokens"]}')
            for case_id, delta in comparison['case_deltas'].items():
                print(f'  {case_id}: {delta:+.2f}')
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
