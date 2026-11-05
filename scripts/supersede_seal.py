"""在保留旧封存记录的前提下，为同一批 12 条新题生成“继承封存”（候选 + 封存各一份，显式关联旧版本）。

用途：旧封存按 wall_clock_s=30 冻结，现要改成 60s / token_budget=12000 后只运行一次。
做法不是修改旧记录，而是新建一个候选目录，把旧封存的哈希写进 `supersedes` 字段，
再由保管方封存、运行。旧记录原样保留，作为“此数据首次按 30s 冻结”的历史证据。

强制检查（任一不满足即退出码 2，不产生任何记录）：
- 旧封存必须存在且**未被消耗**（存在 attempt.json 说明这批数据已经用过，不能再封一次）；
- 新数据集的 sha256 必须等于旧封存的 dataset_sha256（同一批题，不换数据）；
- 新配置必须与旧候选只在允许改动的键上不同（默认允许：wall_clock_s、token_budget）。

用法（保管方在持有数据与封存目录的机器上执行）：

    python scripts/supersede_seal.py \
        --previous-work <旧封存目录> --work <新封存目录> \
        --settings docs/blind-config-2026-11-06-supersede.json \
        --dataset <12 条 jsonl> --attestation <独立性声明 json> \
        --implementer implementer --reason "wall_clock_s 30→60、token_budget 6000→12000，代理抖动防护"
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLIND = ROOT / "scripts" / "blind_eval.py"
ALLOWED_CHANGES = {"wall_clock_s", "token_budget"}


def _load_blind():
    spec = importlib.util.spec_from_file_location("blind_eval", BLIND)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def supersede(previous_work: pathlib.Path, work: pathlib.Path, settings: pathlib.Path,
              dataset: pathlib.Path, attestation: pathlib.Path, implementer: str, reason: str) -> dict[str, Any]:
    blind = _load_blind()

    previous_seal_path = previous_work / "seal.json"
    previous_candidate_path = previous_work / "candidate.json"
    if not previous_seal_path.exists() or not previous_candidate_path.exists():
        raise ValueError("旧封存目录缺少 seal.json 或 candidate.json")
    if (previous_work / "attempt.json").exists():
        raise ValueError("旧封存的尝试已消耗；这批数据不能再次封存或运行")

    previous_seal = read_json(previous_seal_path)
    previous_candidate = read_json(previous_candidate_path)

    dataset_hash = digest(dataset)
    if dataset_hash != previous_seal["dataset_sha256"]:
        raise ValueError("新数据集与旧封存不是同一批样本（sha256 不一致）；继承封存不允许换数据")

    settings_raw = read_json(settings)
    if set(settings_raw) != blind.CONFIG_KEYS:
        raise ValueError("配置必须完整且只含 BLIND_EVAL.md 列出的非敏感键")
    from app.config import load_config

    new_config = {key: load_config({**settings_raw, "provider": "scripted"}, env={}).as_mapping()[key]
                  for key in sorted(blind.CONFIG_KEYS)}
    old_config = previous_candidate.get("config", {})
    changed = {key: [old_config.get(key), new_config.get(key)]
               for key in sorted(blind.CONFIG_KEYS) if old_config.get(key) != new_config.get(key)}
    unexpected = sorted(set(changed) - ALLOWED_CHANGES)
    if unexpected:
        raise ValueError(f"继承封存只允许改动 {sorted(ALLOWED_CHANGES)}，实际还改了：{unexpected}")

    candidate = blind.freeze(work, settings, implementer)
    patched = dict(candidate)
    patched["supersedes"] = {
        "reason": reason.strip(),
        "previous_seal_sha256": digest(previous_seal_path),
        "previous_candidate_sha256": previous_seal["candidate_sha256"],
        "previous_sealed_at": previous_seal.get("sealed_at"),
        "previous_dataset_sha256": previous_seal["dataset_sha256"],
        "same_dataset": True,
        "previous_attempt_consumed": False,
        "changed_config": changed,
        "note": "旧封存原样保留；本次仅在同一批 12 条样本上更新运行条件，仍未运行",
    }
    (work / "candidate.json").write_text(json.dumps(patched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sealed = blind.seal(work, dataset, attestation)
    return {
        "work": str(work),
        "candidate_sha256": sealed["candidate_sha256"],
        "dataset_sha256": sealed["dataset_sha256"],
        "seal_sha256": digest(work / "seal.json"),
        "supersedes_seal_sha256": patched["supersedes"]["previous_seal_sha256"],
        "changed_config": changed,
        "next": "由保管方执行一次 `python scripts/blind_eval.py run --work <目录> --dataset <文件>`；不得重跑",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为同一批新题生成继承封存记录（保留旧记录）")
    parser.add_argument("--previous-work", required=True, type=pathlib.Path)
    parser.add_argument("--work", required=True, type=pathlib.Path)
    parser.add_argument("--settings", required=True, type=pathlib.Path)
    parser.add_argument("--dataset", required=True, type=pathlib.Path)
    parser.add_argument("--attestation", required=True, type=pathlib.Path)
    parser.add_argument("--implementer", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        result = supersede(args.previous_work, args.work, args.settings, args.dataset,
                           args.attestation, args.implementer, args.reason)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # 控制台不回显可能含题干或凭据的底层文本。
        print(f"supersede: 未完成（{type(exc).__name__}）；检查旧封存状态、数据集哈希与配置", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
