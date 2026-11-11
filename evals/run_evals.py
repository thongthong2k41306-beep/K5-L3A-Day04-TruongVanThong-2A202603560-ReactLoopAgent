"""Chạy và chấm eval. expected chỉ cung cấp cho judge, không gửi cho agent."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from providers import Provider
from scenarios import ScenarioTools
from grading import grade_case, summarize, bonus_points
from bonus.tools import BonusTools


def source_hashes():
    """Không trộn kết quả các phiên bản agent/dataset khi resume."""
    root = Path(__file__).resolve().parents[1]
    names = ('agent.py', 'providers.py', 'status_tools.py', 'bonus/tools.py',
             'evals/cases.json', 'bonus/cases.json', 'evals/scenarios.py', 'evals/grading.py')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def save_report(path, report):
    """Thay file sau khi ghi xong để giữ checkpoint trước nếu bị ngắt."""
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def pending_case(case, args):
    return {'id': case['id'], 'question': case['question'], 'expected': case['expected'],
            'scenario': case.get('scenario', 'normal'), 'provider': args.provider, 'model': args.model,
            'judge_provider': args.judge_provider, 'judge_model': args.judge_model,
            'result': {'status': 'not_run', 'answer': '', 'trace': [], 'usage': []},
            'grade': {'score': None, 'status': 'unscored', 'reason': 'Case chưa được chạy.', 'judge_usage': {}}}


def rate_limited(item):
    return any('HTTP 429' in str(message) for message in (
        item.get('result', {}).get('error', ''), item.get('grade', {}).get('reason', '')))


def load_seed(path, config, hashes, selected):
    """Đọc nguyên kết quả case đã chạy, chỉ nhận cùng cấu hình và phiên bản."""
    report = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(report, dict) or report.get('config') != config:
        raise ValueError('File --seed khác cấu hình model/judge/max-steps/dataset.')
    if report.get('source_hashes') != hashes:
        raise ValueError('File --seed khác mã nguồn/dataset hoặc thiếu hash.')
    entries = report.get('cases')
    if not isinstance(entries, list) or not entries:
        raise ValueError('File --seed thiếu danh sách cases hợp lệ.')
    definitions = {case['id']: case for case in selected}
    imported = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            raise ValueError('File --seed có case thiếu ID hợp lệ.')
        case_id = item['id']
        if case_id not in definitions or case_id in imported:
            raise ValueError('File --seed chứa case ngoài lựa chọn hoặc ID trùng.')
        if any(item.get(field) != definitions[case_id][field] for field in ('question', 'expected')):
            raise ValueError('Nội dung case trong --seed khác dataset hiện tại.')
        if any(item.get(field) != config[field] for field in ('provider', 'model', 'judge_provider', 'judge_model')):
            raise ValueError('Thông tin model trong case --seed không khớp cấu hình.')
        grade = item.get('grade')
        if not isinstance(grade, dict) or 'score' not in grade or not isinstance(item.get('result'), dict):
            raise ValueError('Case --seed thiếu grade/result hợp lệ.')
        score = grade['score']
        if score is None:
            if grade.get('status') != 'unscored':
                raise ValueError('Case --seed chưa có điểm nhưng không được ghi là unscored.')
        elif type(score) not in (int, float) or not 0 <= score <= 100 or grade.get('status') != 'scored':
            raise ValueError('Điểm/trạng thái case --seed không hợp lệ.')
        imported[case_id] = item
    return imported


def grade_existing_case(case, args, previous):
    """Nếu agent đã completed, retry judge mà không gọi lại agent."""
    item = dict(previous)
    try:
        item['grade'] = grade_case(case, item['result'], Provider(args.judge_provider, args.judge_model))
    except Exception as exc:
        item['grade'] = {'score': None, 'status': 'unscored', 'reason': str(exc)[:200], 'judge_usage': {}}
    return item


def run_case(case, args):
    try:
        result = run_agent(case['question'], Provider(args.provider, args.model),
                           (BonusTools('snapshot', scenario=case.get('scenario', 'normal')) if getattr(args, 'bonus', False) else ScenarioTools(case.get('scenario', 'normal'), case.get('fail', False))), max_steps=args.max_steps)
    except Exception as exc:
        result = {'status': 'error', 'answer': '', 'trace': [], 'usage': [], 'error': f'{type(exc).__name__}: {str(exc)[:200]}'}
    if not isinstance(result, dict) or not isinstance(result.get('trace', []), list):
        result = {'status': 'error', 'answer': '', 'trace': [], 'usage': [], 'error': 'run_agent trả kết quả không hợp lệ.'}
    try:
        judge = Provider(args.judge_provider, args.judge_model)
        grade = grade_case(case, result, judge)
    except Exception as exc:
        grade = {'score': None, 'status': 'unscored', 'reason': str(exc), 'judge_usage': {}}
    return {'id': case['id'], 'question': case['question'], 'expected': case['expected'],
            'scenario': case.get('scenario', 'normal'), 'provider': args.provider, 'model': args.model,
            'judge_provider': args.judge_provider, 'judge_model': args.judge_model, 'result': result, 'grade': grade}


def main():
    parser = argparse.ArgumentParser(description='Chạy agent và chấm eval 0–100')
    choices = ['openai', 'gemini', 'anthropic', 'openrouter']
    parser.add_argument('--provider', choices=choices, default=os.getenv('PROVIDER', 'openai'))
    parser.add_argument('--model', default=os.getenv('MODEL'))
    parser.add_argument('--judge-provider', choices=choices, default=os.getenv('JUDGE_PROVIDER'))
    parser.add_argument('--judge-model', default=os.getenv('JUDGE_MODEL'))
    parser.add_argument('--bonus', action='store_true', help='Chạy bộ bonus riêng; không ảnh hưởng điểm chính')
    parser.add_argument('--case', help='Ví dụ E2 hoặc H1; bỏ trống để chạy toàn bộ')
    parser.add_argument('--max-steps', type=int, default=None, help='Giới hạn model calls mỗi case: mặc định 8, bonus 16')
    parser.add_argument('--workers', type=int, default=1, help='Số case chạy đồng thời (mặc định 1)')
    parser.add_argument('--resume', action='store_true', help='Giữ case đã chấm, chạy tiếp case chưa chấm trong --output')
    parser.add_argument('--seed', action='append', default=[], help='Nạp kết quả chạy riêng cùng phiên bản vào output mới; có thể lặp lại')
    parser.add_argument('--max-cases', type=int, help='Giới hạn số case chạy trong lần này; các case còn lại vẫn chưa chấm')
    parser.add_argument('--output', default='eval_results.json')
    args = parser.parse_args()
    args.judge_provider = args.judge_provider or args.provider
    args.judge_model = args.judge_model or args.model
    if not args.model or not args.judge_model:
        parser.error('Thiếu --model hoặc MODEL')
    args.max_steps = args.max_steps if args.max_steps is not None else (16 if args.bonus else 8)
    if args.max_steps < 1 or not 1 <= args.workers <= 8:
        parser.error('--max-steps phải >= 1 và --workers phải từ 1 đến 8')
    if args.max_cases is not None and args.max_cases < 1:
        parser.error('--max-cases phải >= 1')
    if args.seed and args.resume:
        parser.error('--seed chỉ dùng để bắt đầu output mới; các lần tiếp theo dùng --resume.')
    if args.seed and Path(args.output).exists():
        parser.error('Output đã tồn tại; dùng --resume để giữ các case đã có hoặc chọn file output mới.')
    cases_path = (Path(__file__).resolve().parents[1] / 'bonus' / 'cases.json') if args.bonus else (Path(__file__).parent / 'cases.json')
    cases = json.loads(cases_path.read_text(encoding='utf-8'))
    selected = [c for c in cases if not args.case or c['id'] == args.case.upper()]
    if not selected:
        parser.error('Không tìm thấy case')
    config = {'provider': args.provider, 'model': args.model,
              'judge_provider': args.judge_provider, 'judge_model': args.judge_model,
              'max_steps': args.max_steps, 'dataset': 'bonus' if args.bonus else 'core'}
    hashes = source_hashes()
    by_id = {case['id']: pending_case(case, args) for case in selected}
    if args.resume:
        try:
            previous = json.loads(Path(args.output).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            parser.error(f'Không đọc được checkpoint --output: {type(exc).__name__}')
        if previous.get('config') != config:
            parser.error('Cấu hình khác checkpoint; giữ nguyên model/judge/max-steps/dataset hoặc dùng file output mới.')
        if previous.get('source_hashes') != hashes:
            parser.error('Mã nguồn/dataset khác checkpoint hoặc checkpoint cũ chưa có hash; dùng file output mới.')
        old_cases = previous.get('cases', [])
        if (not isinstance(old_cases, list) or not all(isinstance(item, dict) for item in old_cases)
                or len(old_cases) != len(by_id)
                or {item.get('id') for item in old_cases} != set(by_id)):
            parser.error('Danh sách cases khác checkpoint; giữ nguyên lựa chọn --case/--bonus.')
        by_id = {item['id']: item for item in old_cases}
    seeded_ids = set()
    for seed_path in args.seed:
        try:
            imported = load_seed(seed_path, config, hashes, selected)
        except (OSError, ValueError) as exc:
            parser.error(f'Không nạp được --seed: {exc}')
        if seeded_ids.intersection(imported):
            parser.error('Các file --seed có case trùng nhau; giữ một nguồn duy nhất cho mỗi case.')
        seeded_ids.update(imported)
        by_id.update(imported)

    def checkpoint():
        results = [by_id[case['id']] for case in selected]
        summary = summarize(results)
        if args.bonus:
            summary['bonus_points_0_15'] = bonus_points(summary['score_0_100'], not args.case and len(selected) == len(cases))
        report = {'summary': summary, 'config': config, 'source_hashes': hashes, 'cases': results}
        save_report(args.output, report)
        return report

    def run_and_print(case):
        print(f"Đang chạy {case['id']}", flush=True)
        previous = by_id[case['id']]
        if previous.get('result', {}).get('status') == 'completed':
            print(f"{case['id']}: giữ kết quả agent, chấm lại bằng judge.", flush=True)
            item = grade_existing_case(case, args, previous)
        else:
            item = run_case(case, args)
        print(f"{case['id']}: {item['grade'].get('score')} ({item['grade']['status']})", flush=True)
        return item

    pending = [case for case in selected if by_id[case['id']].get('grade', {}).get('score') is None]
    if args.resume or args.seed:
        print(f"Giữ {len(selected) - len(pending)} case đã chấm; còn {len(pending)} case.", flush=True)
    if args.max_cases is not None:
        pending = pending[:args.max_cases]
    checkpoint()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for start in range(0, len(pending), args.workers):
                batch = pending[start:start + args.workers]
                limited = False
                for item in pool.map(run_and_print, batch):
                    by_id[item['id']] = item
                    checkpoint()
                    limited = limited or rate_limited(item)
                if limited:
                    print('Gặp HTTP 429: đã lưu checkpoint và dừng các case tiếp theo. Chờ rồi chạy lại với --resume.', flush=True)
                    break
    except KeyboardInterrupt:
        print('Đã dừng; các case hoàn tất đã được lưu. Chạy lại với --resume để tiếp tục.', flush=True)
    report = checkpoint()
    summary = report['summary']
    if args.bonus:
        print(f"Điểm bonus tham khảo: {summary['bonus_points_0_15']}/15 (chỉ tính khi chấm đủ toàn bộ case).")
    print(f"Điểm: {summary['score_0_100']}/100; đã chấm {summary['scored_cases']}/{summary['total_cases']} case. File: {args.output}")
    if summary['score_0_100'] is None:
        print('Chưa có điểm tổng do có case chưa được chấm; xem reason trong file.', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
