## AI CLI / Claude Code Skills 生态专题日报 - 2026-08-07

### 生态全景

| 项目 | PR 数 | Issue 数 | 热议点 | 
|------|-------|----------|--------| 
| Claude Code | 0 | 4 | [BUG] Instantly hitting usage limits with Max subscription, [BUG] Claude Max plan session limits exhausted abnormally fast since March 23, 2026 (CLI usage), [BUG] Phone verification, [BUG] Console scrolling top of history when claude add text to the console | 
| OpenAI Codex | 0 | 4 | Burning tokens very fast, Codex (gpt-5.5, Plus plan) — rate-limit cost per token jumped ~10-20x since June 16, draining the 5h budget in 2-3 prompts, Gemini CLI becomes extremely slow (1+ HOURS) / stuck during small code-edit tasks (agent loop + model response delays), Support 1M token context for GPT-5.5 in Codex | 
| GitHub Copilot CLI | 0 | 4 | Bring back the GitHub Copilot in the CLI commands to not break workflows, "Copilot Requests" permission for fine-grained tokens should be visible for org-owned tokens, Failed to list models: 403 : unauthorized: not authorized to use this Copilot feature, Sporadic policy blocking issue retrieving models | 
| Kimi Code CLI | 4 | 0 | refactor: rewrite from Python to Bun + TypeScript + React Ink, fix(utils): bound broadcast queues and cap web store cache to prevent memory leaks, fix(aiohttp): reuse TCPConnector to prevent connection leaks, feat: add thermodynamic regime management (T* framework) | 
| OpenCode | 0 | 5 | Memory Megathread, GPT Models takes too long to respond, Copy To Clipboard is not working, Is there a way to sandbox the agent ?, always stuck at “Preparing write...” | 
| Qwen Code | 4 | 0 | feat(review): capture-tui — rendering claims get pixels, not prose (Phase 2), feat(autofix): require isolated targeted E2E proof, feat(cli): add audio bridge for attachments, feat(review): Add Maven multi-module verification, feat(channels): add Feishu ask-user question cards | 
| DeepSeek TUI | 0 | 5 | v0.9.3: Land and verify security hardening/code-scanning fixes, Put it up for agentclientprotocol/registry, feat: sidebar sessions panel with auto-resume and session history browsing, v0.9.3: Fleet model classes, loadout auto, and semantic route roles, 文案展示不全 | 
| Claude Code Skills | 2 | 3 | Security: Community skills distributed under anthropic/ namespace enable trust boundary abuse, run_eval.py: claude -p never triggers skills/commands (0% trigger rate across all queries), Enable org-wide skill sharing in Claude.ai, Add markdown-to-image skill: Markdown → PNG image cards, Add webpilot skill — CDP-free browser automation |

### 差异定位

- **Claude Code** 在 Issues 上有较多的活跃讨论，主要集中在使用限制、性能问题和验证流程上。
- **OpenAI Codex** 的 Issues 活跃度较高，涉及性能和功能需求，如 token 消耗过快和对 GPT-5.5 的支持。
- **Kimi Code CLI** 在 PR 数上领先，主要集中在技术重构和性能优化。
- **Qwen Code** 的 PR 数也较高，重点在于功能扩展和用户体验改进。
- **DeepSeek TUI** 的 Issues 活跃度较高，集中在安全性和功能增强。
- **Claude Code Skills** 的 Issues 和 PR 数都相对较少，但存在关于技能安全性和功能扩展的讨论。

### 趋势信号

- **Claude Code** 和 **OpenAI Codex** 的 Issues 数量较多，反映出用户对性能和资源管理的关注。
- **Kimi Code CLI** 和 **Qwen Code** 的 PR 数较高，表明社区在技术优化和功能增强方面有积极的贡献。
- **DeepSeek TUI** 的 Issues 数量较多，可能表明其在安全性和功能扩展方面有较多的社区反馈。
- **Claude Code Skills** 的 PR 数相对较少，但存在关于技能安全性和扩展性的讨论，反映出该生态在功能完善和安全机制方面有持续的关注。

### 高热度信号点评

- **Claude Code** 的 [BUG] Instantly hitting usage limits with Max subscription (1486 评论)：用户反馈在 Max 计划下迅速达到使用限制，这可能影响用户体验和生产力，需要优先解决。
- **OpenAI Codex** 的 Burning tokens very fast (628 评论)：用户指出 token 消耗速度过快，这可能导致预算快速耗尽，需优化模型效率或调整计费策略。
- **Kimi Code CLI** 的 refactor: rewrite from Python to Bun + TypeScript + React Ink (12 评论)：技术重构可能带来性能提升或更灵活的架构，但需关注社区对新架构的接受度。
- **Qwen Code** 的 feat(cli): add audio bridge for attachments (56 评论)：新增音频桥接功能可能提升用户体验，但需确保其稳定性和易用性。
- **Claude Code Skills** 的 Security: Community skills distributed under anthropic/ namespace enable trust boundary abuse (43 评论)：技能安全问题引发社区关注，需加强信任边界控制以防止潜在风险。

### 速览

- **Claude Code** 的用户反馈集中在使用限制和性能问题上，需重点关注其资源管理和用户界面优化。
- **OpenAI Codex** 的用户主要关注 token 消耗速度和功能扩展，如支持 1M token 上下文。
- **Kimi Code CLI** 的 PR 主要涉及架构优化和性能改进，显示其技术发展迅速。
- **Qwen Code** 的 PR 聚焦于功能增强和用户体验提升，如音频桥接和 Maven 多模块验证。
- **DeepSeek TUI** 的 Issues 多围绕安全性和界面功能，显示其在安全性和用户体验上的持续改进。
- **Claude Code Skills** 的 PR 和 Issues 主要涉及技能安全性和扩展性，显示其在技能生态上的探索和优化。

### 热点讨论

- **Claude Code** 的 [BUG] Instantly hitting usage limits with Max subscription 有大量用户关注，可能影响其在高负载场景下的可用性。
- **OpenAI Codex** 的 Burning tokens very fast 引发用户对资源管理策略的讨论，可能影响其在复杂任务中的表现。
- **Kimi Code CLI** 的 refactor: rewrite from Python to Bun + TypeScript + React Ink 引起部分用户对技术栈变更的讨论，需评估其对现有用户的影响。
- **Qwen Code** 的 feat(cli): add audio bridge for attachments 引起用户对新功能的兴趣，可能提升其在多媒体处理方面的竞争力。
- **Claude Code Skills** 的 Security: Community skills distributed under anthropic/ namespace enable trust boundary abuse 引发对技能安全性的关注，需加强社区审核机制。

### 引用链接

- [Claude Code - Instantly hitting usage limits with Max subscription](https://github.com/anthropics/claude-code/issues/16157)
- [OpenAI Codex - Burning tokens very fast](https://github.com/openai/codex/issues/14593)
- [Kimi Code CLI - refactor: rewrite from Python to Bun + TypeScript + React Ink](https://github.com/MoonshotAI/kimi-cli/pull/1707)
- [Qwen Code - feat(cli): add audio bridge for attachments](https://github.com/QwenLM/qwen-code/pull/8332)
- [Claude Code Skills - Security: Community skills distributed under anthropic/ namespace enable trust boundary abuse](https://github.com/anthropics/skills/issues/492)