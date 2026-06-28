"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

import re

from app.retrieval.policy_index_manager import build_policy_index
from app.services.policy_qa_service import (
    answer_policy_question,
    build_policy_evidence_pack,
)
from app.services.error_taxonomy import ErrorCategory
from app.tools.policy_retrieval_tool import retrieve_policy


def extract_first_chunk_id_from_messages(messages: list[dict[str, str]]) -> str:
    """
    从模型 messages 的证据包中提取第一个 chunk_id。

    参数：
        messages：传给 LLM 的 messages。

    返回：
        str：第一个 POLICY_CHUNK_ID。

    用途：
        测试 stub 用真实检索到的 chunk_id 生成合法引用。
    """
    joined_text = "\n".join(message["content"] for message in messages)
    match = re.search(r"\[POLICY_CHUNK_ID: ([^\]]+)\]", joined_text)
    assert match is not None
    return match.group(1)


def extract_chunk_id_by_source_from_messages(messages: list[dict[str, str]], source_file: str) -> str:
    """
    从模型 messages 的证据包中提取指定来源文件的 chunk_id。

    参数：
        messages：传给 LLM 的 messages。
        source_file：期望引用的政策文件名。

    返回：
        str：该来源文件对应的第一个 POLICY_CHUNK_ID。

    用途：
        测试“优先引用直接业务阶段证据”的结构化数据流。
    """
    joined_text = "\n".join(message["content"] for message in messages)
    pattern = re.compile(
        r"\[POLICY_CHUNK_ID: ([^\]]+)\]\n来源文件：" + re.escape(source_file),
        re.MULTILINE,
    )
    match = pattern.search(joined_text)
    assert match is not None
    return match.group(1)


# 这个测试验证：有相关政策时，服务能组织证据包。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_build_policy_evidence_pack_contains_chunk_id() -> None:
    """
    验证证据包保留 chunk_id、来源文件和小节标题。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确保模型只能基于本次 TopK 证据回答。
    """
    build_policy_index()
    retrieval_result = retrieve_policy("耳机保修多久？", retrieval_mode="bm25")

    evidence_pack = build_policy_evidence_pack(retrieval_result["retrieved_chunks"])

    assert "[POLICY_CHUNK_ID:" in evidence_pack
    assert "来源文件：" in evidence_pack
    assert "小节：" in evidence_pack


# 这个测试验证：正常 mock JSON 输出能得到 answered 状态。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_answer_policy_question_with_valid_stub_returns_answered() -> None:
    """
    验证合法模型 JSON 输出可以生成 answered 响应。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认服务能完成检索、生成和引用校验全流程。
    """
    build_policy_index()

    def stub_generator(messages: list[dict[str, str]]) -> dict:
        chunk_id = extract_first_chunk_id_from_messages(messages)
        return {
            "answer": "耳机属于数码商品，模拟政策中提供 12 个月保修；具体处理仍需按保修流程核实。",
            "cited_chunk_ids": [chunk_id],
            "needs_human_review": False,
            "missing_information": [],
        }

    result = answer_policy_question(
        "耳机保修多久？",
        retrieval_mode="bm25",
        llm_generator=stub_generator,
    )

    assert result["success"] is True
    assert result["answer_status"] == "answered"
    assert result["grounding_verification"]["passed"] is True
    assert result["citations"]


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_generic_policy_question_should_not_require_manual_review() -> None:
    """
    验证通用政策解释问题不应因为真实执行可能需要凭证而进入 manual_review。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        防止“保修多久”等政策解释被误判成订单级执行判断。
    """
    build_policy_index()

    def stub_generator(messages: list[dict[str, str]]) -> dict:
        chunk_id = extract_first_chunk_id_from_messages(messages)
        return {
            "answer": "数码商品提供 12 个月模拟保修，实际申请时可能需要补充订单或购买凭证。",
            "cited_chunk_ids": [chunk_id],
            "needs_human_review": False,
            "missing_information": [],
        }

    result = answer_policy_question(
        "耳机买了以后一般保修多长时间？",
        retrieval_mode="bm25",
        llm_generator=stub_generator,
    )

    assert result["answer_status"] == "answered"
    assert result["generation"]["needs_human_review"] is False
    assert result["generation"]["missing_information"] == []


# 这个测试验证：无关问题不调用 LLM，直接返回 no_relevant_policy。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_no_relevant_policy_does_not_call_llm() -> None:
    """
    验证天气问题不会调用模型。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认无相关政策是正常业务结果，不是生成错误。
    """
    build_policy_index()
    called = {"value": False}

    def stub_generator(messages: list[dict[str, str]]) -> dict:
        called["value"] = True
        return {}

    result = answer_policy_question(
        "今天上海天气怎么样？",
        retrieval_mode="bm25",
        llm_generator=stub_generator,
    )

    assert result["answer_status"] == "no_relevant_policy"
    assert called["value"] is False


