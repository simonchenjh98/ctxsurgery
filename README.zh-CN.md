# ctxsurgery

**定位哪些丢失的上下文片段，能修复一个失败任务。**

[English](README.md) · Python 3.10+ · MIT · Alpha

Agent 在压缩、摘要或重写上下文前能完成任务，之后失败了。日志能告诉你“少了什么”；`ctxsurgery` 进一步用实验检查：**加回哪几段能恢复行为？只是多塞一些无关文字，会不会也恢复？**

输入前后两份上下文、一个任务、可执行断言和调用器。输出受控实验、经过缩减的修复片段集合、完整 JSON 记录和本地 HTML 报告。不是压缩算法，不是新的 Agent 框架，也不需要部署可观测性平台。

## Alpha 状态与实测案例

目前已有两组[真实模型实验记录](examples/live-context-cases.md)，也保留了此前未完成的试跑：

- **原创 Webhook 策略任务**：原文与模型生成的摘要均为 3/3 通过，没有复现退化，不声称修复成功。
- **公开历史记忆上的新检索任务**：原文 3/3、改写后 0/3、恢复函数所在片段后 3/3、同字符数填充对照 0/3；27 次调用完成逐片段移除，得到单片段的已测试 `1-minimal` 修复。

第二项是在看到已知遗漏后专门设计的检索任务，人工划分了三个片段。它证明的是这个任务中的信息恢复，**不是生产事故、AIME 数学答案修复、未知根因的自动发现，也不是广泛模型有效性证明**。内置离线 Demo 仍是合成案例。详细设置、哈希、复现命令、负结果与内容脱敏后的证据见上方链接。

下一里程碑是独立贡献者提供的真实工作流退化案例，而不仅是定向检索探针。项目仍处于 Alpha；每组连续重复三次，不等于统计显著性保证。

## 一分钟运行

克隆仓库并运行离线演示：

```sh
git clone https://github.com/simonchenjh98/ctxsurgery.git
cd ctxsurgery
python -m pip install -e .
ctxsurgery demo --out artifacts/demo
```

打开 `artifacts/demo/report.html`，原始证据在同目录的 `report.json`。

**这个 Demo 是离线、确定性的合成案例，不是实测大模型。** 不需要 API Key，不调用外部模型，不上传或发布内容。它验证工具流程，不证明模型实际表现。

预期定位到 `ci-gate` 和 `approval-gate` 两项发布策略；标题风格备注可以删掉。调用器是一个小型配置解释器，结果来自收到的上下文，不是硬编码的诊断结论。

也可以用 `python -m ctxsurgery demo --out artifacts/demo`。

## 接入真实失败案例

将以下内容保存为 `case.json`：

```json
{
  "version": 1,
  "name": "摘要丢失了发布审批约束",
  "before": [
    {"id": "format", "text": "Answer with exactly one uppercase word."},
    {"id": "approval", "text": "A release without explicit approval must be answered BLOCKED."}
  ],
  "after": "Answer with exactly one uppercase word.",
  "task": "The release has no explicit approval. Should it proceed?",
  "evaluator": {"type": "exact", "expected": "BLOCKED"}
}
```

在环境变量中配置 `OPENAI_API_KEY`，选择你可使用的模型：

```sh
ctxsurgery diagnose case.json --provider openai --model YOUR_MODEL --repeats 3 --max-calls 48 --out artifacts/live
```

默认端点是 `https://api.openai.com/v1`，实际调用可能计费。这个示例可能在缺少约束时也能答对，此时 `already_passing` 才是正确结果：断言没有证明退化发生。真实诊断应使用你的真实失败案例。

支持 `--base-url https://YOUR_HOST/v1` 和 `--api-key-env YOUR_KEY_VARIABLE`。除回环地址（例如 `http://127.0.0.1:8000/v1`）外要求 HTTPS。不要把密钥放入案例 JSON 或命令行参数。

回环端点可以不设置密钥。初版适配器使用 OpenAI 兼容的 Chat Completions 格式（`system` 上下文、`user` 任务、`temperature=0`、`max_tokens`）；需要不同参数的模型可以自行接入 Python 调用器。`--max-output-tokens` 默认 1024，`--timeout` 默认 30 秒，不自动重试或跟随重定向。

端点支持时可显式使用 `--reasoning-effort low`（或 `medium` / `high`），不支持则省略。`finish_reason="length"` 表示输出被截断，按未完成调用处理，不能把它或网络错误计为任务失败。

只比较快照、或重新生成报告，不调用模型：

```sh
ctxsurgery diff before.txt after.txt --out candidates.json
ctxsurgery report artifacts/live/report.json --out artifacts/live/report.html
```

纯文本按空行切片；需要稳定实验单元时，建议使用带明确 `id` 的 JSON 片段。`after` 也支持片段列表。

### 真实归档案例：记忆被占位符替代

