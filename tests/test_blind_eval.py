"""仅测试盲测流程控制与评分，不使用真正新盲测样本、不调用外部模型。"""
import copy
import json
from types import SimpleNamespace

import pytest

from app.schemas import FinalAnswer, Intent, ModelDecision, ModelResponse, RunStatus, StopReason
from scripts import blind_eval as blind


def rows():
    return [dict(case_id=f"fixture-{i:02d}", user_id="U001", text=f"流程测试占位工单 {i}，无需查询订单",
                 order_id=None, intent=intent, expected_tools=[], expected_args=[],
                 expected_needs_human=False, expected_reason=None, label_reason="仅测试协议，不是真实业务标注")
            for i, intent in enumerate(sorted(blind.INTENTS) * 3)]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def packet(tmp_path):
    work = tmp_path / "private-candidate"
    settings = tmp_path / "config.json"
    settings.write_bytes((blind.ROOT / "docs/blind-config.example.json").read_bytes())
    blind.freeze(work, settings, "implementer-fixture")
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows()) + "\n", encoding="utf-8")
    declaration = dict(author="author-clean-context", label_reviewer="reviewer-clean-context", custodian="custodian-fixture",
                       independent_from_implementer=True, no_candidate_code_or_old_cases_seen=True,
                       implementer_has_not_seen_new_cases=True, semantic_overlap_reviewed=True)
    attestation = tmp_path / "declaration.json"
    write_json(attestation, declaration)
    return work, dataset, attestation


def answer_result(**changes):
    answer = FinalAnswer(intent=Intent.OTHER, confidence=0.9, slots={}, reply_draft="请补充问题。",
                         needs_human=False, escalate_reason=None, used_tools=[])
    data = dict(status=RunStatus.OK, stop_reason=StopReason.FINALIZED, answer=answer, tool_calls=[])
    data.update(changes)
    return SimpleNamespace(**data)


def test_no_answer_or_failed_run_never_scores():
    case = next(row for row in rows() if row["intent"] == "other")
    for result in (answer_result(answer=None), answer_result(status=RunStatus.REJECTED),
                   answer_result(stop_reason=StopReason.TIMEOUT)):
        score = blind.score(case, result, [])
        assert not any(score[key] for key in ("intent_ok", "tools_ok", "args_ok", "escalation_ok"))


def test_missing_detail_and_additional_wrong_attempt_fail():
    case = next(row for row in rows() if row["intent"] == "other")
    case.update(expected_tools=["query_order"], expected_args=[dict(name="query_order", arguments={"order_id": "O1001"}, error_code=None)])
    result = answer_result(tool_calls=[{"name": "query_order"}])
    assert blind.score(case, result, [])["evidence_missing"]
    assert not blind.score(case, result, [])["args_ok"]
    good = SimpleNamespace(tool_name="query_order", arguments={"order_id": " o1001 "}, error_code=None, ok=True, approval_required=False)
    assert blind.score(case, result, [good])["args_ok"]
    wrong = copy.copy(good)
    wrong.arguments = {"order_id": "O1005"}
    result.tool_calls.append({"name": "query_order"})
    assert not blind.score(case, result, [good, wrong])["args_ok"]


def test_business_error_requires_preregistered_annotation():
    case = next(row for row in rows() if row["intent"] == "other")
    case.update(expected_tools=["check_logistics"], expected_args=[dict(name="check_logistics", arguments={"order_id": "O1001"}, error_code="NOT_SHIPPED")])
    result = answer_result(tool_calls=[{"name": "check_logistics"}])
    record = SimpleNamespace(tool_name="check_logistics", arguments={"order_id": "O1001"}, error_code="NOT_SHIPPED", ok=False, approval_required=False)
    assert blind.score(case, result, [record])["args_ok"]
    record.error_code = "TOOL_ERROR"
    assert not blind.score(case, result, [record])["args_ok"]
    record.error_code = "NOT_SHIPPED"
    record.approval_required = True
    assert not blind.score(case, result, [record])["args_ok"]


def test_correct_boolean_wrong_reason_is_failure():
    case = next(row for row in rows() if row["intent"] == "other")
    case.update(expected_needs_human=True, expected_reason="DELIVERY_DISPUTE")
    result = answer_result()
    result.answer = result.answer.with_escalation("MODEL_FLAGGED")
    assert not blind.score(case, result, [])["escalation_ok"]


