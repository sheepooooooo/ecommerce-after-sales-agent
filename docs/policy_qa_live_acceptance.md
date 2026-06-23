# 政策问答真实模型验收说明

本文档说明 `scripts/run_policy_qa_live_acceptance.py` 的用途、边界和安全运行方式。

## 为什么 mock 单元测试不能替代真实模型验收

pytest 中的政策问答测试主要验证代码路径、引用校验、订单事实边界、无关问题拦截和异常处理。这些测试必须稳定、快速、可重复，因此不会真实调用 DeepSeek。

真实模型验收用于补足另一类风险：模型服务是否可用、JSON Object 输出模式是否兼容、模型是否会稳定返回可解析 JSON、引用字段是否容易漂移、延迟是否处于可接受范围。这些风险只有真实调用时才能暴露。

## 为什么验收脚本不纳入 pytest

真实模型验收依赖外部网络、API Key、账户余额、模型可用性和服务端限流。若放入 pytest，会让自动化测试变得不稳定，也可能在无意中消耗额度。

因此该脚本仅供开发者手动执行。pytest 仍然只覆盖可离线、可重复、不会调用真实 API 的逻辑。

## 引用合法不等于答案绝对正确

当前引用校验只检查模型声明的 `chunk_id` 是否来自本次检索到的政策证据。它可以防止模型引用不存在的 chunk 或本次未检索到的 chunk。

但是引用合法并不保证答案语义完全正确，也不保证模型完整覆盖政策中的所有例外情形。真实项目中仍需要结合人工抽检、评测集、回归测试和业务专家校验。

## 如何安全运行验收

1. 复制 `.env.example` 为 `.env`。
2. 在 `.env` 中填写自己的 `DEEPSEEK_API_KEY`。
3. 不要把真实 API Key 写入代码、README、测试、报告或聊天记录。
4. 先检查连接：

```powershell
python scripts\check_llm_connection.py
```

5. 再执行真实模型验收：

```powershell
python scripts\run_policy_qa_live_acceptance.py
```

脚本会生成：

```text
eval_results/policy_qa_live_acceptance.json
eval_results/policy_qa_live_acceptance_report.md
```

这些文件只保存结构化摘要，不保存完整系统 Prompt、完整 API 原始响应或 API Key。

## 常见问题处理

API 超时：

- 检查网络和代理配置。
- 适当调大 `LLM_TIMEOUT_SECONDS`，例如 `60`。
- 稍后重试，排除服务端临时波动。

余额不足或鉴权失败：

- 检查 `DEEPSEEK_API_KEY` 是否配置在 `.env` 中。
- 检查账户余额、权限和模型访问资格。
- 不要把 API Key 粘贴到日志、报告或 issue 中。

模型不可用或模型名错误：

- 检查 `LLM_MODEL` 是否为预期模型。
- 当前项目默认使用 `deepseek-v4-flash`，不要在代码中硬编码替换为其他模型。
- 如服务端返回参数不兼容，请根据错误检查 `LLM_ENABLE_THINKING` 与 SDK 版本。

JSON 解析失败：

- 确认请求仍然使用 JSON Object 输出模式。
- 检查模型是否输出了 Markdown、代码块或额外说明。
- 可临时查看验收报告中的错误类型和失败原因，但不要保存完整原始响应到仓库。

引用校验失败：

- 检查模型返回的 `cited_chunk_ids` 是否来自本次 retrieved chunks。
- 检查检索 TopK 是否召回了正确政策。
- 引用失败不能通过硬编码验收结果绕过，应修复提示词、检索或引用校验逻辑。

## 项目边界

本验收只验证智选商城模拟政策问答链路，不代表任何真实平台政策、法律意见或消费者权益承诺。

脚本不会执行真实退款、真实订单取消、真实物流修改或真实工单创建。具体订单退款资格仍应由订单查询 Tool 和退款资格规则 Tool 判断。