# 这个测试验证：具体订单退款问题不应伪装成已确认退款结论。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_order_refund_question_returns_manual_review() -> None:
    """
    验证 ORD 订单问题进入 manual_review。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认政策 QA 不替代订单查询和退款资格规则 Tool。
    """
    result = answer_policy_question("ORD10004 可以直接退款吗？", llm_generator=lambda messages: {})

    assert result["answer_status"] == "manual_review"
    assert result["debug"]["llm_called"] is False


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_citation_should_prefer_direct_business_stage_evidence() -> None:
    """
    验证已发货取消问题在证据包包含取消政策时，可引用直接业务阶段证据并通过校验。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        覆盖“检索证据 -> 模型引用 -> 引用校验 -> 最终 citations”的结构化数据流。
    """
    build_policy_index()

    def stub_generator(messages: list[dict[str, str]]) -> dict:
        chunk_id = extract_chunk_id_by_source_from_messages(messages, "cancellation_policy.md")
        return {
            "answer": "订单已发货后通常不能直接取消，可按配送情况拒收；如已签收，则按售后路径处理。",
            "cited_chunk_ids": [chunk_id],
            "needs_human_review": False,
            "missing_information": [],
        }

    result = answer_policy_question(
        "商品已经发货，但我临时不想要了怎么办？",
        retrieval_mode="bm25",
        llm_generator=stub_generator,
    )

    assert result["success"] is True
    assert result["grounding_verification"]["passed"] is True
    assert result["answer_status"] == "answered"
    assert "cancellation_policy.md" in [citation["source_file"] for citation in result["citations"]]


# 这个测试验证：非 JSON 输出触发一次格式修复重试。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_non_json_output_triggers_one_repair_retry() -> None:
    """
    验证第一次非 JSON、第二次合法 JSON 时可恢复。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认有限重试机制生效且不会无限重试。
    """
    build_policy_index()
    state = {"count": 0, "chunk_id": ""}

    def stub_generator(messages: list[dict[str, str]]) -> str | dict:
        state["count"] += 1
        if state["count"] == 1:
            state["chunk_id"] = extract_first_chunk_id_from_messages(messages)
            return "这不是 JSON"
        return {
            "answer": "已按政策证据回答。",
            "cited_chunk_ids": [state["chunk_id"]],
            "needs_human_review": False,
            "missing_information": [],
        }

    result = answer_policy_question(
        "退货后优惠券会退回来吗？",
        llm_generator=stub_generator,
    )

    assert result["success"] is True
    assert result["debug"]["generation_attempt_count"] == 2
    assert result["debug"]["used_repair"] is True


# 这个测试验证：第二次仍失败时返回 generation_error。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_second_generation_failure_returns_generation_error() -> None:
    """
    验证两次输出都无法解析时返回 generation_error。

    参数：
        无。

    返回：
        None：pytest 根据断言判断测试是否通过。

    用途：
        确认服务不会无限重试。
    """
    build_policy_index()

    result = answer_policy_question(
        "退货后优惠券会退回来吗？",
        llm_generator=lambda messages: "不是 JSON",
    )

    assert result["success"] is True
    assert result["answer_status"] == "degraded"
    assert result["debug"]["generation_attempt_count"] == 2


class StubLLMError(RuntimeError):
    def __init__(self, message: str, error_category: str) -> None:
        super().__init__(message)
        self.error_category = error_category


def test_retryable_llm_error_then_success() -> None:
    build_policy_index()
    state = {"count": 0, "chunk_id": ""}

    def flaky_generator(messages: list[dict[str, str]]) -> dict:
        state["count"] += 1
        if state["count"] == 1:
            raise StubLLMError("temporary timeout sk-secret", ErrorCategory.LLM_TIMEOUT.value)
        state["chunk_id"] = extract_first_chunk_id_from_messages(messages)
        return {
            "answer": "已根据政策证据回答。",
            "cited_chunk_ids": [state["chunk_id"]],
            "needs_human_review": False,
            "missing_information": [],
        }

    result = answer_policy_question(
        "耳机保修多久？",
        llm_generator=flaky_generator,
        retry_config={"max_retries": 2, "base_delay_seconds": 0, "backoff_multiplier": 1},
    )

    assert result["success"] is True
    assert result["answer_status"] == "answered"
    assert result["debug"]["retry_count"] == 1
    assert any(event["action_type"] == "retry_attempt" for event in result["debug"]["retry_trace_events"])


def test_retry_exhausted_returns_degraded_without_fabricated_answer() -> None:
    build_policy_index()

    def broken_generator(messages: list[dict[str, str]]) -> dict:
        raise StubLLMError("temporary timeout sk-secret", ErrorCategory.LLM_TIMEOUT.value)

    result = answer_policy_question(
        "耳机保修多久？",
        llm_generator=broken_generator,
        retry_config={"max_retries": 2, "base_delay_seconds": 0, "backoff_multiplier": 1},
    )

    assert result["success"] is True
    assert result["answer_status"] == "degraded"
    assert result["debug"]["degraded"] is True
    assert result["debug"]["retry_count"] == 2
    assert result["debug"]["fallback_action"] == "return_retrieved_policy_evidence"
    assert "暂时不可用" in result["answer"]
    assert result["generation"] is None
    assert result["citations"]
    assert "sk-secret" not in str(result["debug"]["retry_trace_events"])
    assert any(event["action_type"] == "retry_exhausted" for event in result["debug"]["retry_trace_events"])
    assert any(event["action_type"] == "fallback" for event in result["debug"]["retry_trace_events"])


def test_non_retryable_configuration_error_does_not_retry() -> None:
    build_policy_index()
    state = {"count": 0}

    def broken_config_generator(messages: list[dict[str, str]]) -> dict:
        state["count"] += 1
        raise StubLLMError("missing api key", ErrorCategory.LLM_CONFIGURATION_ERROR.value)

    result = answer_policy_question(
        "耳机保修多久？",
        llm_generator=broken_config_generator,
        retry_config={"max_retries": 2, "base_delay_seconds": 0, "backoff_multiplier": 1},
    )

    assert state["count"] == 1
    assert result["answer_status"] == "degraded"
    assert result["debug"]["retry_count"] == 0
    assert result["debug"]["error_category"] == ErrorCategory.LLM_CONFIGURATION_ERROR.value
