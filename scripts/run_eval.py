"""离线评估入口：`python scripts/run_eval.py [--provider scripted|openai]`。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import load_config  # noqa: E402
from app.eval import runner  # noqa: E402
from app.eval.datasets import load_drafts, load_eval_cases, load_holdout  # noqa: E402

DATASETS = {"eval": load_eval_cases, "holdout": load_holdout, "drafts": load_drafts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=tuple(DATASETS), default="eval")
    parser.add_argument("--provider", choices=("scripted", "openai"), default="scripted")
    parser.add_argument("--no-approve", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    config = load_config()
    dataset = DATASETS[args.dataset]()
    result = runner.run_suite(config, dataset, provider=args.provider, approve=not args.no_approve)
    out_dir = Path(args.out) if args.out else None
    json_path, md_path = runner.write_report(result, config, out_dir=out_dir)

    print(f"report: {json_path}")
    print(f"markdown: {md_path}")
    for key, value in result.metrics.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
