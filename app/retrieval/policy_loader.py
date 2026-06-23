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
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import POLICY_DIRECTORY
from app.retrieval.policy_schema import PolicyChunk


def get_policy_directory() -> Path:
    """
    获取政策文档目录。

    参数：
        无。

    返回：
        Path：data/policies 的绝对路径。

    用途：
        让加载器不依赖终端当前目录，稳定读取同一批政策文档。
    """
    return POLICY_DIRECTORY


def extract_document_title(markdown_text: str, fallback_title: str) -> str:
    """
    从 Markdown 文本中提取第一个一级标题。

    参数：
        markdown_text：政策文档原始 Markdown 文本。
        fallback_title：没有一级标题时使用的备用标题。

    返回：
        str：文档标题。

    用途：
        chunk 需要保存文档标题，方便检索结果解释来源。
    """
    for line_text in markdown_text.splitlines():
        if line_text.startswith("# "):
            return line_text[2:].strip()
    return fallback_title


def load_policy_documents() -> list[dict[str, Any]]:
    """
    加载所有 Markdown 政策文档。

    参数：
        无。

    返回：
        list[dict[str, Any]]：每个元素包含 source_file、document_title、content。

    用途：
        为后续语义切块提供稳定输入。
    """
    policy_directory = get_policy_directory()
    policy_document_list: list[dict[str, Any]] = []

    if not policy_directory.exists():
        raise FileNotFoundError(
            f"政策目录不存在：{policy_directory}。请确认 data/policies 已创建。"
        )

    # 按文件名排序，保证每次构建索引时 chunk 顺序稳定，便于测试和排查。
    for policy_document_path in sorted(policy_directory.glob("*.md")):
        markdown_text = policy_document_path.read_text(encoding="utf-8").strip()
        if not markdown_text:
            print(f"跳过空政策文档：{policy_document_path.name}")
            continue

        policy_document_list.append(
            {
                "source_file": policy_document_path.name,
                "document_title": extract_document_title(
                    markdown_text=markdown_text,
                    fallback_title=policy_document_path.stem,
                ),
                "content": markdown_text,
            }
        )

    return policy_document_list


def chunk_policy_document(policy_document: dict[str, Any]) -> list[PolicyChunk]:
    """
    将单份政策文档按二级标题切分为 chunk。

    参数：
        policy_document：load_policy_documents 返回的单份文档字典。

    返回：
        list[PolicyChunk]：该文档切出的政策片段列表。

    用途：
        按 Markdown 标题切块能保留业务语义，例如“适用范围”“Agent 可执行边界”。
        机械按固定字符数切分可能把一条规则截断，影响检索解释性。
    """
    source_file = str(policy_document["source_file"])
    document_title = str(policy_document["document_title"])
    markdown_text = str(policy_document["content"])
    markdown_lines = markdown_text.splitlines()

    section_list: list[tuple[str, list[str]]] = []
    current_section_title = ""
    current_section_lines: list[str] = []

    for line_text in markdown_lines:
        if line_text.startswith("## "):
            if current_section_lines:
                section_list.append((current_section_title, current_section_lines))
            current_section_title = line_text[3:].strip()
            current_section_lines = [line_text]
        elif current_section_lines:
            current_section_lines.append(line_text)

    if current_section_lines:
        section_list.append((current_section_title, current_section_lines))

    # 如果某篇文档没有二级标题，就把整篇文档作为一个 chunk。
    if not section_list:
        section_list = [(document_title, markdown_lines)]

    policy_chunk_list: list[PolicyChunk] = []
    for section_index, (section_title, section_lines) in enumerate(section_list, start=1):
        chunk_id = f"{Path(source_file).stem}__section_{section_index:02d}"
        chunk_content = "\n".join(section_lines).strip()
        policy_chunk_list.append(
            PolicyChunk(
                chunk_id=chunk_id,
                source_file=source_file,
                document_title=document_title,
                section_title=section_title or document_title,
                content=chunk_content,
            )
        )

    return policy_chunk_list


def build_all_policy_chunks() -> list[PolicyChunk]:
    """
    加载全部政策文档并生成全部 chunk。

    参数：
        无。

    返回：
        list[PolicyChunk]：所有政策片段。

    用途：
        供索引构建脚本一次性生成可检索知识库。
    """
    policy_document_list = load_policy_documents()
    policy_chunk_list: list[PolicyChunk] = []

    for policy_document in policy_document_list:
        policy_chunk_list.extend(chunk_policy_document(policy_document))

    return policy_chunk_list


if __name__ == "__main__":
    documents = load_policy_documents()
    chunks = build_all_policy_chunks()
    print(f"加载政策文档数量：{len(documents)}")
    print(f"生成政策 chunk 数量：{len(chunks)}")
    for chunk in chunks[:2]:
        print(json.dumps(chunk.to_dict(), ensure_ascii=False, indent=2))

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
