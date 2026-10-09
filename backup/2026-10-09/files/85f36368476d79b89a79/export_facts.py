"""Export local historical evidence; no training, network, or source edits."""
import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = Path(__file__).resolve().parent

    def git(*arguments):
        return subprocess.check_output(
            ['git', *arguments], cwd=repo, encoding='utf-8', errors='strict'
        ).strip()

    history = git('log', '--reverse', '--format=%H%x09%aI%x09%cI%x09%s')
    (out / 'git_history.tsv').write_text(
        'commit\tauthor_date\tcommitter_date\tsubject\n' + history + '\n', encoding='utf-8'
    )
    sources = [
        'config.yaml', 'requirements.txt', 'run_all.py', 'run_ablation.py',
        'tests/test_pipeline.py', 'thesis_app/pipeline.py',
        'thesis_app/dcc_walk.py', 'thesis_app/signal_layer.py',
        'outputs/results/dataset_summary.json', 'outputs/results/metrics.csv',
        'outputs/results/test_results.txt', 'outputs/results/test_results.xml',
    ]
    facts = {
        'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'commit': git('rev-parse', 'HEAD'),
        'commit_count': int(git('rev-list', '--count', 'HEAD')),
        'tests_rerun_by_this_script': False,
        'sources': {}, 'datasets': {},
    }
    for name in sources:
        path = repo / name
        if path.is_file():
            data = path.read_bytes()
            facts['sources'][name] = {
                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()
            }
        else:
            facts['sources'][name] = {'missing': True}
    for name in ['data/raw/prices.csv', 'data/processed/returns.csv']:
        path = repo / name
        if not path.is_file():
            facts['datasets'][name] = {'missing': True}
            continue
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream)
            header = next(reader)
            rows = list(reader)
        facts['datasets'][name] = {
            'rows': len(rows), 'columns': header,
            'first_index': rows[0][0] if rows else None,
            'last_index': rows[-1][0] if rows else None,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    summary = repo / 'outputs/results/dataset_summary.json'
    if summary.is_file():
        facts['stored_dataset_summary'] = json.loads(summary.read_text(encoding='utf-8'))
    (out / 'project_facts.json').write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(f"Exported {facts['commit_count']} commits and {len(sources)} source records.")


if __name__ == '__main__':
    main()
