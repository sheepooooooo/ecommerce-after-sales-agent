"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

# ============================================================
# 【核心文件分区】
# 1. 路径与依赖：导入本文件需要的模块。
# 2. 数据结构与辅助函数：定义本模块内部复用的工具。
# 3. 核心流程：实现本文件最重要的业务或工程能力。
# 4. 边界与阅读重点：说明副作用、异常和学习入口。
# ============================================================


import json
import re
import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.config import DEFAULT_POLICY_TOP_K
from app.llm.deepseek_client import generate_policy_answer
from app.schemas.policy_qa_schema import (
    PolicyCitation,
    PolicyGenerationResult,
    PolicyQAResponse,
)
from app.services.citation_grounding_verifier import verify_policy_citations
from app.services.error_taxonomy import ErrorCategory, classify_exception, is_retryable_category
from app.services.retry_policy import RetryExhaustedError, execute_with_retry
from app.services.trace_store import sanitize_value
from app.tools.policy_retrieval_tool import retrieve_policy


SYSTEM_PROMPT = """
你是智选商城模拟售后政策问答助手。
你只能依据用户本次问题和给定的政策证据回答。
不得编造未出现在证据中的规则、期限、金额、操作能力或平台承诺。
如果证据不足、问题超出政策范围、需要订单号或需要订单事实判断，必须设置 needs_human_review=true，或在 missing_information 中说明需要补充什么。
通用政策解释问题与订单级执行判断必须区分：
- 用户询问保修多久、是否支持电子发票、一般多久发货、优惠券规则是什么等通用规则，且证据直接写明规则时，必须直接回答政策规则，并设置 needs_human_review=false、missing_information=[]。
- 真实执行服务时可能需要订单号、购买凭证、图片或检测报告，不等于当前政策解释必须人工处理。可以在回答中补充“实际申请时可能需要补充凭证”，但不得因此设置 needs_human_review=true。
- 只有用户要求判断某一个具体订单、证据明确要求人工确认、涉及支付争议/隐私/安全/投诉等高风险情况、政策证据不足或问题超出当前模拟政策可自动解释范围时，才设置 needs_human_review=true。
例如，“耳机保修多久”这类通用规则问题，若证据直接写明保修期限，应直接回答政策期限；可以补充“实际申请时可能需要订单或购买凭证”，但不得因此设置 needs_human_review=true。
回答时必须优先引用直接覆盖用户核心动作和业务阶段的政策 chunk。用户问取消、拒收、已发货后的处理方式时，应优先引用直接描述取消、拒收、发货阶段的政策；不能只因为某个退款政策也相关，就忽略更直接的业务阶段政策。
不得声称已经执行退款、取消订单、创建工单、修改订单等真实动作。
回答应简洁、友好、面向电商用户。
回答必须引用至少一个证据 chunk。
你只能输出 JSON，不输出 Markdown、解释、代码块或额外文字。
JSON 格式严格为：
{
  "answer": "面向用户的中文回答",
  "cited_chunk_ids": ["chunk_id_1"],
  "needs_human_review": false,
  "missing_information": []
}
""".strip()


# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def is_order_fact_question(query: str) -> bool:
    """
    判断用户问题是否涉及具体订单事实。

    参数：
        query：用户问题。

    返回：
        bool：如果包含具体订单号且涉及退款/物流/订单状态，则返回 True。

    用途：
        政策 QA 只回答政策咨询，不替代订单查询和退款规则引擎。
    """
    if not isinstance(query, str):
        return False
    has_order_id = re.search(r"\bORD\d{5,}\b", query.upper()) is not None
    has_order_action = any(
        keyword in query
        for keyword in ["退款", "退货", "取消", "发货", "物流", "签收", "订单", "能不能"]
    )
    return has_order_id and has_order_action


def build_policy_evidence_pack(retrieved_chunk_list: list[dict[str, Any]]) -> str:
    """
    将本次检索到的政策 chunk 组织成证据包。

    参数：
        retrieved_chunk_list：本次 TopK 检索结果。

    返回：
        str：给模型阅读的证据包文本。

    用途：
        模型只能看本次检索到的证据，而不是完整知识库，方便约束回答来源并做引用校验。
    """
    evidence_block_list: list[str] = []
    for retrieved_chunk in retrieved_chunk_list:
        evidence_block_list.append(
            "\n".join(
                [
                    f"[POLICY_CHUNK_ID: {retrieved_chunk['chunk_id']}]",
                    f"来源文件：{retrieved_chunk['source_file']}",
                    f"小节：{retrieved_chunk['section_title']}",
                    "内容：",
                    str(retrieved_chunk["content"]),
                ]
            )
        )
    return "\n\n".join(evidence_block_list)