可选的 [Dynamic Cheatsheet 案例](examples/public-dynamic-cheatsheet.md) 从固定版本的公开仓库导入两份历史模型记忆，展示原有文字被“之前内容保留”占位符替代的情况：

```sh
python scripts/import_public_example.py --out artifacts/public-example
ctxsurgery diff artifacts/public-example/before.txt artifacts/public-example/after.txt
```

导入脚本会明确下载固定公开源并验证校验和；正常安装、测试和离线 Demo 不下载。导入和 diff 本身**仅是静态差异证据**。另有[独立的真实检索探针](examples/live-context-cases.md#case-2-a-newly-authored-retrieval-probe-on-archived-memories)，测试两个函数默认参数的信息恢复，不重放或修复原归档中的 AIME 任务。来源、许可边界与解释限制见案例说明。

## 实验检查什么

1. 用忽略空白差异的精确子串匹配，找出可能丢失的片段；增加词边界检查，避免部分词误匹配。
2. 验证原始上下文确实成功、缩减后的上下文确实失败。
3. 加回候选片段，并与**字符数匹配的中性填充文字**对照。
4. 按顺序逐个删除片段，缩减仍符合实验判据的修复集合。
5. 保存每次真实调用的结果与错误。错误计入预算，但不能被当成任务失败的证据。

`status` 和 `minimality` 必须一起看。只有实际建立的 `1-minimal` 才能说“这个集合中再单独删任一片段，会破坏已测试的修复判据”。**不等于全局最小集合，不等于唯一原因。**

原始上下文不成功、压缩后仍成功、恢复无效、填充文字也能恢复，都是有价值的结果。预算用完或调用出错，则说明证据不完整。

CLI 退出码：`0` 表示诊断完成（也包括否定发现），`2` 表示输入/配置错误，`3` 表示预算耗尽或调用错误。

## 断言与 Python 接口

内置三种断言：

| 类型 | 例子 | 判定 |
| --- | --- | --- |
| `exact` | `{"type":"exact","expected":"BLOCKED"}` | 去掉首尾空白后，字符串完全一致 |
| `contains` | `{"type":"contains","all":["BLOCKED"],"none":["APPROVED"]}` | 包含所有必需子串、不包含禁用子串；区分大小写，至少一个断言 |
| `json` | `{"type":"json","expected":{"allowed":false}}` | 合法 JSON、结构及值类型一致；不接受 Markdown 代码围栏 |

```python
import json
from pathlib import Path
from ctxsurgery.engine import diagnose
from ctxsurgery.models import Case
from ctxsurgery.report import render_html

case = Case.from_dict(json.loads(Path("case.json").read_text(encoding="utf-8")))

def runner(context: str, task: str) -> str:
    # your_agent 是你自己的接入，不是本项目内置依赖。
    # 每次调用必须使用独立或已重置的状态。
    return your_agent.run(context=context, task=task)

result = diagnose(case, runner, repeats=3, max_calls=48)
Path("report.html").write_text(render_html(result), encoding="utf-8")
```

调用器也可以返回包含用量信息的 `ctxsurgery.models.Response`。诊断会反复调用 Agent，请在隔离环境中运行，关闭写文件、发消息等副作用，并重置记忆，避免实验组相互污染。

## 必须知道的边界

- 候选发现是启发式，不理解语义；改写可能被误认为丢失。
- 有序贪心缩减只建立经过测试的 **1-minimal**，不做所有子集的穷举；片段交互和顺序会影响结果。
- 填充文字匹配的是**字符数，不是 token 数**，并非完美安慰剂对照。
- 少量重复采样不是显著性检验；通过阈值不是“因果置信度”。
- 加回片段是一次修复干预，不会复原原有位置、隐藏状态或全部生产环境。
- 结论受断言约束：未检测的行为仍可能出错。
- v0.1 处理上下文快照与单个任务，不提供完整工具轨迹重放、追踪平台导入或语义匹配。

## 隐私

`demo`、`diff`、`report` 无需网络。真实 `diagnose` 会将任务和上下文变体发送到你明确选择的模型端点。项目没有分析埋点或报告遥测。

报告可能包含私有上下文、模型输出和错误。使用 `--redact` 可对保存的报告中的案例名、候选文本、试验输出和错误进行脱敏：

```sh
ctxsurgery diagnose case.json --provider openai --model YOUR_MODEL --redact --out artifacts/redacted
```

**脱敏报告不代表输入不会发送给模型端点，也不是通用密钥扫描器。** 片段 ID 等元信息仍可能敏感。分享前检查 JSON 与 HTML，不要提交私有案例或真实运行报告。

## 开发

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

贡献要求见 [CONTRIBUTING.md](CONTRIBUTING.md)，许可证为 [MIT](LICENSE)。项目仍在早期：证据清楚、失败状态诚实，比看起来漂亮的定位结论更重要。
