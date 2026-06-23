"""
【文件作用】
本文件是项目中的 Python 模块，用于支撑当前目录对应的 Agent、RAG、Tool、API 或工程化能力。

【在项目中的位置】
它会被项目内的服务、脚本或测试按需导入。请结合文件名和所在目录理解具体调用关系。

【主要输入与输出】
输入和输出取决于具体函数。本注释只解释阅读路径，不改变业务逻辑、数据库、LLM 或 API 行为。
"""

import sys
from pathlib import Path

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.retrieval.policy_index_manager import build_policy_index
from app.retrieval.vector_index_manager import build_vector_index


if __name__ == "__main__":
    # print 仅用于本地学习演示，正式服务不使用 print 作为日志。
    chunk_manifest = build_policy_index()
    vector_manifest = build_vector_index()
    print("全部政策索引构建完成")
    print(f"政策文档数量：{chunk_manifest['document_count']}")
    print(f"chunk 数量：{chunk_manifest['chunk_count']}")
    print(f"Embedding 模型：{vector_manifest['embedding_model_name']}")
    print(f"向量维度：{vector_manifest['vector_dimension']}")
    print(f"chunk 索引路径：{chunk_manifest['chunks_path']}")
    print(f"FAISS 索引路径：{vector_manifest['faiss_index_path']}")
