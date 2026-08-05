# 【AI CLI / Claude Code Skills 生态】专题日报

**日期**：2026-08-05

## 一、生态全景与活跃度对比

本期追踪 Claude Code、OpenAI Codex、Gemini CLI、GitHub Copilot CLI、Kimi Code CLI、OpenCode、Qwen Code、DeepSeek TUI 及 Claude Code Skills 仓库。以社区互动热度（评论数）为核心指标，各项目活跃度排行如下：

| 项目 | PR 数 | Issue 数 | 近期 Release | 热议点（最高热度） |
|---|---|---|---|---|
| Claude Code | 0 | 5 | v2.1.222 | Max 订阅用量极速耗尽（1484 评论） |
| OpenAI Codex | 0 | 5 | rust-v0.147.0-alpha.7 | Token 燃烧过快（628 评论） |
| Gemini CLI | 0 | 5 | v0.55.0-nightly | 小任务极度缓慢/卡死（218 评论） |
| OpenCode | 0 | 5 | v1.18.13 | 记忆系统大讨论（122 评论） |
| Qwen Code | 5 | 0 | desktop-v0.1.0 | 自动修复需独立 E2E 证明（62 评论） |
| DeepSeek TUI | 2 | 3 | v0.9.3 | Codewhale v0.9.4 发布列车（40 评论） |
| Claude Code Skills | 2 | 3 | 无 | 社区 Skills 信任边界滥用（43 评论） |
| GitHub Copilot CLI | 0 | 5 | v1.0.79-2 | 恢复原有 CLI 命令工作流（37 评论） |
| Kimi Code CLI | 5 | 0 | 1.49.0 | 从 Python 重写为 Bun+TS+React Ink（12 评论） |

## 二、差异定位与高热度信号点评

