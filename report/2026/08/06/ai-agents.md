# AI Agent 生态专题日报
## 2026-08-06

## 生态全景

## 活跃度对比表
| 项目 | PR 数 | Issue 数 | 热议点 |
| --- | --- | --- | --- |
| OpenClaw | 6 | 0 | fix(slack), perf: avoid event-loop stall during embedded_run bootstrap-context, feat: add lease-bound metadata to session spawns, fix(tts): defer text settlement for final-mode TTS to eliminate churn (#83511), fix(wechat): preserve existing accounts across hot reload |
| NanoBot | 5 | 1 | feat(observability): OpenTelemetry tracing for LLM calls and tools, Architectural issue: nanobot does not preserve the exact prompt prefix it previously sent, Endpoint channel, feat(llm-wiki): enhance llm-wiki functionality with auto-archiving and management commands, feat(tools): add read-only search_history tool |
| PicoClaw | 3 | 3 | chore: move installation scripts from docs repo to here, Feature: Intelligent Model Routing for Cost & Performance Optimization, Added simplex channel type |
| ZeroClaw | 5 | 0 | feat(gateway): add OpenAI chat completions endpoint, feat(matrix): add single-message progress drafts, fix(tools): add allowed_private_hosts opt-in to file_download SSRF gate, feat(channels/telegram): add multi_message streaming mode, fix(channels): cap Telegram bot commands and repair truncation WARN for #8950 |
| Hermes Agent | 5 | 0 | feat(discord): add conservative voice barge-in, feat(gateway): make still-working heartbeats configurable, feat(gateway): add Zulip integration and messaging support, feat(session_context): add set/reset_current_turn_session_key public wrappers, Handle WhatsApp Cloud calls with a sidecar |
| CoPaw | 5 | 0 | feat(channels): add WhatsApp channel via neonize-qwenpaw, fix(agents): sanitize local paths in formatter normalization, feat(nextcloud_talk): add Nextcloud Talk channel integration, Add French (fr-CA) language support, Feat/semantic skill routing |

## 共同技术方向

## 差异化定位

## 社区热度与成熟度

## 趋势信号

## OpenClaw
速览：OpenClaw社区近期活跃，多个PR和Release更新，重点关注性能优化和功能增强。
版本发布：OpenClaw发布v2026.7.1-2至v2026.7.2-beta.7版本。
社区热点：PR #102082 fix(slack): suppress progress chrome sends 引起574次评论，是社区热议的话题。

## NanoBot
速览：NanoBot社区持续发展，新增功能丰富，社区活跃度较高。
版本发布：NanoBot发布v0.3.0至v0.2.1版本。
社区热点：PR #3173 feat(observability): OpenTelemetry tracing for LLM calls and tools 引起10次评论。

## PicoClaw
速览：PicoClaw社区在功能优化和性能提升方面有所进展。
版本发布：PicoClaw发布nightly至v0.2.9版本。
社区热点：Issue #295 Feature: Intelligent Model Routing for Cost & Performance Optimization 引起10次评论。

## ZeroClaw
速览：ZeroClaw社区在功能增强和性能优化方面持续努力。
版本发布：ZeroClaw发布v0.8.4至v0.8.2版本。
社区热点：PR #8486 feat(gateway): add OpenAI chat completions endpoint 引起30次评论。

## Hermes Agent
速览：Hermes Agent社区在功能扩展和性能优化方面取得进展。
版本发布：Hermes Agent发布v2026.8.3至v2026.7.20版本。
社区热点：PR #75325 feat(discord): add conservative voice barge-in 引起592次评论。

## CoPaw
速览：CoPaw社区在功能扩展和语言支持方面有所增强。
版本发布：CoPaw发布v2.1.0-beta.1至v2.0.1版本。
社区热点：PR #3498 feat(channels): add WhatsApp channel via neonize-qwenpaw 引起10次评论。