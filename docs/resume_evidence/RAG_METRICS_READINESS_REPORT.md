# RAG 指标可计算性检查报告

- 检查时间：2026-06-23T13:06:12
- RAG 项目路径：C:\Users\16793\Desktop\all-in-rag\code\C1
- 路径是否存在：True
- 当前能否真实计算 Hit@K / Recall@K / MRR：False

## 已发现材料

- 评测题 JSONL：['agent_eval_questions.jsonl', 'agent_planner_eval_questions.jsonl', 'eval_questions.jsonl', 'eval_questions_30_template.jsonl', 'eval_questions_annotated.example.jsonl', 'eval_questions_auto_candidate.jsonl', 'eval_results\\agent_eval_details.jsonl', 'eval_results\\agent_planner_eval_details.jsonl', 'eval_results\\eval_questions_20260615_222929_700564_rag_eval_details.jsonl', 'eval_results\\eval_questions_20260615_224139_678497_rag_eval_details.jsonl', 'eval_results\\eval_questions_20260615_225656_247059_rag_eval_details.jsonl', 'eval_results\\eval_questions_20260616_002222_688101_rag_eval_details.jsonl', 'eval_results\\eval_questions_20260616_004156_449115_rag_eval_details.jsonl', 'eval_results\\eval_questions_20260616_131402_512389_rag_eval_details.jsonl', 'eval_results\\langgraph_agent_eval_details.jsonl', 'eval_results\\rag_eval_details.jsonl', 'eval_results\\retrieval_experiments\\retrieval_experiment_details_20260615_225819_797054.jsonl', 'eval_results\\retrieval_experiments\\retrieval_experiment_details_20260616_002348_984105.jsonl', 'eval_results\\retrieval_experiments\\retrieval_experiment_details_20260616_004324_386457.jsonl', 'eval_results\\retrieval_experiments\\retrieval_experiment_details_20260616_131554_167876.jsonl', 'eval_results\\retrieval_experiments\\retrieval_experiment_details_latest.jsonl']
- 人工标注字段：[]
- 检索结果或实验结果：[]
- 评测脚本：['eval_annotation_helper.py', 'evaluate_agent.py', 'evaluate_agent_planner.py', 'evaluate_langgraph_agent.py', 'evaluate_rag.py', 'retrieval_experiment.py']
- 日志或耗时记录：['logs\\app.log']

## 缺少什么

- 未确认评测题包含 source/file/page/chunk 等人工标注。
- 未发现检索结果或实验结果文件。

## 下一步建议

- 可优先检查并运行：python eval_annotation_helper.py
- 可优先检查并运行：python evaluate_agent.py
- 可优先检查并运行：python evaluate_agent_planner.py
- 可优先检查并运行：python evaluate_langgraph_agent.py
- 可优先检查并运行：python evaluate_rag.py
- 可优先检查并运行：python retrieval_experiment.py

## 指标边界

- 没有人工标注时，不能声称 Recall@K 或 MRR，因为无法判断某条检索结果是否真相关。
- 只有题目、人工标注答案来源和检索结果能够逐题对齐时，才能计算 Hit@K、Recall@K、MRR。
- 本脚本不修改 RAG 项目代码，也不计算虚假结果。
