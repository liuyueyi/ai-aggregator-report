## AI CLI / Claude Code Skills 生态专题日报

### 生态全景

| 项目 | PR 数 | Issue 数 | 热议点 |
| --- | --- | --- | --- |
| Claude Code | 0 | 4 | Instantly hitting usage limits with Max subscription, Claude Max plan session limits exhausted abnormally fast, Phone verification, Console scrolling top of history when claude add text to the console |
| OpenAI Codex | 0 | 6 | Burning tokens very fast, rate-limit cost per token jumped ~10-20x since June 16, Codex desktop app for Linux, GPT-5.5 Codex reasoning-token clustering, Support 1M token context for GPT-5.5 |
| Gemini CLI | 0 | 4 | Gemini CLI becomes extremely slow, "Allow for session" only allows once, Tracking: 429 / Capacity Issues, Add gemini-3.1-pro-preview |
| GitHub Copilot CLI | 0 | 4 | Bring back the GitHub Copilot in the CLI commands, "Copilot Requests" permission, Failed to list models, Sporadic policy blocking issue retrieving models |
| Kimi Code CLI | 4 | 0 | refactor: rewrite from Python to Bun + TypeScript + React Ink, fix(utils): bound broadcast queues and cap web store cache, feat(session): expose runtime identity (pid + session id), fix(aiohttp): reuse TCPConnector, feat: add thermodynamic regime management (T* framework) |
| OpenCode | 0 | 4 | Memory Megathread, GPT Models takes too long to respond, Copy To Clipboard is not working, Is there a way to sandbox the agent ?, always stuck at  “Preparing write...” |
| Qwen Code | 4 | 0 | feat(autofix): require isolated targeted E2E proof, feat(review): capture-tui — rendering claims get pixels, not prose (Phase 2), feat(cli): Add model toggle hotkey (Ctrl+F), feat(review): Add Maven multi-module verification, docs: add legacy code audit (/audit) design doc |
| DeepSeek TUI | 3 | 4 | release: Codewhale v0.9.4 release train, v0.9.3: Land and verify security hardening/code-scanning fixes, perf(prompt): progressively disclose fresh context, Put it up for agentclientprotocol/registry, feat: sidebar sessions panel with auto-resume and session history browsing |
| Claude Code Skills | 2 | 3 | Security: Community skills distributed under anthropic/ namespace enable trust boundary abuse, Add markdown-to-image skill: Markdown → PNG image cards, Enable org-wide skill sharing in Claude.ai, Add webpilot skill — CDP-free browser automation, run_eval.py: claude -p never triggers skills/commands (0% trigger rate across all queries) |

### 热点讨论

- **Claude Code**: 用户反馈在使用Max订阅时，使用频率过高导致使用限制，以及电话验证问题。
- **OpenAI Codex**: 用户反馈使用速度过快，费用过高，以及对Linux桌面应用程序的需求。
- **Gemini CLI**: 用户反馈在执行小代码编辑任务时速度极慢，以及对“允许会话”功能的限制。
- **GitHub Copilot CLI**: 用户反馈需要恢复CLI命令中的GitHub Copilot，以及对权限请求的可见性。
- **Kimi Code CLI**: 用户对代码重构、内存泄漏修复、会话暴露、TCP连接器重用和热力学管理框架的添加表示赞赏。
- **OpenCode**: 用户反馈内存问题、GPT模型响应时间过长、复制到剪贴板功能不正常、沙箱代理的需求以及“Preparing write...”的卡顿问题。
- **Qwen Code**: 用户对自动修复、渲染声明、模型切换快捷键、Maven多模块验证和代码审计文档的添加表示赞赏。
- **DeepSeek TUI**: 用户对发布新版本、安全加固、性能改进和会话面板的添加表示赞赏。
- **Claude Code Skills**: 用户对安全漏洞、Markdown到图像技能、组织内技能共享、Webpilot技能和命令触发率的问题表示关注。

### 趋势信号

- AI编程CLI工具的用户反馈主要集中在性能、安全性和功能扩展方面。
- 生态系统中对Linux桌面应用程序的需求逐渐增加。
- 用户对代码审计和安全加固的关注度提升。
- 生态系统的活跃度较高，但部分项目在社区互动方面还有待加强。

[完整 markdown 专题日报正文](#)