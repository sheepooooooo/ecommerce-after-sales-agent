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


from typing import Any

from app.schemas.policy_qa_schema import PolicyGenerationResult


def verify_policy_citations(
    generation_result: PolicyGenerationResult,
    retrieved_chunk_list: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    校验模型引用是否来自本次检索证据。

    参数：
        generation_result：模型生成结果。
        retrieved_chunk_list：本次检索得到的 chunk 列表。

    返回：
        dict[str, Any]：引用校验结果。

    用途：
        防止模型引用不存在或不属于本次证据的 chunk_id。
    """
    retrieved_chunk_id_set = {
        str(retrieved_chunk["chunk_id"])
        for retrieved_chunk in retrieved_chunk_list
        if "chunk_id" in retrieved_chunk
    }
    checked_citation_ids = [str(chunk_id) for chunk_id in generation_result.cited_chunk_ids]
    valid_citation_ids: list[str] = []
    invalid_citation_ids: list[str] = []
    warnings: list[str] = []

    if not checked_citation_ids:
        warnings.append("模型未提供任何引用。")

    if len(checked_citation_ids) != len(set(checked_citation_ids)):
        warnings.append("模型引用中存在重复 chunk_id。")

    for chunk_id in checked_citation_ids:
        if chunk_id in retrieved_chunk_id_set and chunk_id not in valid_citation_ids:
            valid_citation_ids.append(chunk_id)
        elif chunk_id not in retrieved_chunk_id_set:
            invalid_citation_ids.append(chunk_id)

    passed = (
        len(checked_citation_ids) > 0
        and not invalid_citation_ids
        and len(checked_citation_ids) == len(set(checked_citation_ids))
    )
    if not generation_result.needs_human_review and not valid_citation_ids:
        passed = False
        warnings.append("needs_human_review=false 时至少需要一个合法引用。")

    if passed:
        reason = "模型引用均来自本次检索到的政策证据。"
    else:
        reason = "引用校验未通过；该校验只确认引用是否属于本次证据，不保证完整事实正确性。"

    return {
        "passed": passed,
        "checked_citation_ids": checked_citation_ids,
        "valid_citation_ids": valid_citation_ids,
        "invalid_citation_ids": invalid_citation_ids,
        "warnings": warnings,
        "reason": reason,
    }

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
