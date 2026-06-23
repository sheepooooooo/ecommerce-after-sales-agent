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


from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyChunk:
    """
    表示一段可检索的政策片段。

    字段说明：
        chunk_id：稳定的片段编号，例如 refund_return_policy__section_01。
        source_file：来源政策文件名，便于追溯规则来源。
        document_title：文档一级标题，便于理解片段所属政策。
        section_title：二级标题，便于定位具体规则小节。
        content：该小节的标题和正文内容。
    """

    chunk_id: str
    source_file: str
    document_title: str
    section_title: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        """
        将 PolicyChunk 转换为普通字典。

        参数：
            无。

        返回：
            dict[str, Any]：JSON 可序列化的 chunk 字典。

        用途：
            写入 JSONL 索引文件，便于人工查看和调试。
        """
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "document_title": self.document_title,
            "section_title": self.section_title,
            "content": self.content,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "PolicyChunk":
        """
        从普通字典恢复 PolicyChunk。

        参数：
            data：从 JSONL 读取出来的字典。

        返回：
            PolicyChunk：恢复后的政策片段对象。

        用途：
            在线检索时从本地索引文件加载 chunk。
        """
        return PolicyChunk(
            chunk_id=str(data["chunk_id"]),
            source_file=str(data["source_file"]),
            document_title=str(data["document_title"]),
            section_title=str(data["section_title"]),
            content=str(data["content"]),
        )

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
