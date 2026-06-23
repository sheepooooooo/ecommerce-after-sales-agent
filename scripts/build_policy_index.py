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


if __name__ == "__main__":
    # print 仅用于本地学习演示，后续服务化时应使用结构化日志。
    manifest = build_policy_index()
    print("政策索引构建完成")
    print(f"文档数量：{manifest['document_count']}")
    print(f"chunk 数量：{manifest['chunk_count']}")
    print(f"索引路径：{manifest['chunks_path']}")
    print(f"manifest 路径：{manifest['manifest_path']}")
