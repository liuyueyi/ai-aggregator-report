## AI CLI / Claude Code Skills 生态专题日报（2026-08-07）

### 生态全景

| 项目 | PR 数 | Issue 数 | 热议点 | 
|------|-------|----------|-------|
| Claude Code | 0 | 4 | [BUG] Instantly hitting usage limits with Max subscription, [BUG] Claude Max plan session limits exhausted abnormally fast since March 23, 2026 (CLI usage), [BUG] Phone verification, [BUG] Console scrolling top of history when claude add text to the console, [Feature Request] Support AGENTS.md |
| OpenAI Codex | 0 | 4 | [BUG] Burning tokens very fast, [BUG] Codex (gpt-5.5, Plus plan) — rate-limit cost per token jumped ~10-20x since June 16, draining the 5h budget in 2-3 prompts, [BUG] Tracking: 429 / Capacity Issues, [Feature Request] Support 1M token context for GPT-5.5 |
| Gemini CLI | 0 | 4 | [BUG] Gemini CLI becomes extremely slow (1+ HOURS) / stuck during small code-edit tasks (agent loop + model response delays), [BUG] "Allow for session" only allows once for shell commands that include a path, [BUG] Tracking: 429 / Capacity Issues, [Feature Request] Add gemini-3.1-pro-preview |
| GitHub Copilot CLI | 0 | 4 | [Feature Request] Bring back the GitHub Copilot in the CLI commands to not break workflows, [Feature Request] "Copilot Requests" permission for fine-grained tokens should be visible for org-owned tokens, [BUG] Failed to list models: 403 : unauthorized: not authorized to use this Copilot feature, [BUG] Sporadic policy blocking issue retrieving models |
| Kimi Code CLI | 0 | 4 | [PR] refactor: rewrite from Python to Bun + TypeScript + React Ink, [PR] fix(utils): bound broadcast queues and cap web store cache to prevent memory leaks, [PR] feat(session): expose runtime identity (pid + session id) for external observers, [PR] fix(aiohttp): reuse TCPConnector to prevent connection leaks |
| OpenCode | 0 | 5 | [BUG] Memory Megathread, [BUG] GPT Models takes too long to respond, [BUG] Copy To Clipboard is not working, [BUG] always stuck at “Preparing write...”, [Feature Request] Add Maven multi-module verification |
| Qwen Code | 4 | 0 | [PR] feat(review): capture-tui — rendering claims get pixels, not prose (Phase 2), [PR] feat(autofix): require isolated targeted E2E proof, [PR] feat(cli): add audio bridge for attachments, [PR] feat(review): Add Maven multi-module verification, [PR] feat(channels): add Feishu ask-user question cards |
| DeepSeek TUI | 0 | 5 | [BUG] v0.9.3: Land and verify security hardening/code-scanning fixes, [BUG] Put it up for agentclientprotocol/registry, [BUG] feat: sidebar sessions panel with auto-resume and session history browsing, [BUG] v0.9.3: Fleet model classes, loadout auto, and semantic route roles, [BUG] 文案展示不全 |
| Claude Code Skills | 2 | 3 | [Security] Community skills distributed under anthropic/ namespace enable trust boundary abuse, [Feature Request] Enable org-wide skill sharing in Claude.ai, [BUG] run_eval.py: claude -p never triggers skills/commands (0% trigger rate across all queries), [Feature Request] Add markdown-to-image skill: Markdown → PNG image cards, [Feature Request] Add webpilot skill — CDP-free browser automation |

### 差异定位

- **Claude Code** 与 **OpenAI Codex** 都面临较高的使用限制问题，但 Claude Code 的用户反馈更为集中，主要集中在订阅限制和会话管理上。
- **Gemini CLI** 和 **GitHub Copilot CLI** 都有性能和权限相关的 bug 报告，但 Gemini CLI 的问题涉及更广泛的性能瓶颈。
- **Qwen Code** 在 PR 数量上表现突出，展示了其在功能扩展方面的活跃度，特别是对 Markdown 渲染和附件处理的增强。
- **OpenCode** 面临较多性能和用户体验问题，其中“Preparing write...”的卡顿问题被多次提及。
- **DeepSeek TUI** 的热议点主要集中在功能改进和安全性问题，但 PR 数量较少，表明其开发活跃度较低。
- **Claude Code Skills** 的社区互动较为活跃，特别是安全性和技能扩展方面的问题和建议。

### 趋势信号