def build_policy_qa_messages(query: str, evidence_pack: str) -> list[dict[str, str]]:
    """
    构造政策问答模型消息。

    参数：
        query：用户问题。
        evidence_pack：本次检索证据包。

    返回：
        list[dict[str, str]]：OpenAI Chat Completions messages。

    用途：
        将系统约束、证据和用户问题清楚分开，避免模型看到无关上下文。
    """
    user_prompt = "\n".join(
        [
            "请只根据以下政策证据回答用户问题。",
            "",
            "【政策证据】",
            evidence_pack,
            "",
            "【用户问题】",
            query,
        ]
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_repair_messages(raw_output: str) -> list[dict[str, str]]:
    """
    构造格式修复重试消息。

    参数：
        raw_output：第一次模型返回的原始内容。

    返回：
        list[dict[str, str]]：只要求修复 JSON 格式的消息。

    用途：
        第二次重试只修复格式，不加入新的业务信息，避免无限扩展上下文。
    """
    return [
        {"role": "system", "content": "你只负责把输入改写为严格 JSON object。不要添加新业务信息。"},
        {
            "role": "user",
            "content": (
                "请将以下内容改写成严格 JSON："
                '{"answer": "...", "cited_chunk_ids": [], '
                '"needs_human_review": false, "missing_information": []}\n'
                f"原始内容：{raw_output}"
            ),
        },
    ]


def normalize_llm_output(generator_output: Any) -> tuple[dict[str, Any], float, str]:
    """
    规范化 LLM generator 的返回。

    参数：
        generator_output：真实 DeepSeek client 或测试 stub 的返回。

    返回：
        tuple[dict[str, Any], float, str]：parsed、latency_ms、raw_text。

    用途：
        测试可注入简单 stub，真实运行也能处理 deepseek_client 的结构。
    """
    if isinstance(generator_output, dict) and "parsed" in generator_output:
        return (
            generator_output["parsed"],
            float(generator_output.get("latency_ms", 0.0)),
            str(generator_output.get("raw_text", "")),
        )
    if isinstance(generator_output, dict):
        return generator_output, 0.0, json.dumps(generator_output, ensure_ascii=False)
    if isinstance(generator_output, str):
        return json.loads(generator_output), 0.0, generator_output
    raise ValueError("LLM generator 返回类型不支持。")


def call_generator_with_repair(
    messages: list[dict[str, str]],
    llm_generator: Callable[[list[dict[str, str]]], Any],
    sleep_func: Callable[[float], None] | None = None,
    retry_config: dict[str, Any] | None = None,
) -> tuple[PolicyGenerationResult | None, dict[str, Any], str | None]:
    """
    调用模型，并在格式错误时最多进行一次修复重试。

    参数：
        messages：首次生成 messages。
        llm_generator：可注入的模型生成函数。

    返回：
        tuple：生成结果、debug 信息、错误信息。

    用途：
        控制模型生成失败处理，避免无限重试。
    """
    debug_info = {
        "generation_attempt_count": 0,
        "used_repair": False,
        "generation_latency_ms": 0.0,
        "retry_count": 0,
        "retry_trace_events": [],
        "error_category": None,
    }
    raw_output_for_repair = ""

    for attempt_index in range(2):
        debug_info["generation_attempt_count"] += 1
        try:
            current_messages = messages if attempt_index == 0 else build_repair_messages(raw_output_for_repair)
            if attempt_index == 1:
                debug_info["used_repair"] = True
            generator_output, retry_debug = execute_with_retry(
                "policy_qa_tool.ask_policy_question",
                lambda: llm_generator(current_messages),
                sleep_func=sleep_func,
                retry_config=retry_config,
            )
            debug_info["retry_count"] += retry_debug["retry_count"]
            debug_info["retry_trace_events"].extend(retry_debug["trace_events"])
            parsed_dict, latency_ms, raw_text = normalize_llm_output(generator_output)
            raw_output_for_repair = raw_text
            debug_info["generation_latency_ms"] += latency_ms
            return PolicyGenerationResult.model_validate(parsed_dict), debug_info, None
        except (json.JSONDecodeError, ValueError, ValidationError) as error:
            debug_info["error_category"] = ErrorCategory.NON_RETRYABLE_SCHEMA_ERROR.value
            raw_output_for_repair = raw_output_for_repair or str(error)
            if attempt_index == 1:
                return None, debug_info, f"模型输出无法解析为指定 JSON 结构：{error}"
        except RetryExhaustedError as error:
            debug_info["retry_count"] += error.retry_count
            debug_info["retry_trace_events"].extend(error.trace_events)
            debug_info["error_category"] = error.error_category
            return None, debug_info, str(error)
        except Exception as error:
            debug_info["error_category"] = classify_exception(error)
            if not is_retryable_category(debug_info["error_category"]):
                return None, debug_info, f"模型生成失败：{error}"
            if attempt_index == 1:
                return None, debug_info, f"模型生成失败：{error}"
            raw_output_for_repair = str(error)

    return None, debug_info, "模型生成失败。"


def build_degraded_citations(retrieved_chunk_list: list[dict[str, Any]]) -> list[PolicyCitation]:
    citations: list[PolicyCitation] = []
    for chunk in retrieved_chunk_list[:3]:
        citations.append(
            PolicyCitation(
                chunk_id=chunk["chunk_id"],
                source_file=chunk["source_file"],
                section_title=chunk["section_title"],
            )
        )
    return citations


def build_evidence_summary(retrieved_chunk_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for chunk in retrieved_chunk_list[:3]:
        summary.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "source_file": chunk.get("source_file"),
                "section_title": chunk.get("section_title"),
                "content_summary": sanitize_value(str(chunk.get("content", ""))[:180]),
            }
        )
    return summary


