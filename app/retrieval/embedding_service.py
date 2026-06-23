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


import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from app.config import EMBEDDING_MODEL_NAME


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    加载并缓存 SentenceTransformer 模型。

    参数：
        无。

    返回：
        SentenceTransformer：已加载的 BGE 中文 Embedding 模型。

    用途：
        模型加载较慢，因此必须复用同一个模型实例，避免每次检索都重新加载。
    """
    try:
        # 文档和 query 必须用同一个模型编码，否则向量空间不一致，相似度就没有意义。
        return SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as error:
        raise RuntimeError(
            "Embedding 模型加载失败。"
            f"模型名：{EMBEDDING_MODEL_NAME}。"
            f"失败原因：{error}。"
            "请检查网络是否能访问 Hugging Face、磁盘空间是否充足、"
            "以及 sentence-transformers / torch 依赖是否安装完整。"
        ) from error


def embed_text_list(text_list: list[str]) -> np.ndarray:
    """
    将多段文本编码为二维 float32 向量数组。

    参数：
        text_list：需要编码的文本列表。

    返回：
        np.ndarray：形状为 [文本数量, 向量维度] 的 float32 数组。

    用途：
        构建向量索引时批量编码全部政策 chunk。
    """
    if not text_list:
        raise ValueError("text_list 不能为空，无法生成 Embedding。")
    if any(not isinstance(text, str) or not text.strip() for text in text_list):
        raise ValueError("text_list 中存在空文本或非字符串，无法生成 Embedding。")

    embedding_model = get_embedding_model()

    # normalize_embeddings=True 会做 L2 归一化。
    # 向量归一化后，内积可以等价衡量余弦相似度；本项目使用 FAISS IndexFlatIP。
    embedding_array = embedding_model.encode(
        text_list,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embedding_array, dtype=np.float32)


def embed_single_text(text: str) -> np.ndarray:
    """
    将单条文本编码为二维 float32 向量数组。

    参数：
        text：需要编码的单条文本。

    返回：
        np.ndarray：形状为 [1, 向量维度] 的 float32 数组。

    用途：
        检索时将用户 query 编码为向量，再交给 FAISS search。
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text 不能为空，无法生成 query Embedding。")
    return embed_text_list([text])


if __name__ == "__main__":
    # 以下 print 仅用于学习演示，正式服务不使用 print 作为日志。
    first_text = "订单已经发货但不想要了怎么办"
    second_text = "包裹都寄出来了，我改变主意了怎么处理"
    demo_vectors = embed_text_list([first_text, second_text])
    cosine_similarity = float(np.dot(demo_vectors[0], demo_vectors[1]))
    print("Embedding 学习演示：")
    print(f"向量维度：{demo_vectors.shape[1]}")
    print(f"第一条向量前 5 个值：{demo_vectors[0][:5].tolist()}")
    print(f"两句话的余弦相似度：{cosine_similarity:.4f}")

# ============================================================
# 【阅读重点】
# 1. 先看文件顶部说明，理解它在项目中的位置。
# 2. 再看核心函数的输入、输出和副作用。
# 3. 最后结合测试理解它防止哪类回归问题。
# ============================================================
