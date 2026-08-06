---
name: ai-aggregator-report
description: "多源热点采集与多主题日报生成引擎。从 40+ 数据源（Hacker News、GitHub、微博、华尔街见闻、AI 精选、国际新闻、用户 OPML 等）并发抓取，本地去重幂等，按主题分组输出信号，另含 AI CLI / Agent 生态追踪专题。当用户要求『今日早报』『AI 日报』『科技新闻』『财经早餐』『吃瓜』『国际新闻』『AI CLI』『AI Agent 生态』『聚合日报』或查询事件热度时使用。**无需额外 LLM key**：用 --collect 采集信号后由 Agent 自己写日报（也可用 --json 让 CLI 自动生成）。"
---

# AI 聚合日报 (ai-aggregator-report)

多源热点采集 + 多主题日报引擎。执行一次按 6 个主题（综合 / 科技 / AI 深度 / 财经 / 吃瓜 / 国际）输出信号，统一归档到 `report/YYYY/MM/DD/`。

**两种运行方式**：

| 方式 | 是否需 .env LLM | 适用 |
|---|---|---|
| **`--collect`（推荐给 Agent）** | ❌ 不需要 | 由 Agent 自己的大模型按 `prompts/` 写日报 |
| **`--json`** | ✅ 需要 | CI / 本地全自动生成日报 |

CLI 进度日志一律走 stderr；stdout 只输出结构化 JSON，适合 AI Agent / 脚本消费。

---

## 🔄 工作流

**每次日报请求都走同一流程**：采集信号 → 写日报 → 保存归档 → 选题建议 → 展示。

### 方式 A：采集模式（无需 LLM，推荐）

1. 采集信号（规则分类，纯确定性，不调用任何 LLM）：

```bash
.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews,github,weibo --topic general,tech
```

2. stdout 返回按主题分组的信号 JSON（字段见下），**你自己就是 LLM**：
3. 按 `prompts/report.{topic}.md` 的模板与风格写每份日报（简体中文、反幻觉）。
4. 保存到 `report/YYYY/MM/DD/{topic}.md`，并写当日 `index.md`（各主题速览 + tagline）。

### 方式 B：自动模式（配 .env 的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）

```bash
# 全部主题（43+ 源）
.venv/Scripts/python.exe -m aiaggr.main --json

# 只看部分主题 / 源
.venv/Scripts/python.exe -m aiaggr.main --json --topic general,tech --source hackernews,github

# 指定日期
.venv/Scripts/python.exe -m aiaggr.main --json --date 2026-08-05

# 无 key 冒烟（验证管线）
.venv/Scripts/python.exe -m aiaggr.main --json --mock-llm --source hackernews --topic general
```

### 方式 C：选题参考模式（读取已有日报，生成选题建议）

不抓取、不生成日报，仅读取 `report/YYYY/MM/DD/` 下已有的日报，逐主题调 LLM 生成选题建议，输出 Markdown 文档 + 与前日差异对比。

```bash
# 所有主题
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only

# 指定主题
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only --topic general,tech

# mock 冒烟
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only --mock-llm --topic general
```

输出 `report/YYYY/MM/DD/topic_suggestions.md`（Markdown 文档，含前日 diff + 每条选题的「为什么值得写」）。

> **自动触发**：方式 B 生成日报后会自动附带生成选题建议（无需额外参数）。首次运行无前日数据时跳过差异对比。

---

## 📦 采集模式 JSON（方式 A 的 stdout）

```jsonc
{
  "exit_code": 0,
  "date": "2026-08-10",
  "mode": "collect",
  "fetched": 90,            // 原始信号数
  "unique": 90,             // 去重后唯一信号数
  "sources": 2,
  "sources_empty": ["v2ex"],// 返回空/失败的源 key
  "new_fingerprints": 27,   // 本次记录的跨日去重指纹
  "signals": 27,            // 分组后的信号总数
  "topics": {               // 主题 key → 信号数组（已按 score 排序、截取 limit 条）
    "general": [
      {
        "source": "微博热搜", "source_key": "weibo",
        "title": "标题", "url": "https://...",
        "heat": "108万",              // 原始热度文本原样保留
        "score": 0.88, "raw_score": 877975,
        "comments": 0, "author": "",
        "summary": "一句话摘要", "tags": [],
        "published_at": null,          // 无逐条时间则为 null
        "age_bucket": "unknown",       // today / past_72h / older / unknown
        "hn_url": null, "gh_url": null,
        "also_on": []
      }
    ],
    "tech": []
  },
  "tracking": {                 // 生态追踪信号（不参与主题日报，专供专题报告）
    "cli_tracker": [
      {
        "project": "Claude Code", "repo": "anthropics/claude-code",
        "kind": "issue",        // issue / pr / release
        "source": "Claude Code", "title": "标题", "url": "https://github.com/...",
        "comments": 1484, "heat": "1484 评论",
        "score": 0.91, "raw_score": 1484,
        "published_at": "2026-03-23T...Z",
        "gh_url": "https://github.com/anthropics/claude-code/issues/38335"
      }
    ],
    "agents_tracker": []
  }
}
```

先看 `exit_code`：`0` 成功 / `1` 部分失败 / `2` 配置错误。`sources_empty` 非空时单源失败不影响结果（V2EX / Google Trends 偶发超时属正常）。

---

## 🔭 生态追踪专题报告（可选）