@pytest.mark.parametrize("mutation", ["count", "null_label", "tools_mismatch", "duplicate", "unknown_field", "invalid_args"])
def test_invalid_dataset_rejected_before_seal(mutation):
    data = rows()
    if mutation == "count":
        data.pop()
    elif mutation == "null_label":
        data[0]["expected_needs_human"] = None
    elif mutation == "tools_mismatch":
        data[0]["expected_tools"] = ["query_order"]
    elif mutation == "duplicate":
        data[0]["text"] = data[1]["text"]
    elif mutation == "unknown_field":
        data[0]["reply_draft"] = "label leak"
    else:
        data[0]["expected_tools"] = ["query_order"]
        data[0]["expected_args"] = [dict(name="query_order", arguments={"order_id": "O1001", "approved": True}, error_code=None)]
    with pytest.raises(ValueError):
        blind.validate_rows(data)


def test_freeze_seal_and_identity_controls(packet):
    work, dataset, attestation = packet
    assert "api_key" not in blind.read(work / "candidate.json")["config"]
    declaration = blind.read(attestation)
    declaration["label_reviewer"] = declaration["author"]
    write_json(attestation, declaration)
    with pytest.raises(ValueError):
        blind.seal(work, dataset, attestation)
    declaration["label_reviewer"] = "independent-label-reviewer"
    declaration["semantic_overlap_reviewed"] = False
    write_json(attestation, declaration)
    with pytest.raises(ValueError):
        blind.seal(work, dataset, attestation)
    declaration["semantic_overlap_reviewed"] = True
    write_json(attestation, declaration)
    sealed = blind.seal(work, dataset, attestation)
    assert sealed["cases"] == 12
    assert "text" not in sealed


def test_changed_sources_or_data_rejected(packet, monkeypatch):
    work, dataset, attestation = packet
    blind.seal(work, dataset, attestation)
    before = blind.sources()
    monkeypatch.setattr(blind, "sources", lambda: {**before, "fake.py": "changed"})
    with pytest.raises(ValueError):
        blind.run(work, dataset)
    assert not (work / "attempt.json").exists()
    monkeypatch.setattr(blind, "sources", lambda: before)
    dataset.write_text(dataset.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        blind.run(work, dataset)
    assert not (work / "attempt.json").exists()


def test_modified_author_packet_rejected(packet):
    work, dataset, attestation = packet
    with (work / "mock-orders.json").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(ValueError):
        blind.seal(work, dataset, attestation)


def test_full_fake_run_is_blind_and_single_use(packet, monkeypatch):
    work, dataset, attestation = packet
    blind.seal(work, dataset, attestation)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-offline-test-key")
    requests = []
    class FakeProvider:
        def __init__(self, config):
            pass
        def complete(self, request):
            requests.append(request)
            return ModelResponse(ModelDecision(final=answer_result().answer))
    monkeypatch.setattr("app.llm.openai_compat.OpenAICompatProvider", FakeProvider)
    report = blind.run(work, dataset)
    assert len(requests) == 12
    assert report["metrics"]["intent_ok"]["correct"] == 3
    assert report["metrics"]["intent_ok"]["total"] == 12
    assert report["human_adoption_rate"] is None
    assert len((work / "results.jsonl").read_text(encoding="utf-8").splitlines()) == 12
    for request in requests:
        assert "label_reason" not in json.dumps(request.messages)
        assert "expected_tools" not in json.dumps(request.messages)
        assert "仅测试协议，不是真实业务标注" not in json.dumps(request.messages, ensure_ascii=False)
    with pytest.raises(FileExistsError):
        blind.run(work, dataset)
    assert len(requests) == 12


def test_midrun_failure_consumes_attempt(packet, monkeypatch):
    work, dataset, attestation = packet
    blind.seal(work, dataset, attestation)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-offline-test-key")
    class CrashProvider:
        def __init__(self, config):
            pass
        def complete(self, request):
            raise RuntimeError("injected offline failure")
    monkeypatch.setattr("app.llm.openai_compat.OpenAICompatProvider", CrashProvider)
    with pytest.raises(RuntimeError):
        blind.run(work, dataset)
    assert (work / "attempt.json").exists()
    assert blind.read(work / "failure.json")["completed_cases"] == 0
    assert not (work / "report.json").exists()
    with pytest.raises(FileExistsError):
        blind.run(work, dataset)


def test_repository_is_not_a_custodian_directory():
    with pytest.raises(ValueError):
        blind.external(blind.ROOT / "data" / "new_holdout.jsonl")


def test_wilson_interval_does_not_imply_certainty():
    low, high = blind.wilson(12, 12)
    assert 0.75 < low < 0.76
    assert high == 1