- **Claude Code** 在 2026 年 8 月 6 日发布了多个版本更新，包括 v2.1.223、v2.1.222 和 v2.1.221，表明其在近期有较高的更新频率。
- **OpenAI Codex** 在 2026 年 8 月 6 日发布了 rust-v0.147.0-alpha.13 和 rust-v0.146.1，显示其在技术迭代上持续进行。
- **Qwen Code** 在 2026 年 8 月 1 日至 6 日之间发布了多个 PR，包括对 Markdown 渲染和附件处理的支持，反映出其在功能增强方面的活跃度。
- **OpenCode** 在 2026 年 8 月 5 日发布了 v1.18.14，显示其在近期有持续更新。
- **DeepSeek TUI** 在 2026 年 7 月 31 日发布了 v0.9.3，表明其在安全性与功能优化上有所进展。

### 高热度信号点评

- **Claude Code** 的 [BUG] Instantly hitting usage limits with Max subscription（https://github.com/anthropics/claude-code/issues/16157）和 [BUG] Claude Max plan session limits exhausted abnormally fast since March 23, 2026 (CLI usage)（https://github.com/anthropics/claude-code/issues/38335）表明其在订阅和会话管理方面存在重大问题，影响用户体验，社区关注度极高。
- **OpenAI Codex** 的 [BUG] Burning tokens very fast（https://github.com/openai/codex/issues/14593）和 [BUG] Codex (gpt-5.5, Plus plan) — rate-limit cost per token jumped ~10-20x since June 16, draining the 5h budget in 2-3 prompts（https://github.com/openai/codex/issues/28879）显示其在 token 使用成本和性能方面存在显著问题，引发社区广泛关注。

### 热点讨论

- **Claude Code** 的 [BUG] Phone verification（https://github.com/anthropics/claude-code/issues/34229）和 [BUG] Console scrolling top of history when claude add text to the console（https://github.com/anthropics/claude-code/issues/826）表明其在用户验证和界面交互方面仍需优化。
- **OpenAI Codex** 的 [BUG] Tracking: 429 / Capacity Issues（https://github.com/openai/codex/issues/24937）和 [BUG] GPT-5.5 Codex reasoning-token clustering at 516/1034/1552 may be leading to degraded performance on complex tasks（https://github.com/openai/codex/issues/30364）显示其在模型性能和资源管理方面存在挑战。
- **Gemini CLI** 的 [BUG] Gemini CLI becomes extremely slow (1+ HOURS) / stuck during small code-edit tasks (agent loop + model response delays)（https://github.com/google-gemini/gemini-cli/issues/22141）表明其在处理小代码任务时存在性能瓶颈。
- **GitHub Copilot CLI** 的 [Feature Request] Bring back the GitHub Copilot in the CLI commands to not break workflows（https://github.com/github/copilot-cli/issues/53）和 [BUG] Failed to list models: 403 : unauthorized: not authorized to use this Copilot feature（https://github.com/github/copilot-cli/issues/552）显示其在权限管理和功能集成上仍有待完善。
- **Kimi Code CLI** 的 [PR] refactor: rewrite from Python to Bun + TypeScript + React Ink（https://github.com/MoonshotAI/kimi-cli/pull/1707）和 [PR] fix(utils): bound broadcast queues and cap web store cache to prevent memory leaks（https://github.com/MoonshotAI/kimi-cli/pull/2236）表明其在架构优化和资源管理上有所进展。
- **OpenCode** 的 [BUG] Memory Megathread（https://github.com/anomalyco/opencode/issues/20695）和 [BUG] GPT Models takes too long to respond（https://github.com/anomalyco/opencode/issues/29079）表明其在内存管理和模型响应速度方面存在较大问题。
- **Qwen Code** 的 [PR] feat(review): capture-tui — rendering claims get pixels, not prose (Phase 2)（https://github.com/QwenLM/qwen-code/pull/8388）和 [PR] feat(autofix): require isolated targeted E2E proof（https://github.com/QwenLM/qwen-code/pull/8318）显示其在增强用户体验和功能测试方面有积极进展。
- **DeepSeek TUI** 的 [BUG] v0.9.3: Land and verify security hardening/code-scanning fixes（https://github.com/Hmbown/CodeWhale/issues/3368）和 [BUG] 文案展示不全（https://github.com/Hmbown/CodeWhale/issues/998）表明其在安全性与用户体验方面有持续优化。
- **Claude Code Skills** 的 [Security] Community skills distributed under anthropic/ namespace enable trust boundary abuse（https://github.com/anthropics/skills/issues/492）和 [Feature Request] Enable org-wide skill sharing in Claude.ai（https://github.com/anthropics/skills/issues/228）显示其在安全性和技能共享方面有较高关注度。

### 总结

AI CLI 工具和 Claude Code Skills 项目在 2026 年 8 月表现出活跃的社区互动，尤其是 Claude Code 在订阅和会话管理方面的问题引发广泛关注。Qwen Code 在功能扩展上较为积极，而 OpenCode 和 DeepSeek TUI 面临性能和用户体验的挑战。Claude Code Skills 的安全性和技能扩展问题也引起用户重视，可能影响其生态的稳定性与扩展性。