def build_citations(
    valid_citation_ids: list[str],
    retrieved_chunk_list: list[dict[str, Any]],
) -> list[PolicyCitation]:
    """
    根据合法 chunk_id 构造引用列表。

    参数：
        valid_citation_ids：校验通过的引用 id。
        retrieved_chunk_list：本次检索证据。

    返回：
        list[PolicyCitation]：最终引用列表。

    用途：
        将引用 id 补充为来源文件和小节标题，方便前端或报告展示。
    """
    chunk_by_id = {
        retrieved_chunk["chunk_id"]: retrieved_chunk
        for retrieved_chunk in retrieved_chunk_list
    }
    citation_list: list[PolicyCitation] = []
    for chunk_id in valid_citation_ids:
        retrieved_chunk = chunk_by_id[chunk_id]
        citation_list.append(
            PolicyCitation(
                chunk_id=chunk_id,
                source_file=retrieved_chunk["source_file"],
                section_title=retrieved_chunk["section_title"],
            )
        )
    return citation_list


def answer_policy_question(
    query: str,
    retrieval_mode: str = "bm25",
    top_k: int = DEFAULT_POLICY_TOP_K,
    llm_generator: Callable[[list[dict[str, str]]], Any] | None = None,
    sleep_func: Callable[[float], None] | None = None,
    retry_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    回答政策咨询问题。

    参数：
        query：用户问题。
        retrieval_mode：政策检索模式，支持 bm25、dense、hybrid。
        top_k：检索证据数量。
        llm_generator：可选模型生成函数，测试时可注入 stub。

    返回：
        dict[str, Any]：PolicyQAResponse 的 JSON 可序列化字典。

    用途：
        编排“检索 -> 证据组织 -> LLM 生成 -> 引用校验”的完整流程。
    """
    service_start_time = time.perf_counter()
    actual_generator = llm_generator or generate_policy_answer

    if not isinstance(query, str) or not query.strip():
        return PolicyQAResponse(
            success=True,
            query=query,
            answer_status="no_relevant_policy",
            answer="问题为空，无法检索政策；请补充具体售后问题。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=[],
            citations=[],
            has_relevant_policy=False,
            generation=None,
            grounding_verification={"passed": False, "reason": "问题为空，未进入生成。"},
            message="问题为空。",
            error=None,
            debug={"llm_called": False, "total_latency_ms": 0.0},
        ).model_dump()

    if not isinstance(top_k, int) or top_k <= 0:
        return PolicyQAResponse(
            success=False,
            query=query,
            answer_status="generation_error",
            answer="top_k 参数不合法，请传入正整数。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=[],
            citations=[],
            has_relevant_policy=False,
            generation=None,
            grounding_verification={"passed": False, "reason": "参数错误。"},
            message="参数错误。",
            error="top_k 必须是正整数。",
            debug={
                "llm_called": False,
                "total_latency_ms": 0.0,
                "error_category": ErrorCategory.INVALID_REQUEST.value,
                "retry_count": 0,
            },
        ).model_dump()

    if is_order_fact_question(query):
        return PolicyQAResponse(
            success=True,
            query=query,
            answer_status="manual_review",
            answer="这个问题涉及具体订单事实，需要先查询订单状态并调用退款资格规则 Tool，不能只靠政策问答直接确认。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=[],
            citations=[],
            has_relevant_policy=False,
            generation=None,
            grounding_verification={"passed": False, "reason": "具体订单事实问题未进入政策问答生成。"},
            message="该问题应由后续 Agent 路由到订单查询和退款规则 Tool。",
            error=None,
            debug={"llm_called": False, "total_latency_ms": 0.0},
        ).model_dump()

    retrieval_start_time = time.perf_counter()
    retrieval_result = retrieve_policy(
        query=query,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
    )
    retrieval_latency_ms = (time.perf_counter() - retrieval_start_time) * 1000

    if not retrieval_result["success"]:
        return PolicyQAResponse(
            success=False,
            query=query,
            answer_status="generation_error",
            answer="政策检索失败，暂时无法生成可靠回答。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=[],
            citations=[],
            has_relevant_policy=False,
            generation=None,
            grounding_verification={"passed": False, "reason": "检索失败。"},
            message=retrieval_result["message"],
            error=retrieval_result["error"],
            debug={"llm_called": False, "retrieval_latency_ms": round(retrieval_latency_ms, 4)},
        ).model_dump()

    retrieved_chunks = retrieval_result["retrieved_chunks"]
    if not retrieval_result["has_relevant_policy"]:
        return PolicyQAResponse(
            success=True,
            query=query,
            answer_status="no_relevant_policy",
            answer="暂未检索到与该问题相关的智选商城模拟政策。你可以补充订单、商品或售后场景信息；涉及复杂问题时建议转人工处理。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=[],
            citations=[],
            has_relevant_policy=False,
            generation=None,
            grounding_verification={"passed": False, "reason": "无相关政策，未调用模型。"},
            message="无相关政策。",
            error=None,
            debug={
                "llm_called": False,
                "retrieval_latency_ms": round(retrieval_latency_ms, 4),
                "total_latency_ms": round((time.perf_counter() - service_start_time) * 1000, 4),
            },
        ).model_dump()

    evidence_pack = build_policy_evidence_pack(retrieved_chunks)
    messages = build_policy_qa_messages(query, evidence_pack)
    generation_result, generation_debug, generation_error = call_generator_with_repair(
        messages=messages,
        llm_generator=actual_generator,
        sleep_func=sleep_func,
        retry_config=retry_config,
    )

    if generation_result is None:
        error_category = generation_debug.get("error_category") or ErrorCategory.INTERNAL_ERROR.value
        retry_trace_events = generation_debug.get("retry_trace_events", [])
        fallback_trace_event = {
            "step": "policy_qa_tool.ask_policy_question",
            "action_type": "fallback",
            "status": "degraded",
            "latency_ms": 0,
            "retry_count": generation_debug.get("retry_count", 0),
            "error_category": error_category,
            "fallback_action": "return_retrieved_policy_evidence",
            "degraded": True,
        }
        citation_list = build_degraded_citations(retrieved_chunks)
        return PolicyQAResponse(
            success=True,
            query=query,
            answer_status="degraded",
            answer="当前政策回答服务暂时不可用，以下仅返回已检索到的模拟政策依据摘要；请稍后重试或转人工处理。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=retrieved_chunks,
            citations=citation_list,
            has_relevant_policy=True,
            generation=None,
            grounding_verification={"passed": False, "reason": "生成失败，已降级为证据摘要。"},
            message="模型生成失败，已安全降级。",
            error=generation_error,
            debug={
                **generation_debug,
                "llm_called": True,
                "degraded": True,
                "fallback_action": "return_retrieved_policy_evidence",
                "error_category": error_category,
                "evidence_summary": build_evidence_summary(retrieved_chunks),
                "retry_trace_events": [*retry_trace_events, fallback_trace_event],
                "retrieval_latency_ms": round(retrieval_latency_ms, 4),
                "total_latency_ms": round((time.perf_counter() - service_start_time) * 1000, 4),
            },
        ).model_dump()

    verification_result = verify_policy_citations(generation_result, retrieved_chunks)
    if not verification_result["passed"]:
        return PolicyQAResponse(
            success=False,
            query=query,
            answer_status="generation_error",
            answer="模型回答的引用未通过校验，暂不返回该回答。",
            retrieval_mode=retrieval_mode,
            retrieved_chunks=retrieved_chunks,
            citations=[],
            has_relevant_policy=True,
            generation=generation_result,
            grounding_verification=verification_result,
            message="引用校验失败。",
            error=verification_result["reason"],
            debug={
                **generation_debug,
                "llm_called": True,
                "retrieval_latency_ms": round(retrieval_latency_ms, 4),
                "total_latency_ms": round((time.perf_counter() - service_start_time) * 1000, 4),
            },
        ).model_dump()

    answer_status = "manual_review" if generation_result.needs_human_review else "answered"
    citation_list = build_citations(verification_result["valid_citation_ids"], retrieved_chunks)

    return PolicyQAResponse(
        success=True,
        query=query,
        answer_status=answer_status,
        answer=generation_result.answer,
        retrieval_mode=retrieval_mode,
        retrieved_chunks=retrieved_chunks,
        citations=citation_list,
        has_relevant_policy=True,
        generation=generation_result,
        grounding_verification=verification_result,
        message="政策问答生成完成，并通过引用校验。",
        error=None,
        debug={
            **generation_debug,
            "llm_called": True,
            "retrieval_latency_ms": round(retrieval_latency_ms, 4),
            "total_latency_ms": round((time.perf_counter() - service_start_time) * 1000, 4),
        },
    ).model_dump()

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
