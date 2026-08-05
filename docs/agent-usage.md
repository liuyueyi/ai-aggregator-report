# 使用 AI Agent 进行热点采集

本项目专为 **AI Agent 协作**而设计：Agent（如 OpenCode / Claude Code / Codex / Codebuddy / OpenClaw 等）可作为「副驾驶」直接调用本项目抓取热点信号，再由 Agent 自己的大模型按模板写日报。**全程无需配置任何 LLM key**。

## 核心思路

Agent 与本项目之间只有一个约定：**stdout 输出结构化 JSON，进度日志走 stderr**。

- 项目负责：并发抓取 40+ 源 → 本地去重幂等 → 规则分类 → 输出按主题分组的信号 JSON（确定性、无 LLM）
- Agent 负责：拿到 JSON → 按 `prompts/report.*.md` 模板写日报 → 归档到 `report/YYYY/MM/DD/`

## 推荐的 Agent 采集命令（方式 A：无需 LLM key）

```bash
.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews,github,weibo --topic general,tech
```

也可以全源、全主题采集：

```bash
.venv/Scripts/python.exe -m aiaggr.main --collect --json
```

stdout 返回 JSON 的结构（关键字段）：

```jsonc
{
  "exit_code": 0,              // 0 成功 / 1 部分失败 / 2 配置错误
  "date": "2026-08-10",
  "mode": "collect",
  "fetched": 90, "unique": 90, "sources": 2,
  "sources_empty": ["v2ex"],   // 单源失败不影响结果
  "topics": {                  // 主题 key → 信号数组（已按 score 排序、截取 limit 条）
    "general": [
      {
        "source": "微博热搜", "source_key": "weibo",
        "title": "标题", "url": "https://...",
        "heat": "108万",                 // 原始热度文本，原样使用
        "score": 0.88, "raw_score": 877975,
        "comments": 0, "author": "",
        "summary": "一句话摘要", "tags": [],
        "published_at": null,            // 无逐条时间则为 null
        "age_bucket": "unknown",         // today / past_72h / older / unknown
        "hn_url": null, "gh_url": null,
        "also_on": []
      }
    ],
    "tech": []
  },
  "tracking": {                // 生态追踪信号（专供 ai-cli.md / ai-agents.md 专题报告）
    "cli_tracker":   [ /* project / repo / kind / title / url ... */ ],
    "agents_tracker": []
  }
}
```

> 生态追踪：若要生成「AI CLI 生态」或「AI Agent 生态」专题，从 `tracking` 段取信号，按 `prompts/tracking.cli.md` / `prompts/tracking.agents.md` 模板写 `ai-cli.md` / `ai-agents.md`。

## 按 Agent 接入示例

### OpenCode（本项目所在环境）

OpenCode 可直接读取根目录 `SKILL.md`（skill 定义）与 `AGENTS.md`（开发指引），把整个仓库挂进会话：

1. 让 OpenCode 加载 `SKILL.md` 描述的 skill。
2. 会话中自然语言提问即可，例如：「帮我生成今日 AI 日报」。
3. OpenCode 会自动执行上面的 `--collect --json` 命令，读取 JSON 信号，按模板写日报并归档到 `report/YYYY/MM/DD/`。

### Claude Code / Codex / Codebuddy 等通用 Coding Agent

这些 Agent 都能直接执行 shell 命令并读写文件，接入方式相同：

1. 给 Agent 一段指令（或写入项目 `AGENTS.md` / 自定义 instruction）：

   ```
   采集命令：.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews,github --topic general
   然后按 prompts/report.general.md 的模板写日报，保存到 report/2026/08/05/general.md
   ```

2. Agent 自己运行命令 → 解析 stdout JSON → 写日报 → 归档。

### OpenClaw 等通用 AI Agent 平台

OpenClaw 通过工具/插件形式接入：为其配置一个「执行 shell 命令」的工具，指向本项目的 `--collect --json` 命令即可。同样的 JSON 输出协议使其可以无侵入接入。

## 各 Agent 模式速查

| 场景 | 命令 | 是否需 .env LLM |
|---|---|---|
| Agent 采集信号、自己写日报（**推荐**） | `--collect --json` | 否 |
| 自动全流程（CLI 抓取+生成+落盘） | `--json` | 是 |
| 冒烟验证管线（无 key） | `--mock-llm --source hackernews --topic general` | 否 |

## 写日报的守则（Agent 必须遵守）

1. **只用 JSON 里的信号**：绝不虚构新闻、不补造时间/热度。
2. **时间表述基于 `age_bucket`**：`today`→「今日」，`past_72h`→「近 3 天」，`older`→「多日前」，`unknown`→「时间未知」。不编具体日期。
3. **热度原文引用**：微博 `heat` 如「108万」原样使用，不换算。
4. **语言**：日报为简体中文，保留英文专有名词（ChatGPT、Python 等）。
5. **归档**：保存到 `report/YYYY/MM/DD/{topic}.md`，并生成/更新当日 `index.md`。

## 常见问题

- **没有 `.venv` 怎么办**：先 `uv venv .venv && uv pip install --python .venv/Scripts/python.exe -r requirements.txt`（Linux/macOS 路径为 `.venv/bin/python`）。
- **Windows 落盘 JSON 变 UTF-16**：PowerShell `1>` 会转 UTF-16，用 `cmd /c ".venv\Scripts\python.exe -m aiaggr.main --collect --json > out.json"`。
- **想要今天全部热点但不想分主题**：`--collect --json --topic general`（综合主题白名单最广）。
- **自备 LLM key 想全自动**：配好 `.env` 后直接 `--json`，CLI 一条龙完成（见 [cli-usage.md](./cli-usage.md)）。