### Claude Code：用量限制引发社区风暴
* **速览**：今日发布 [v2.1.222](https://github.com/anthropics/claude-code/releases/tag/v2.1.222) 与 [v2.1.221](https://github.com/anthropics/claude-code/releases/tag/v2.1.221)。
* **热点讨论**：[Max 订阅用量极速耗尽 BUG](https://github.com/anthropics/claude-code/issues/16157)（1484 评论）与 [3 月 23 日后 CLI 会话限制异常](https://github.com/anthropics/claude-code/issues/38335)（831 评论）席卷社区。此外 [手机验证 BUG](https://github.com/anthropics/claude-code/issues/34229) 也引发 742 评论。功能层面，[支持 AGENTS.md 请求](https://github.com/anthropics/claude-code/issues/6235)备受期待（348 评论）。
* **趋势**：计费与会话限制机制成为用户最大痛点，验证流程的稳定性也亟待优化。

### OpenAI Codex：Token 消耗与推理性能成焦点
* **速览**：连续发布 [rust-v0.147.0-alpha.7](https://github.com/openai/codex/releases/tag/rust-v0.147.0-alpha.7) 等多个 Alpha 版本。
* **热点讨论**：[Token 燃烧过快](https://github.com/openai/codex/issues/14593)（628 评论）是社区核心痛点。6 月以来，[Plus 计划每 Token 成本跳增 10-20 倍](https://github.com/openai/codex/issues/28879) 引发广泛不满（210 评论）。技术层面，[GPT-5.5 推理 Token 聚集导致复杂任务性能退化](https://github.com/openai/codex/issues/30364)（183 评论）及 [支持 1M 上下文](https://github.com/openai/codex/issues/19464)（132 评论）是核心演进信号。
* **趋势**：成本控制与长上下文支持是 Codex 当前技术演进的两大主轴。

### Gemini CLI：性能瓶颈与容量危机
* **速览**：持续推送 [v0.55.0-nightly](https://github.com/google-gemini/gemini-cli/releases/tag/v0.55.0-nightly.20260803.gf47d6c6f7) 每日构建。
* **热点讨论**：[小代码编辑任务极度缓慢/卡死](https://github.com/google-gemini/gemini-cli/issues/22141)（218 评论）严重影响体验。[429 容量问题追踪](https://github.com/google-gemini/gemini-cli/issues/24937)（131 评论）与 [添加 gemini-3.1-pro-preview 呼声](https://github.com/google-gemini/gemini-cli/issues/19532)（127 评论）表明社区对新模型与稳定性的渴求。
* **趋势**：Agent 循环延迟与容量限制是制约 Gemini CLI 体验的瓶颈。

### OpenCode：记忆机制与易用性探讨
* **速览**：发布 [v1.18.13](https://github.com/anomalyco/opencode/releases/tag/v1.18.13)。
* **热点讨论**：[记忆系统大讨论](https://github.com/anomalyco/opencode/issues/20695)（122 评论）居首。[GPT 模型响应过慢](https://github.com/anomalyco/opencode/issues/29079)（118 评论）与 [复制到剪贴板失效](https://github.com/anomalyco/opencode/issues/4283)（117 评论）是高频痛点。安全方面，[Agent 沙箱隔离](https://github.com/anomalyco/opencode/issues/2242)获 81 评论关注。
* **趋势**：记忆与沙箱隔离是开源 CLI 工具走向成熟的关键技术挑战。

### Claude Code Skills：信任边界与自动化触发缺陷
* **热点讨论**：安全方面，[anthropic/ 命名空间下的社区 Skills 存在信任边界滥用风险](https://github.com/anthropics/skills/issues/492)（43 评论）值得警惕。功能方面，[Markdown 转图片 Skill](https://github.com/anthropics/skills/pull/1066) 与 [无 CDP 浏览器自动化 webpilot](https://github.com/anthropics/skills/pull/571) 是新晋 PR。但 [run_eval.py 中 Skills 0% 触发率](https://github.com/anthropics/skills/issues/556)（12 评论）暴露了自动化触发链路的严重缺陷。
* **趋势**：生态繁荣伴随安全审查需求上升，自动化触发可靠性需紧急修复。

### Qwen Code：TUI 渲染与审计能力跃升
* **速览**：发布 [Desktop v0.1.0](https://github.com/QwenLM/qwen-code/releases/tag/desktop-v0.1.0) 与 [v0.21.6-preview.0](https://github.com/QwenLM/qwen-code/releases/tag/v0.21.6-preview.0)。
* **热点讨论**：PR 活跃，[autofix 要求独立 E2E 证明](https://github.com/QwenLM/qwen-code/pull/8318)（62 评论）领衔。[capture-tui 渲染像素而非文本](https://github.com/QwenLM/qwen-code/pull/8388)（22 评论）与 [遗留代码审计设计文档](https://github.com/QwenLM/qwen-code/pull/8397)（34 评论）展示技术创新。UI 层面，[Fleet View 重写以匹配 Claude Code](https://github.com/QwenLM/qwen-code/pull/6451)（41 评论）。
* **趋势**：Qwen Code 正在通过 TUI 视觉化与严格验证机制构建差异化护城河。

### DeepSeek TUI：安全加固与发布列车推进
* **速览**：发布 [v0.9.3](https://github.com/Hmbown/CodeWhale/releases/tag/v0.9.3)。
* **热点讨论**：[Codewhale v0.9.4 发布列车 PR](https://github.com/Hmbown/CodeWhale/pull/5135)（40 评论）推进版本迭代。[安全加固与代码扫描修复](https://github.com/Hmbown/CodeWhale/issues/3368)（29 评论）与 [渐进式上下文披露](https://github.com/Hmbown/CodeWhale/pull/5077)（14 评论）是近期重点。
* **趋势**：在发布节奏加快的同时，强化安全扫描与上下文管理。

### GitHub Copilot CLI：授权与策略拦截痛点
* **速览**：发布 [v1.0.79-2](https://github.com/github/copilot-cli/releases/tag/v1.0.79-2)。
* **热点讨论**：[恢复原有 CLI 命令以不破坏工作流](https://github.com/github/copilot-cli/issues/53)（37 评论）呼声高。[细粒度 Token 权限不可见](https://github.com/github/copilot-cli/issues/223)（31 评论）与 [403 未授权错误](https://github.com/github/copilot-cli/issues/552)（30 评论）反映授权机制复杂。
* **趋势**：权限管理与 API 稳定性是 Copilot CLI 体验提升的关键。

### Kimi Code CLI：底层架构重构
* **速览**：发布 [1.49.0](https://github.com/MoonshotAI/kimi-cli/releases/tag/1.49.0)。
* **热点讨论**：核心 PR [从 Python 重写为 Bun + TypeScript + React Ink](https://github.com/MoonshotAI/kimi-cli/pull/1707)（12 评论）标志底层架构大换血。稳定性方面，[限制广播队列防内存泄漏](https://github.com/MoonshotAI/kimi-cli/pull/2236)（12 评论）与 [复用 TCPConnector 防连接泄漏](https://github.com/MoonshotAI/kimi-cli/pull/2231)（7 评论）是重点。
* **趋势**：向现代 JS 运行时迁移，大幅优化底层资源管理与稳定性。