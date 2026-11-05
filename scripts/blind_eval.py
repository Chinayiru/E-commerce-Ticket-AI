"""独立保管的 12 条盲测：freeze → seal → run；不是身份认证或防篡改沙箱。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import sys
from collections import Counter
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import TZ_SHANGHAI, load_config
from app.schemas import TicketIn

INTENTS = {"refund", "address_change", "shipping_urge", "other"}
TOOLS = {"query_order", "check_logistics", "refund_preview"}
INTERNAL = {"create_ticket_draft"}
CONFIG_KEYS = {"model", "base_url", "prompt_version", "demo_now", "max_steps", "token_budget",
               "wall_clock_s", "window_turns", "max_output_tokens", "refund_auto_limit_cents",
               "refund_window_days", "price_in_usd_per_mtok", "price_out_usd_per_mtok", "usd_cny_fx"}


def now():
    return datetime.now(TZ_SHANGHAI).isoformat(timespec="seconds")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def exclusive(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def external(path: Path):
    if path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("盲测工作区和数据须在仓库外，由独立保管方控制")


def runtime():
    packages = {}
    for name in ("httpx", "fastapi", "uvicorn", "pytest"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "packages": packages}


def sources():
    files = [p for folder in ("app", "scripts", "tests") for p in (ROOT / folder).rglob("*.py")]
    files += [ROOT / "docs" / name for name in ("DESIGN.md", "IMPLEMENTATION.md", "BLIND_AUTHOR_CONTRACT.md")]
    return {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(files)}


def freeze(work: Path, settings: Path, implementer: str):
    external(work)
    if not implementer.strip():
        raise ValueError("实现者标识不得为空")
    if work.exists():
        raise ValueError("freeze 须使用不存在的新目录，不能覆盖旧候选")
    raw = read(settings)
    if set(raw) != CONFIG_KEYS:
        raise ValueError("配置必须完整且只含 BLIND_EVAL.md 列出的非敏感键")
    cfg = load_config({**raw, "provider": "scripted"}, env={})
    endpoint = urlsplit(cfg.base_url)
    if endpoint.scheme not in ("http", "https") or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("base_url 须为无凭据、无查询参数的 HTTP(S) 地址")
    # 秘钥只在 run 时从环境读取；冻结时不需要凭据。
    normalized = cfg.as_mapping()
    config = {key: normalized[key] for key in sorted(CONFIG_KEYS)}
    from app.tools.mock_data import MOCK_ORDERS
    mock_bytes = (json.dumps(MOCK_ORDERS, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    contract_bytes = (ROOT / "docs/BLIND_AUTHOR_CONTRACT.md").read_bytes()
    candidate = dict(schema=1, frozen_at=now(), implementer=implementer,
                     source_hashes=sources(), runtime=runtime(), config=config,
                     author_packet_hashes={"mock-orders.json": digest(mock_bytes), "author-contract.md": digest(contract_bytes)},
                     conclusion="候选冻结记录；未产生独立评估结果")
    work.mkdir(parents=True)
    exclusive(work / "candidate.json", candidate)
    (work / "mock-orders.json").write_bytes(mock_bytes)
    (work / "author-contract.md").write_bytes(contract_bytes)
    return candidate


def normalized_args(args):
    return {key: (value.strip().upper() if key == "order_id" and isinstance(value, str) else value)
            for key, value in args.items()}


def validate_rows(rows):
    if not all(isinstance(row, dict) and isinstance(row.get("intent"), str) for row in rows):
        raise ValueError("每行须为含字符串 intent 的对象")
    if len(rows) != 12 or Counter(row.get("intent") for row in rows) != Counter({name: 3 for name in INTENTS}):
        raise ValueError("须恰好 12 条、每个意图 3 条")
    ids, texts = set(), set()
    required = {"case_id", "user_id", "text", "order_id", "intent", "expected_tools", "expected_args",
                "expected_needs_human", "expected_reason", "label_reason"}
    for index, row in enumerate(rows, 1):
        if set(row) != required:
            raise ValueError(f"第 {index} 条字段不符合合同")
        TicketIn.from_payload({"ticket_id": row["case_id"], **{key: row[key] for key in ("user_id", "text", "order_id")}})
        text = re.sub(r"\s+", "", row["text"])
        if row["case_id"] in ids or text in texts:
            raise ValueError(f"第 {index} 条编号或文本重复")
        ids.add(row["case_id"])
        texts.add(text)
        if type(row["expected_needs_human"]) is not bool:
            raise ValueError(f"第 {index} 条必须预先确定转人工标签，不接受 null")
        reason = row["expected_reason"]
        if row["expected_needs_human"]:
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"第 {index} 条转人工必须有确定原因")
        elif reason is not None:
            raise ValueError(f"第 {index} 条非转人工的原因必须为 null")
        if not isinstance(row["label_reason"], str) or not row["label_reason"].strip():
            raise ValueError(f"第 {index} 条缺少标注理由")
        names = row["expected_tools"]
        if not isinstance(names, list) or any(name not in TOOLS for name in names) or len(set(names)) != len(names):
            raise ValueError(f"第 {index} 条工具集合非法")
        calls = row["expected_args"]
        if not isinstance(calls, list):
            raise ValueError(f"第 {index} 条参数必须为数组")
        for call in calls:
            if not isinstance(call, dict) or set(call) != {"name", "arguments", "error_code"}:
                raise ValueError(f"第 {index} 条调用标注字段非法")
            if call["name"] not in names or not isinstance(call["arguments"], dict) or set(call["arguments"]) != {"order_id"}:
                raise ValueError(f"第 {index} 条调用参数非法")
            if not isinstance(call["arguments"]["order_id"], str) or not re.fullmatch(r"O\d{4}", call["arguments"]["order_id"].upper()):
                raise ValueError(f"第 {index} 条调用订单号非法")
            if call["error_code"] not in (None, "NOT_SHIPPED", "ORDER_NOT_FOUND", "REFUND_NOT_ALLOWED", "ORDER_STATE_UNSUPPORTED"):
                raise ValueError(f"第 {index} 条预期错误码非法")
        if {call["name"] for call in calls} != set(names):
            raise ValueError(f"第 {index} 条工具与参数标注不一致")


def load_rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_rows(rows)
    return rows


def candidate_check(work):
    candidate = read(work / "candidate.json")
    if candidate["source_hashes"] != sources() or candidate["runtime"] != runtime():
        raise ValueError("候选源码或运行时已变化，不能沿用冻结记录")
    if any(digest((work / name).read_bytes()) != value for name, value in candidate["author_packet_hashes"].items()):
        raise ValueError("出题合同或订单表与冻结作者包不一致")
    return candidate


def seal(work: Path, dataset: Path, attestation: Path):
    external(work)
    external(dataset)
    candidate = candidate_check(work)
    if (work / "attempt.json").exists():
        raise ValueError("该候选的尝试已消耗")
    declaration = read(attestation)
    required = {"author", "label_reviewer", "custodian", "independent_from_implementer",
                "no_candidate_code_or_old_cases_seen", "implementer_has_not_seen_new_cases", "semantic_overlap_reviewed"}
    if set(declaration) != required:
        raise ValueError("独立性声明字段不完整")
    identities = [declaration[key] for key in ("author", "label_reviewer", "custodian")]
    if any(not isinstance(value, str) or not value.strip() for value in identities):
        raise ValueError("须填写出题、复核、保管流程的真实标识")
    if declaration["author"].strip().casefold() == declaration["label_reviewer"].strip().casefold():
        raise ValueError("出题与标注复核须为不同人或不同隔离流程")
    if any(value.strip().casefold() == candidate["implementer"].strip().casefold() for value in identities):
        raise ValueError("出题、标注复核和保管方不得是实现者")
    if any(declaration[key] is not True for key in required - {"author", "label_reviewer", "custodian"}):
        raise ValueError("独立性与语义重复复核声明尚未满足")
    rows = load_rows(dataset)
    # 只做字面筛查；语义独立性仍需保管方按协议核验。
    old = set()
    for name in ("eval_cases.jsonl", "holdout.jsonl", "drafts_50.jsonl"):
        for line in (ROOT / "data" / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                old.add(re.sub(r"\s+", "", json.loads(line).get("text", "")))
    if any(re.sub(r"\s+", "", row["text"]) in old for row in rows):
        raise ValueError("新样本与旧数据存在字面重复")
    sealed = dict(sealed_at=now(), candidate_sha256=digest((work / "candidate.json").read_bytes()),
                  dataset_sha256=digest(dataset.read_bytes()), cases=12, declaration=declaration)
    exclusive(work / "seal.json", sealed)
    return sealed


def score(case, result, calls):
    """独立评分：任何缺失答案/非 ok/缺少明细都不能获得成功分。"""
    answer = result.answer
    complete = result.status.value == "ok" and result.stop_reason.value == "finalized" and answer is not None
    records = [call for call in calls if call.tool_name not in INTERNAL]
    summaries = [call for call in result.tool_calls if call["name"] not in INTERNAL]
    evidence = len(records) == len(summaries) and Counter(call.tool_name for call in records) == Counter(call["name"] for call in summaries)
    def matches(record, want):
        return (record.tool_name == want["name"] and normalized_args(record.arguments) == normalized_args(want["arguments"])
                and record.error_code == want["error_code"] and record.ok is (want["error_code"] is None)
                and not record.approval_required)
    expected = case["expected_args"]
    params = evidence and all(any(matches(record, want) for record in records) for want in expected)
    params = params and all(any(matches(record, want) for want in expected) for record in records)
    return dict(intent_ok=bool(complete and answer.intent.value == case["intent"]),
                tools_ok=bool(complete and evidence and {call.tool_name for call in records} == set(case["expected_tools"])),
                args_ok=bool(complete and params),
                escalation_ok=bool(complete and answer.needs_human is case["expected_needs_human"] and answer.escalate_reason == case["expected_reason"]),
                evidence_missing=not evidence)


def wilson(correct, n):
    z = 1.959963984540054
    p = correct / n
    divisor = 1 + z*z/n
    center = (p + z*z/(2*n)) / divisor
    radius = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / divisor
    return [round(max(0, center-radius), 4), round(min(1, center+radius), 4)]


def run(work: Path, dataset: Path):
    external(work)
    external(dataset)
    candidate = candidate_check(work)
    sealed = read(work / "seal.json")
    if sealed["candidate_sha256"] != digest((work / "candidate.json").read_bytes()) or sealed["dataset_sha256"] != digest(dataset.read_bytes()):
        raise ValueError("候选或数据与封存指纹不一致")
    rows = load_rows(dataset)
    cfg = load_config({**candidate["config"], "provider": "openai", "db_path": str(work / "runs.db"), "log_dir": str(work / "logs")})
    # 原子排他创建；中途故障也视为解封，不提供 resume/retry 参数。
    exclusive(work / "attempt.json", dict(started_at=now(), state="consumed_before_first_call",
                                         candidate_sha256=sealed["candidate_sha256"], dataset_sha256=sealed["dataset_sha256"]))
    from app.core.loop import ExecutionLoop
    from app.llm.openai_compat import OpenAICompatProvider
    from app.store.db import Database
    records = []
    try:
        store = Database(cfg.db_path)
        model = OpenAICompatProvider(cfg)
        for case in rows:
            # 只把工单输入传给被测系统，不传标签、参考答案或标注理由。
            payload = {"ticket_id": case["case_id"], **{key: case[key] for key in ("user_id", "text", "order_id")}}
            result = ExecutionLoop(cfg, store, model).run(payload, dataset_hash=sealed["dataset_sha256"])
            grades = score(case, result, store.list_tool_calls(result.run_id) if result.run_id else [])
            row = dict(case_id=case["case_id"], run_id=result.run_id, **grades,
                       result=result.to_dict(), expected_needs_human=case["expected_needs_human"])
            with (work / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            records.append(row)
        metrics = {}
        for key in ("intent_ok", "tools_ok", "args_ok", "escalation_ok"):
            count = sum(row[key] for row in records)
            metrics[key] = dict(correct=count, total=12, accuracy=round(count / 12, 4), wilson_95=wilson(count, 12))
        confusion = Counter()
        missing = 0
        for row in records:
            answer = row["result"]["answer"]
            if answer is None:
                missing += 1
            else:
                gold, pred = row["expected_needs_human"], answer["needs_human"]
                confusion["TP" if gold and pred else "FN" if gold else "FP" if pred else "TN"] += 1
        if candidate["source_hashes"] != sources() or candidate["runtime"] != runtime():
            raise ValueError("运行期间候选或运行时变化，本次结果无效且额度已消耗")
        report = dict(completed_at=now(), candidate_sha256=sealed["candidate_sha256"], dataset_sha256=sealed["dataset_sha256"],
                      metrics=metrics, escalation_confusion={key: confusion[key] for key in ("TP", "FN", "FP", "TN")},
                      missing_answers=missing, degraded=sum(row["result"]["status"] != "ok" for row in records),
                      cases=12, human_adoption_rate=None,
                      scope="仅适用于这 12 条独立合成样本；独立性依据外部声明，不能代表线上总体或人工采纳率。")
        exclusive(work / "report.json", report)
        return report
    except Exception as exc:
        exclusive(work / "failure.json", dict(at=now(), completed_cases=len(records), error_type=type(exc).__name__,
                                               message="运行中断，尝试已消耗；检查保管方日志，不得重跑后挑选结果"))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--work", required=True, type=Path)
    freeze_parser.add_argument("--config", required=True, type=Path)
    freeze_parser.add_argument("--implementer", required=True)
    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument("--work", required=True, type=Path)
    seal_parser.add_argument("--dataset", required=True, type=Path)
    seal_parser.add_argument("--attestation", required=True, type=Path)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--work", required=True, type=Path)
    run_parser.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            freeze(args.work, args.config, args.implementer)
        elif args.command == "seal":
            seal(args.work, args.dataset, args.attestation)
        else:
            run(args.work, args.dataset)
        print(f"{args.command}: 完成；产物由保管方持有：{args.work}")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # 不在控制台打印可能含题干/凭据的底层异常文本。
        print(f"{args.command}: 未完成（{type(exc).__name__}）；检查协议、冻结状态和输入格式", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
