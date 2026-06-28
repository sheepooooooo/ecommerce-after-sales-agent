"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PolicyCitation(BaseModel):
    """
    政策引用信息。
    """

    chunk_id: str = Field(description="被引用的政策 chunk 编号。")
    source_file: str = Field(description="被引用 chunk 所属政策文件。")
    section_title: str = Field(description="被引用 chunk 所属政策小节标题。")


class PolicyGenerationResult(BaseModel):
    """
    模型生成结果。
    """

    answer: str = Field(description="面向用户的中文回答。")
    cited_chunk_ids: list[str] = Field(description="模型声明引用的 chunk_id 列表。")
    needs_human_review: bool = Field(description="是否需要人工进一步处理。")
    missing_information: list[str] = Field(description="回答还需要用户补充的信息。")


class PolicyQAResponse(BaseModel):
    """
    政策问答 Tool 的统一返回结构。
    """

    success: bool = Field(description="程序流程是否成功完成。")
    query: str = Field(description="用户原始问题。")
    answer_status: Literal[
        "answered",
        "no_relevant_policy",
        "manual_review",
        "generation_error",
        "degraded",
    ] = Field(description="回答状态。")
    answer: str = Field(description="最终返回给用户的中文回答。")
    retrieval_mode: str = Field(description="使用的检索模式。")
    retrieved_chunks: list[dict[str, Any]] = Field(description="本次检索到的政策证据片段。")
    citations: list[PolicyCitation] = Field(description="最终合法引用列表。")
    has_relevant_policy: bool = Field(description="检索层是否认为存在相关政策。")
    generation: PolicyGenerationResult | None = Field(description="模型生成的结构化结果。")
    grounding_verification: dict[str, Any] = Field(description="引用校验结果。")
    message: str = Field(description="面向调用方的状态说明。")
    error: str | None = Field(description="错误信息；无错误时为 None。")
    debug: dict[str, Any] = Field(description="调试信息，不包含任何 API Key。")