当用户要求「AI CLI」「Claude Code」「Skills」「Agent 生态」「OpenClaw」等时，除主题日报外还生成**专题报告**（不占用主题日报位）：

1. 从 JSON 的 `tracking` 段取信号（`cli_tracker` / `agents_tracker`，每条带 `project` / `repo` / `kind`）。
2. 按 `prompts/tracking.cli.md` / `prompts/tracking.agents.md` 的模板写专题报告。
3. 归档为 `report/YYYY/MM/DD/ai-cli.md` 与 `report/YYYY/MM/DD/ai-agents.md`，并计入当日 `index.md`。

> `--collect` 每次默认追踪内置仓库列表（`config.yaml` 的 `tracking` 段可增删）。不想要追踪信号可 `--source` 显式排除。

---

## ✍️ 写日报（Agent 在方式 A 中的职责）

1. **模板**：读 `prompts/report.{topic}.md`，遵循其中的结构、占位符语义与文风。
2. **只使用 JSON 里的信号**：绝不虚构新闻、不补造时间/热度。
3. **时间表述**：依据 `age_bucket`（today →「今日」，past_72h →「近 3 天」，older →「多日前」，unknown →「时间未知」），不要编具体日期。
4. **反幻觉**：标题/摘要/热度原样引用；多源重复可在正文合并观点，但保留各自链接。
5. **归档**：保存到 `report/YYYY/MM/DD/{topic}.md`，并生成/更新当日 `index.md`（含各主题 tagline 速览）。
6. **幂等**：当天已有 `{topic}.md` 时覆盖前先确认（通常由用户决定重跑）；`--collect` 不会因"日报已存在"而中断。

---

## 🖥 CLI 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--date YYYY-MM-DD` | 报告日期（按配置时区） | 今天 |
| `--topic general,tech` | 只看指定主题（逗号分隔） | 全部 |
| `--source hackernews,github` | 数据源 key（逗号分隔）；`user` 为 OPML 自定义源 | `all` |
| `--limit N` | 覆盖每个数据源的抓取条数上限 | 各源配置 |
| `--collect` | 采集模式：只抓取+去重+规则分类，不调 LLM、不生成日报，输出信号 JSON | 否 |
| `--force` | 强制重跑，覆盖已存在日报 | 否 |
| `--mock-llm` | 模拟 LLM，无需密钥（验证管线） | 否 |
| `--no-llm` | 跳过 LLM 主题精修（仅规则分类） | 否 |
| `--json` | 进度进 stderr，stdout 只输出结果 JSON | 否 |
| `--list-sources` | 列出所有数据源 key | — |
| `--config PATH` | 指定 config.yaml | `config.yaml` |

> **article_cli.py 专用参数**（`python -m aiaggr.article_cli`）：

| 参数 | 说明 | 默认 |
|---|---|---|
| `--topics-only` | 选题参考模式：读取已有日报 → LLM 选题 → Markdown + diff | 否 |

> Windows 上把 stdout 落盘且保持 UTF-8 用 `cmd /c "... > out.json"`；PowerShell 的 `1>` 会转成 UTF-16。

---

## 🎯 主题（config.yaml 可增删）

| 主题 | key | 日报文件 |
|---|---|---|
| 🌍 综合早报 | `general` | `general.md` |
| 🦄 科技早报 | `tech` | `tech.md` |
| 🧠 AI 深度日报 | `ai_daily` | `ai_daily.md` |
| 📈 财经早报 | `finance` | `finance.md` |
| 🍉 吃瓜早报 | `social` | `social.md` |
| 🌐 国际新闻 | `international` | `international.md` |

**生态追踪专题**（不占主题日报位，仅按需生成）：

| 专题 | 源 | 日报文件 |
|---|---|---|
| AI CLI 生态 | `cli_tracker` | `ai-cli.md` |
| AI Agent 生态 | `agents_tracker` | `ai-agents.md` |

`--list-sources` 输出全部可用的源 key（`hackernews` · `github` · `v2ex` · `producthunt` · `huggingface` · `weibo` · `wallstreetcn` · `tencent` · `36kr` · `lobsters` · `devto` · `reddit` · `google_trends` · `hn_ai` · 各 RSS 源 · `user` · `cli_tracker` · `agents_tracker`）。

---

## 📦 输出归档

```
report/
└── YYYY/MM/DD/
    ├── index.md                  # 当日索引（各主题速览 + tagline）
    ├── general.md
    ├── tech.md
    ├── ...                       # 每主题一份
    └── topic_suggestions.md      # 选题建议（Markdown，含前日 diff + 为什么值得写）
```

---

## ⚠️ 规则（Strict）

1. **输出语言**：日报为**简体中文**；保留常见英文专有名词（ChatGPT、Python 等）。
2. **时间**：必须基于 `age_bucket` 表述；`unknown` 写「时间未知」，不编造。
3. **反幻觉**：只使用 JSON 中的信号，绝不虚构新闻/热度/时间。
4. **热度原文**：微博 `heat`（如「108万」）原样使用，不换算。
5. **跨日去重**：`.state/seen.jsonl` 已自动处理，当日重复信号不会出现在 JSON 里，无需干预。
6. **幂等**：`--collect` 不会因当日日报已存在而中断；`--json` 当日日报已存在时 `exit_code 0 + skipped: true` 早退，不是失败。

---

## 前置要求

- `.venv` 已按 README 创建并安装依赖。
- **方式 A（--collect）**：无需任何 LLM key，开箱即用。
- **方式 B（--json）**：需 `.env` 配 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`。