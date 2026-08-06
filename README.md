# AI 聚合日报 (ai-aggregator-report)

基于 LLM 的多源热点采集与多主题日报生成引擎。每天自动从 **65+** 个数据源并发抓取新闻信号，本地去重幂等，按新闻类型分类生成多份主题日报，统一归档到 `report/YYYY/MM/DD/`，并提供 **Web UI + RSS 订阅 + 飞书推送**。同时内置独立的 **文章生产工作流**，从信号池出发按「选题 → 证据 → 计划 → 草稿 → 审稿 → 门禁 → 修订 → 排版」流水线产出可发布文章。

- 架构蓝本：[dailydawn](https://github.com/TangSY/dailydawn)（异步抓取 → Signal 模型 → 聚合去重 → LLM 管线）
- SKILL参考：[news-aggregator-skill](https://github.com/cclank/news-aggregator-skill/)（多主题日报、统一模板、反幻觉规则）
- 能力参照：[agents-radar](https://github.com/duanyytop/agents-radar)（Web UI / RSS / 飞书推送 / GitHub 生态追踪 / HN 并行查询）

---

## ✨ 核心特性

- **统一数据源层**：65+ 源统一注册、统一 `Signal` 输出，网络脆弱源自动跳过（`safe_fetch`）不影响整体
- **社交源接入**：头条直连公开热榜 API；公众号 / 小红书 / X 走 RSSHub 路由（`RsshubFetcher`）；Twitter 双后端专用 API（TwitterAPI.io + Xquik）——均 fail-open
- **生态追踪**：`cli_tracker` / `agents_tracker` 通过 GitHub API 追踪 AI CLI（Claude Code / Skills 等）与 Agent 生态热议题，生成独立专题报告（不占用主题日报位）
- **可配置 LLM**：OpenAI 兼容协议（OpenAI / DeepSeek / Doubao / OneAPI 等），仅需 3 个环境变量
- **本地去重 + 幂等**：canonical URL 去重、跨源分数叠加、跨日指纹去重（按窗口归档）、报告已存在自动跳过（可 `--force` 重跑）
- **主题分类**：按源白名单规则分配 + LLM 精修，信号可命中多个主题
- **多主题日报**：综合 / 科技 / AI 深度 / 财经 / 吃瓜 / 国际，每个主题独立生成一份日报
- **选题建议**：`article_cli --topics-only` 读取当日日报，LLM 生成下期选题参考，归档为 `topic_suggestions.md`
- **文章生产工作流**：独立入口，产物含 Markdown + 微信兼容 HTML + `.plan.json`（全链路数据），配质量门禁 + 修订循环 + 配图方案（plan-only）
- **用户自定义源**：标准 OPML 2.0 订阅，默认进综合早报，可按关键字映射到任意主题
- **无 key 冒烟**：`--mock-llm` 可在不填 LLM 密钥的情况下跑通整条管线（各阶段走确定性兜底）
- **双调度**：GitHub Actions 每日 cron + 本地 `uv run` 一键运行

---

## 🧱 数据源一览（65+ 个，可按需开关）

| 类别 | 源 key |
|---|---|
| **API/爬虫** | `hackernews` · `github` · `v2ex` · `producthunt` · `huggingface` · `weibo` · `wallstreetcn` · `tencent` · `36kr` · `lobsters` · `devto` · `reddit` · `toutiao` · `dailydawn` |
| **趋势/搜索** | `google_trends`（pytrends） · `hn_ai`（HN 6 个 AI 查询串 → Algolia） |
| **AI/RSS** | `arxiv` · `aihot` · `tldr_ai` · `import_ai` · `bensbites` · `interconnects` · `oneusefulthing` · `kdnuggets` · `aitoroi` · `memia` · `chinai` |
| **中文深度** | `sspai` · `infoq_cn` |
| **国际新闻** | `bbc_top` · `bbc_world` · `bbc_chinese` · `guardian_world` · `aljazeera` · `france24` · `reuters` |
| **AI/公司博客** | `huggingface-blog` · `lilianweng` · `nvidia-blog` · `stability-ai` · `deepmind-blog` · `runway-research` · `the-decoder` · `replicate-blog` |
| **播客/专栏** | `lexfridman` · `80000hours` · `latentspace` · `waitbutwhy` · `jamesclear` · `paulgraham` · `scottyoung` · `dankoe` · `farnamstreet` |
| **聚合源** | `hnrss-best` · `producthunt-feed` · `lobsters-feed` · `r/programming` · `r/MachineLearning` · `r/LocalLLaMA` · `r/StableDiffusion` · `r/midjourney` · `r/comfyui` · `r/singularity` |
| **社交（RSSHub/专用 API）** | `wechat_gzh` · `xiaohongshu` · `twitter_x`（RSSHub 路由） · `twitter`（TwitterAPI.io / Xquik） · `toutiao`（直连热榜） |
| **自定义** | `user`（OPML） |
| **生态追踪** | `cli_tracker` · `agents_tracker`（GitHub API，仅产出专题报告，不参与主题日报） |

> 列表为「可切换」源口径（含默认关闭的开关源）；默认启用约 65 个。任一源失败自动跳过（`safe_fetch`），不影响整条管线。
> 生态追踪依赖 GitHub REST API（匿名 60 次/小时；配 `GITHUB_TOKEN` 提升到 5000 次/小时）。

---

## 🚀 快速开始

```bash
# 1. 安装依赖（推荐 uv）
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 2. 配置 LLM
cp .env.example .env
#   编辑 .env，至少填 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
# 验证 llm 配置
.venv/Scripts/python.exe scripts/llm_check.py "介绍下你自己"

# 3. 跑一次（生成全部主题日报）
.venv/Scripts/python.exe -m aiaggr.main

# 无 key 冒烟（模拟 LLM，验证管线）
.venv/Scripts/python.exe -m aiaggr.main --mock-llm --source hackernews,weibo --topic general,tech
```

成功输出示例：

```
=== AI 聚合日报 · 2026-08-06 ===
→ 并行抓取 65 个数据源 ...
✓ 抓取到 156 条原始信号
✓ 聚合去重后 98 条唯一信号
✓ 主题分类: {'general': 55, 'tech': 40, ...}
✓ [general] 已保存到 report\2026\08\06\general.md
...
→ 完成：6 份主题日报写入 report
→ manifest.json 更新（含选题建议入口） / feed.xml 更新
```

---

## 🖥 日报 CLI（`aiaggr.main`）

| 参数 | 说明 | 默认 |
|---|---|---|
| `--date YYYY-MM-DD` | 报告日期（按配置时区） | 今天 |
| `--topic general,tech` | 只看指定主题 | 全部 |
| `--source hackernews,github` | 数据源 key 逗号分隔；`user` 为 OPML 自定义源 | `all` |
| `--limit N` | 覆盖每个数据源的抓取条数上限 | 各源配置 |
| `--force` | 强制重跑，覆盖已存在日报 | 否 |
| `--collect` | 采集模式：只抓取+去重+规则分类，不调 LLM、不生成日报，输出按主题分组的信号 JSON | 否 |
| `--deep` | 为每条信号抓取正文（截断至 ~3000 字），供 Agent/LLM 写深度洞察 | 否 |
| `--mock-llm` | 模拟 LLM，无需密钥 | 否 |
| `--no-llm` | 跳过 LLM 主题精修（仅规则分类） | 否 |
| `--json` | Agent 友好输出：进度日志进 stderr，stdout 只输出结果 JSON | 否 |
| `--list-sources` | 列出所有数据源 key | — |
| `--config PATH` | 指定 config.yaml | `config.yaml` |

### 🤖 Agent / 脚本直接使用

**两种 Agent 模式**：

- **`--collect --json`（无需 LLM key，可配 `--deep` 补正文）**：CLI 只负责抓取+去重+规则分类，stdout 输出按主题分组的信号 JSON；由 Agent 自己的大模型按 `prompts/report.*.md` 写日报并归档。**推荐给 Agent 使用**。
- **`--json`（需 .env LLM）**：CLI 全自动抓取 → 分类 → 生成 → 落盘。

```bash
# 采集模式：拿信号自己写日报（无需 .env）
.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews,weibo --topic general
```

```jsonc
{
  "exit_code": 0,
  "date": "2026-08-10",
  "mode": "collect",
  "fetched": 90, "unique": 90, "sources": 2,
  "sources_empty": ["v2ex"],
  "signals": 27,
  "topics": {
    "general": [ { "source": "微博热搜", "source_key": "weibo", "title": "...", "url": "...",
                   "heat": "108万", "score": 0.88, "age_bucket": "unknown", /* ... */ } ]
  },
  "tracking": {
    "cli_tracker": [ { "project": "Claude Code", "repo": "anthropics/claude-code",
                       "kind": "issue", "title": "...", "url": "..." } ]
  }
}
```

> `--collect` 的 `tracking` 段包含生态追踪信号（每条带 `project` / `repo` / `kind`），供 Agent 生成 `ai-cli.md` / `ai-agents.md` 专题报告。每条信号含 `content` 字段（配 `--deep` 时为抓取的正文）。

```jsonc
// 自动模式（有 .env LLM 时）
{
  "exit_code": 0, "date": "2026-08-06", "mode": "llm",
  "fetched": 156, "unique": 98, "sources": 65,
  "sources_empty": ["v2ex"],
  "topics": [{ "key": "general", "name": "综合早报", "icon": "🌍",
               "tagline": "综合早报 · 15 条信号",
               "file": "report\\2026\\08\\06\\general.md", "count": 15, "skipped": false }],
  "index": "report\\2026\\08\\06\\index.md",
  "new_fingerprints": 15
}
```

先看 `exit_code`（`0` 成功 / `1` 部分失败 / `2` 配置错误）：`--json` 当天日报已存在会 `skipped: true` 早退，不是失败；`--collect` 不受日报存在性影响。Agent 接入规范详见根目录 [`SKILL.md`](SKILL.md)。

---

## 📝 文章生产工作流（`aiaggr.article_cli`）

独立入口，不依赖日报管线：抓取 → 聚合去重 → `rank → topic → decision → evidence → plan → draft → title → review → gate → revision → cover → render`。产物落到 `article/YYYY/MM/DD/{slug}.md` + `{slug}.html`（微信兼容）+ `{slug}.plan.json`（含 decision / topic / evidence / plan / review / gate / cover 全链路）。

- 入参上限 `article.input_limit`（默认 40，按 score 取前 N）
- **选题参考模式**（`--topics-only`）：读取当日已有日报，逐主题调 LLM 生成选题建议，输出 `report/YYYY/MM/DD/topic_suggestions.md`（Markdown + 与前日 diff），不抓取、不生成文章
- **证据链贯穿**：`topic.clusters[].itemIds → plan.sections[].itemIds → draft`（仅用来源事实）→ `review`（对照来源审 fact）→ `gate`
- 每阶段 LLM 失败/空返回走**确定性兜底**；质量门禁（`gate`）+ 修订循环（`revision`）保证只修安全项、分单调不降才采纳
- 配图（`cover`）本期仅生成封面/正文配图 **prompt 方案**（`mode: plan-only`），不接生图 API

```bash
# 冒烟（mock，无需 key）
.venv/Scripts/python.exe -m aiaggr.article_cli --mock-llm --source toutiao --topic social

# 真实 LLM 生成
.venv/Scripts/python.exe -m aiaggr.article_cli --source hn_ai --topic ai_daily --limit 12

# Agent 模式（JSON stdout）
.venv/Scripts/python.exe -m aiaggr.article_cli --mock-llm --source hackernews --topic general --json

# 选题参考模式（读取日报生成选题建议，不抓取不生成文章）
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only --topic general,tech --mock-llm
```

| 参数 | 说明 |
|---|---|
| `--topic` / `--source` / `--limit` / `--date` | 同日报 CLI：源、主题、抓取条数、日期 |
| `--mock-llm` | 模拟 LLM，各阶段走确定性兜底 |
| `--json` | Agent 友好输出：stdout 只输出结果 JSON |
| `--topics-only` | 选题参考模式（读已有日报 → 生成选题建议，`不抓取/不生成文章`） |

---

## 🎯 主题日报（默认 6 个，可在 config.yaml 增删）

| 主题 | key | 源白名单 | 日报文件 |
|---|---|---|---|
| 🌍 综合早报 | `general` | HN · AIHN(hn_ai) · GitHub · V2EX · PH · 微博 · 36氪 · 腾讯 · user · agentradar ·（综合/文化博客） | `general.md` |
| 🦄 科技早报 | `tech` | HN · hn_ai · GitHub · PH · V2EX · Lobsters · Dev.to · 少数派 · InfoQ ·（开发者/安全博客） | `tech.md` |
| 🧠 AI 深度日报 | `ai_daily` | hn_ai · HF Papers · arXiv · AIHOT · TLDR · Import AI · newsletters · 公司博客 · AI Reddit | `ai_daily.md` |
| 📈 财经早报 | `finance` | 华尔街见闻 · 36氪 · 腾讯 | `finance.md` |
| 🍉 吃瓜早报 | `social` | 微博 · V2EX · 公众号 · 小红书 · 头条 · X（RSSHub）· Twitter专用API | `social.md` |
| 🌐 国际新闻 | `international` | BBC · Guardian · Al Jazeera · France 24 · Reuters | `international.md` |

生态追踪专题报告（`--collect` 不生成，仅 `--json` 自动模式生成）：

| 报告 | 源 | 内容 |
|---|---|---|
| `ai-cli.md` | `cli_tracker` | Claude Code / Claude Code Skills / DeepSeek TUI 等热门 Issue、PR、Release |
| `ai-agents.md` | `agents_tracker` | OpenClaw / Agent 核心库等的热门 Issue、PR、Release |

分类逻辑：**源白名单规则分配**（基础，确定性）+ **LLM classifier 精修**（通用源可命中更垂直主题，失败自动降级为规则结果）。

---

## 📦 输出结构

```
./                      # 项目根
├── report/             # 主题日报（YYYY/MM/DD/）
│   └── YYYY/MM/DD/
│       ├── index.md          # 当日索引（各主题速览 + tagline）
│       ├── general.md · tech.md · ai_daily.md · finance.md · social.md · international.md
│       ├── ai-cli.md        # 生态追踪专题（cli_tracker）
│       ├── ai-agents.md     # 生态追踪专题（agents_tracker）
│       └── topic_suggestions.md   # 选题建议（article_cli --topics-only 生成）
├── article/            # 文章生产工作流产物（YYYY/MM/DD/{type}.md + .html + .plan.json）
├── site/               # 站点交付目录（index.html Web UI + manifest.json + feed.xml）
└── .state/             # 幂等状态（seen.jsonl + taglines.jsonl + arch/），随 git 提交
```

站点交付 `site/`（每次日报后重建，供 Web UI / RSS）：

```
site/index.html     # Web UI（自包含，hash 路由，#date / #date/topic）
site/manifest.json  # Web UI 数据源（日期 → 主题 → 文件），含「选题建议」入口
site/feed.xml       # RSS 2.0（content:encoded 全文，最新 30 条）
```

日报遵循统一模板（news-aggregator-skill）：

```markdown
#### 1. [标题](url)
- **来源**: 源名 | **时间**: 时间 | **热度**: 热度
- **链接**: [讨论](hn_url) | [GitHub](gh_url)
- **摘要**: 一句话。
- **深度洞察**: 💡 背景 / 影响 / 价值。
```

---

## 🔑 配置

### LLM（`.env`，OpenAI 兼容协议）

```bash
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
# AGGR_MOCK_LLM=1   # 或 --mock-llm
```

### 推送 / 站点 / 生态 / 社交 / 文章（`.env`）

```bash
# 飞书机器人 webhook（多个用逗号分隔；兼容旧 FEISHU_WEBHOOK_URL）
FEISHU_WEBHOOK_URLS=
# GitHub Token：生态追踪提限流；也可用于 daily-report.yml 内的 PR/发布等操作
GITHUB_TOKEN=
# GitHub Pages 站点地址（manifest/feed/web UI 内链接的 base_url）
PAGES_URL=
# RSSHub 实例地址（公众号/小红书/X 路由用，默认 https://rsshub.app）
RSSHUB_BASE_URL=
# Twitter/X 专用 API（二选一或都配，配其一才启用）
TWITTER_API_KEY=     # TwitterAPI.io 的 X-API-Key
XQUIK_API_KEY=       # Xquik 的 x-api-key
# 证据补全正文抓取（article 工作流，走 Jina Reader 认证）
JINA_API_KEY=
```

### `config.yaml`

- `llm`：模型、超时、温度、mock、并发
- `timezone`：日报按本地日期归属（默认 `Asia/Shanghai`）
- `dedup`：跨日去重窗口（默认 7 天）、是否排除、是否忽略跟踪参数
- `topics`：主题定义（`sources` 白名单 / `limit` / `prompt` 文件）
- `sources`：数据源注册表（`type: api|rss|trends|opml|tracking|rsshub` + 开关参数）
- `rsshub`：社交源路由（`{name, path, hours, enabled}`，`base` 取 env 或 `https://rsshub.app`；公众号/小红书部分需自建实例 + token，失败 fail-open）
- `opml`：自定义源 OPML 路径（`paths`）/ 默认主题 / `topic_map` 关键字映射
- `site`：站点交付（`base_url` 供 manifest/feed/web UI 引用）
- `tracking`：生态追踪仓库列表（默认内置 AI CLI / Agent 生态仓库）
- `article`：文章工作流（`dry_run` / `input_limit` / `profiles` / `quality_gate` / `evidence` / `output.dir`）

### 用户自定义订阅源（User OPML）

把常看的 RSS/Atom 写进 OPML，`--source user` 即可统一抓取：

```xml
<outline type="rss" text="Simon Willison" title="Simon Willison"
         xmlUrl="https://simonwillison.net/atom/everything/" />
```

OPML 查找路径与关键字映射见 `config.yaml` 的 `opml` 段（`paths` + `topic_map`，默认映射 `ai/llm/openai/anthropic → ai_daily`），引用样式见 `user_sources.opml.example`。

---

## ⚙️ 去重与幂等

| 机制 | 说明 |
|---|---|
| **同日去重** | canonical URL（去 utm/fbclid 等跟踪参数）去重；跨源同 URL 分数叠加 |
| **跨日去重** | `.state/seen.jsonl` 记录每日已产出信号指纹，7 天窗口内重复信号不再进当日日报；超过窗口自动归档到 `.state/arch/YYYYMM-seen.jsonl` |
| **报告幂等** | `report/YYYY/MM/DD/{topic}.md` 已存在则跳过 LLM 调用（省成本）；`--force` 强制重跑 |
| **选题锚** | `.state/taglines.jsonl` 记录每日各主题 tagline，作为次日避免主题重复的锚 |

`.state/` 会随 git 提交，保证 GitHub Actions 连续运行时跨日去重持续生效。

---

## 🤖 GitHub Actions

- `daily-report.yml`：每日 UTC 22:00（北京时间 06:00）定时 `python -u -m aiaggr.main --force` + 手动 `workflow_dispatch`；提交 `report/` `.state/` `site/`，并在有变更时显式触发 `pages.yml` 部署（`GITHUB_TOKEN` 的 push 不连锁触发 `on: push`）。
- `pages.yml`（Deploy GitHub Pages）：由 `daily-report.yml` 显式触发 + `on: push` 到 `main` 自动发布；打包 `site/*` 与 `report/` 到 GitHub Pages，提供在线 Web UI 与 RSS。

---

## 🧩 如何扩展

### 新增数据源

1. 纯 RSS 源：在 `config.yaml` 的 `sources.rss` 加一条 `{name, url, hours, enabled}` 即可（无需写代码）。
2. 自定义 API 源：在 `aiaggr/fetchers/` 新建 `mydata.py`，继承 `BaseFetcher` 实现 `async fetch()` 返回 `Signal` 列表，再在 `fetchers/__init__.py` 的 `_API_CLASSES` 注册。
3. 社交类（无公开 API 平台）：公众号/小红书/X 走 `sources.rsshub` 路由，或新建专用 API 抓取器（如 `twitter.py` / `toutiao.py`）+ 注册 `.fn.env.example` 变量。
4. 需要 API key 时在 `.env.example` 与 workflow env 补变量。
5. `--source mydata` 验证（改完跑一次 `python -m compileall -q aiaggr`）。

### 新增专题 / 选题建议

- 在 `config.yaml` 的 `topics` 加一项（`sources` 白名单 + `prompt` 文件），并新建 `prompts/report.{topic}.md`（严格输出 `{"tagline","markdown"}`）。
- 新增「生态追踪专题」在 `tracking` 段加仓库即可。

---

## 📁 项目结构

```
ai-aggregator-report/
├── aiaggr/                  # 核心包
│   ├── main.py              # CLI 入口：热门记录（幂等 → 抓取 → 聚合 → 分发 → 分类 → 生成 → 落盘 → 选题 → 站点 → 飞书）
│   ├── article_cli.py       # 文章生产工作流独立入口（含 --topics-only 选题参考）
│   ├── config.py            # config.yaml + .env 加载
│   ├── dedup.py             # 去重幂等核心（canonical URL + fingerprint + aggregate）
│   ├── state.py             # StateStore：seen.jsonl / taglines.jsonl / arch 归档
│   ├── llm.py               # OpenAI 兼容客户端（json 降级 + 重试 + mock）
│   ├── classifier.py        # 主题分类（规则分配 + LLM 精修）
│   ├── pipeline.py          # 主题日报生成管线（拼 prompt → call_json → 兜底）
│   ├── topics.py            # 选题建议生成器（generate_topic_suggestions + diff）
│   ├── renderer.py          # markdown 落盘 + index + date_path
│   ├── notify.py            # 飞书推送（interactive 卡片，无 webhook 静默跳过）
│   ├── site.py              # 站点交付（manifest.json 含选题入口 + feed.xml RSS）
│   ├── tracking.py          # 生态追踪专题报告生成器（ai-cli / ai-agents）
│   ├── deep.py              # --deep 正文抓取（enrich_with_content）
│   ├── article/             # 文章生产工作流模块（rank/topic/decision/evidence/plan/draft/title/review/gate/revision/cover/render/workflow）
│   └── fetchers/            # 统一数据源层
│       ├── base.py          # Signal 数据模型 + BaseFetcher + safe_fetch + normalize_score
│       ├── __init__.py      # _API_CLASSES 注册表 + build_fetchers + select_fetchers
│       ├── rss.py / rsshub.py / twitter.py / toutiao.py / user_opml.py / hn_ai.py / github_tracker.py
│       └── (专用源…)
├── prompts/                 # LLM 提示词（classifier / report.* / article.* / article_topics / tracking.*）
├── scripts/llm_check.py     # LLM 配置连通性自检
├── config.yaml              # 主配置
├── requirements.txt
├── .env.example
├── user_sources.opml.example
├── SKILL.md                 # Agent 接入规范
├── report/                   # 日报输出（YYYY/MM/DD/）
├── article/                  # 文章工作流产物（YYYY/MM/DD/）
├── site/                     # 站点交付目录（index.html / manifest.json / feed.xml）
└── .state/                   # 幂等状态（seen.jsonl + taglines.jsonl + arch/）
```

---

## 依赖

`httpx · feedparser · beautifulsoup4 · lxml · python-dotenv · openai · tenacity · PyYAML · tzdata · pytrends · markdown`（`praw` 可选，Reddit 默认走公开 JSON）。

> Web UI 在无 `markdown` 依赖时也会用内置轻量渲染器兜底，但 `requirements.txt` 已含 `markdown>=3.6`。

## License

MIT