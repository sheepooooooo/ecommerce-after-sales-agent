"""
【文件作用】
本文件是 pytest 测试，用来验证受控场景下的模块行为。

【在项目中的位置】
pytest 会自动收集本文件。它通过调用 app 或 scripts 中的公开入口来防止回归问题。

【主要输入与输出】
输入是固定测试数据、临时目录或 stub/mock。输出是断言结果。pytest 不应真实调用 DeepSeek、Docker 或外部服务。
"""

import json
from pathlib import Path
from typing import Any

import scripts.bootstrap_runtime as bootstrap_runtime_module


# 验证数据库不存在时 bootstrap 会调用初始化逻辑。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_bootstrap_creates_missing_database(tmp_path: Path, monkeypatch: Any) -> None:
    database_path = tmp_path / "orders.db"
    index_dir = tmp_path / "indexes"
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "a.md").write_text("# A\n\n## B\n内容", encoding="utf-8")

    monkeypatch.setattr(bootstrap_runtime_module, "POLICY_DIRECTORY", policy_dir)
    monkeypatch.setattr(bootstrap_runtime_module, "get_database_path", lambda: database_path)
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_policy_index_paths",
        lambda: {"chunks_path": index_dir / "policy_chunks.jsonl", "manifest_path": index_dir / "policy_index_manifest.json"},
    )
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_vector_index_paths",
        lambda: {
            "faiss_index_path": index_dir / "policy_faiss.index",
            "vector_manifest_path": index_dir / "policy_vector_manifest.json",
        },
    )
    monkeypatch.setattr(bootstrap_runtime_module, "initialize_database", lambda: database_path.write_text("db"))
    monkeypatch.setattr(bootstrap_runtime_module, "build_policy_index", lambda: index_dir.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(bootstrap_runtime_module, "build_vector_index", lambda: None)

    result = bootstrap_runtime_module.bootstrap_runtime()

    assert result["database_status"] == "created"
    assert "initialized_demo_database" in result["actions"]


# 验证数据库已存在时 bootstrap 不重置数据库内容。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_bootstrap_does_not_reset_existing_database(tmp_path: Path, monkeypatch: Any) -> None:
    database_path = tmp_path / "orders.db"
    database_path.write_text("existing-ticket-data", encoding="utf-8")
    index_dir = tmp_path / "indexes"
    index_dir.mkdir()
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    policy_file = policy_dir / "a.md"
    policy_file.write_text("# A", encoding="utf-8")
    sha = bootstrap_runtime_module.calculate_file_sha256(policy_file)
    (index_dir / "policy_chunks.jsonl").write_text("{}", encoding="utf-8")
    (index_dir / "policy_index_manifest.json").write_text(
        json.dumps({"source_files": [{"file": "a.md", "sha256": sha}]}),
        encoding="utf-8",
    )
    (index_dir / "policy_faiss.index").write_text("faiss", encoding="utf-8")
    (index_dir / "policy_vector_manifest.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(bootstrap_runtime_module, "POLICY_DIRECTORY", policy_dir)
    monkeypatch.setattr(bootstrap_runtime_module, "get_database_path", lambda: database_path)
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_policy_index_paths",
        lambda: {"chunks_path": index_dir / "policy_chunks.jsonl", "manifest_path": index_dir / "policy_index_manifest.json"},
    )
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_vector_index_paths",
        lambda: {
            "faiss_index_path": index_dir / "policy_faiss.index",
            "vector_manifest_path": index_dir / "policy_vector_manifest.json",
        },
    )
    monkeypatch.setattr(bootstrap_runtime_module, "initialize_database", lambda: database_path.write_text("reset"))
    monkeypatch.setattr(bootstrap_runtime_module, "validate_vector_index", lambda: {"valid": True})

    result = bootstrap_runtime_module.bootstrap_runtime()

    assert result["database_status"] == "existing"
    assert database_path.read_text(encoding="utf-8") == "existing-ticket-data"


# 验证索引文件缺失时 bootstrap 给出 created 状态。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_bootstrap_missing_indexes_reports_created(tmp_path: Path, monkeypatch: Any) -> None:
    database_path = tmp_path / "orders.db"
    database_path.write_text("db", encoding="utf-8")
    index_dir = tmp_path / "indexes"
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    monkeypatch.setattr(bootstrap_runtime_module, "POLICY_DIRECTORY", policy_dir)
    monkeypatch.setattr(bootstrap_runtime_module, "get_database_path", lambda: database_path)
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_policy_index_paths",
        lambda: {"chunks_path": index_dir / "policy_chunks.jsonl", "manifest_path": index_dir / "policy_index_manifest.json"},
    )
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_vector_index_paths",
        lambda: {
            "faiss_index_path": index_dir / "policy_faiss.index",
            "vector_manifest_path": index_dir / "policy_vector_manifest.json",
        },
    )
    monkeypatch.setattr(bootstrap_runtime_module, "build_policy_index", lambda: None)
    monkeypatch.setattr(bootstrap_runtime_module, "build_vector_index", lambda: None)

    result = bootstrap_runtime_module.bootstrap_runtime()

    assert result["policy_index_status"] == "created"
    assert "built_policy_indexes" in result["actions"]


# 验证 manifest 不一致时 bootstrap 提示手动重建。
# 学习提示：这是中文阅读注释，只解释设计意图，不影响运行逻辑。
def test_bootstrap_stale_manifest_suggests_manual_rebuild(tmp_path: Path, monkeypatch: Any) -> None:
    database_path = tmp_path / "orders.db"
    database_path.write_text("db", encoding="utf-8")
    index_dir = tmp_path / "indexes"
    index_dir.mkdir()
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "a.md").write_text("# changed", encoding="utf-8")
    (index_dir / "policy_chunks.jsonl").write_text("{}", encoding="utf-8")
    (index_dir / "policy_index_manifest.json").write_text(
        json.dumps({"source_files": [{"file": "a.md", "sha256": "old"}]}),
        encoding="utf-8",
    )
    (index_dir / "policy_faiss.index").write_text("faiss", encoding="utf-8")
    (index_dir / "policy_vector_manifest.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(bootstrap_runtime_module, "POLICY_DIRECTORY", policy_dir)
    monkeypatch.setattr(bootstrap_runtime_module, "get_database_path", lambda: database_path)
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_policy_index_paths",
        lambda: {"chunks_path": index_dir / "policy_chunks.jsonl", "manifest_path": index_dir / "policy_index_manifest.json"},
    )
    monkeypatch.setattr(
        bootstrap_runtime_module,
        "get_vector_index_paths",
        lambda: {
            "faiss_index_path": index_dir / "policy_faiss.index",
            "vector_manifest_path": index_dir / "policy_vector_manifest.json",
        },
    )

    result = bootstrap_runtime_module.bootstrap_runtime()

    assert result["success"] is False
    assert result["policy_index_status"] == "stale"
    assert "build_all_policy_indexes.py" in result["warnings"][0]
