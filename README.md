# AI 聚合日报 (ai-aggregator-report)

基于 LLM 的多源热点采集与多主题日报生成引擎。每天自动从 40+ 个数据源并发抓取新闻信号，本地去重幂等，按新闻类型分类生成多份主题日报，统一归档到 `report/YYYY/MM/DD/`，并提供 **Web UI + RSS 订阅 + 飞书推送**。

- 架构蓝本：[dailydawn](https://github.com/TangSY/dailydawn)（异步抓取 → Signal 模型 → 聚合去重 → LLM 管线）
- SKILL参考：[news-aggregator-skill](https://github.com/cclank/news-aggregator-skill/)（多主题日报、统一模板、反幻觉规则）
- 能力参照：[agents-radar](https://github.com/duanyytop/agents-radar)（Web UI / RSS / 飞书推送 / GitHub 生态追踪 / HN 并行查询）

---

## ✨ 核心特性

- **统一数据源层**：合并 dailydawn 与 news-aggregator-skill 两套数据源，40+ 源统一注册、统一 `Signal` 输出
- **生态追踪**：`cli_tracker` / `agents_tracker` 通过 GitHub API 追踪 AI CLI（Claude Code / Skills / DeepSeek TUI 等）与 Agent 生态（OpenClaw / peers 等）热议题，生成独立专题报告（不占用主题日报位）
- **可配置 LLM**：OpenAI 兼容协议（OpenAI / DeepSeek / Doubao / OneAPI 等），仅需 3 个环境变量
- **本地去重 + 幂等**：canonical URL 去重、跨源分数叠加、跨日指纹去重、报告已存在自动跳过（可 `--force` 重跑）
- **主题分类**：按源白名单规则分配 + LLM 精修，信号可命中多个主题
- **多主题日报**：综合 / 科技 / AI 深度 / 财经 / 吃瓜 / 国际，每个主题独立生成一份日报
- **用户自定义源**：标准 OPML 2.0 订阅，默认进综合早报，可按关键字映射到任意主题
- **无 key 冒烟**：`--mock-llm` 可在不填 LLM 密钥的情况下跑通整条管线
- **双调度**：GitHub Actions 每日 cron + 本地 `uv run` 一键运行

---

## 🧱 数据源一览（43 个）

| 类别 | 源 key |
|---|---|
| **API/爬虫** | `hackernews` · `github` · `v2ex` · `producthunt` · `huggingface` · `weibo` · `wallstreetcn` · `tencent` · `36kr` · `lobsters` · `devto` · `reddit` |
| **趋势** | `google_trends`（pytrends） · `hn_ai`（HN 6 个 AI 查询串 → Algolia） |
| **AI/RSS** | `arxiv` · `aihot` · `tldr_ai` · `import_ai` · `bensbites` · `interconnects` · `oneusefulthing` · `chinai` · `memia` · `aitoroi` · `kdnuggets` |
| **中文深度** | `sspai` · `infoq_cn` |
| **国际** | `bbc_top` · `bbc_world` · `bbc_chinese` · `guardian_world` · `aljazeera` · `france24` · `reuters` |
| **播客/专栏** | `lexfridman` · `80000hours` · `latentspace` · `waitbutwhy` · `jamesclear` · `farnamstreet` · `paulgraham` · `scottyoung` · `dankoe` |
| **自定义** | `user`（OPML） |
| **生态追踪** | `cli_tracker` · `agents_tracker`（GitHub API，仅产出专题报告，不参与主题日报） |

> 任一源失败自动跳过（`safe_fetch`），不影响整条管线。
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
# 验证llm配置是否准确
.venv/Scripts/python.exe scripts/llm_check.py "介绍下你自己"

# 3. 跑一次（生成全部主题日报）
.venv/Scripts/python.exe -m aiaggr.main

# 无 key 冒烟（模拟 LLM，验证管线）
.venv/Scripts/python.exe -m aiaggr.main --mock-llm --source hackernews,weibo --topic general,tech
```

成功输出示例：

```
=== AI 聚合日报 · 2026-08-05 ===
→ 并行抓取 40+ 个数据源 ...
✓ 抓取到 156 条原始信号
✓ 聚合去重后 98 条唯一信号
✓ 主题分类: {'general': 55, 'tech': 40, ...}
✓ [general] 已保存到 report\2026\08\05\general.md
...
→ 完成：6 份主题日报写入 report
→ manifest.json 更新 / feed.xml 更新
```

---

## 🖥 CLI 用法

| 参数 | 说明 | 默认 |
|---|---|---|
| `--date YYYY-MM-DD` | 报告日期（按配置时区） | 今天 |
| `--topic general,tech` | 只看指定主题 | 全部 |
| `--source hackernews,github` | 数据源 key 逗号分隔；`user` 为 OPML 自定义源 | `all` |
| `--limit N` | 覆盖每个数据源的抓取条数上限 | 各源配置 |
| `--force` | 强制重跑，覆盖已存在日报 | 否 |
| `--collect` | 采集模式：只抓取+去重+规则分类，不调 LLM、不生成日报，输出按主题分组的信号 JSON | 否 |
| `--mock-llm` | 模拟 LLM，无需密钥 | 否 |
| `--no-llm` | 跳过 LLM 主题精修（仅规则分类） | 否 |
| `--json` | Agent 友好输出：进度日志进 stderr，stdout 只输出结果 JSON | 否 |
| `--list-sources` | 列出所有数据源 key | — |
| `--config PATH` | 指定 config.yaml | `config.yaml` |

### 🤖 Agent / 脚本直接使用

**两种 Agent 模式**：

- **`--collect --json`（无需 LLM key）**：CLI 只负责抓取+去重+规则分类，stdout 输出按主题分组的信号 JSON；由 Agent 自己的大模型按 `prompts/report.*.md` 写日报并归档。**推荐给 Agent 使用**。
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

> `--collect` 的 `tracking` 段包含生态追踪信号（每条带 `project` / `repo` / `kind`），供 Agent 生成 `ai-cli.md` / `ai-agents.md` 专题报告。

```jsonc
// 自动模式（有 .env LLM 时）
{
  "exit_code": 0, "date": "2026-08-05", "mode": "llm",
  "fetched": 156, "unique": 98, "sources": 40,
  "sources_empty": ["v2ex"],
  "topics": [{ "key": "general", "name": "综合早报", "icon": "🌍",
               "tagline": "综合早报 · 15 条信号",
               "file": "report\\2026\\08\\05\\general.md", "count": 15, "skipped": false }],
  "index": "report\\2026\\08\\05\\index.md",
  "new_fingerprints": 15
}
```

先看 `exit_code`（`0` 成功 / `1` 部分失败 / `2` 配置错误）：`--json` 当天日报已存在会 `skipped: true` 早退，不是失败；`--collect` 不受日报存在性影响。Agent 接入规范详见根目录 [`SKILL.md`](SKILL.md)。

---

## 🎯 主题日报（默认 6 个，可在 config.yaml 增删）

| 主题 | key | 源白名单 | 日报文件 |
|---|---|---|---|
| 🌍 综合早报 | `general` | HN · GitHub · V2EX · PH · 微博 · 36氪 · 腾讯 · user | `general.md` |
| 🦄 科技早报 | `tech` | HN · GitHub · PH · V2EX · Lobsters · Dev.to · 少数派 · InfoQ | `tech.md` |
| 🧠 AI 深度日报 | `ai_daily` | HF Papers · arXiv · AIHOT · TLDR · newsletters · Import AI | `ai_daily.md` |
| 📈 财经早报 | `finance` | 华尔街见闻 · 36氪 · 腾讯 | `finance.md` |
| 🍉 吃瓜早报 | `social` | 微博 · V2EX | `social.md` |
| 🌐 国际新闻 | `international` | BBC · Guardian · Al Jazeera · France 24 · Reuters | `international.md` |

相关的生态追踪专题报告（`--collect` 不生成，仅 `--json` 自动模式生成）：

| 报告 | 源 | 内容 |
|---|---|---|
| `ai-cli.md` | `cli_tracker` | Claude Code / Claude Code Skills / DeepSeek TUI 等的热门 Issue、PR、Release |
| `ai-agents.md` | `agents_tracker` | OpenClaw / Agent 核心库等的热门 Issue、PR、Release |

分类逻辑：**源白名单规则分配**（基础，确定性）+ **LLM classifier 精修**（通用源可命中更垂直主题，失败自动降级为规则结果）。

---

## 📦 输出结构

```
report/
└── YYYY/
    └── MM/
        └── DD/
            ├── index.md          # 当日索引（各主题速览 + tagline）
            ├── general.md
            ├── tech.md
            ├── ai_daily.md
            ├── finance.md
            ├── social.md
            ├── international.md
            ├── ai-cli.md         # 生态追踪专题（cli_tracker）
            └── ai-agents.md      # 生态追踪专题（agents_tracker）

# 站点交付目录 site/（每次日报后重建，供 Web UI / RSS）
site/index.html     # Web UI（自包含，hash 路由）
site/manifest.json  # Web UI 数据源（日期 → 主题 → 文件）
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

### 推送 / 站点 / 生态追踪（`.env`）

```bash
# 飞书机器人 webhook（多个用逗号分隔；兼容旧 FEISHU_WEBHOOK_URL）
FEISHU_WEBHOOK_URLS=
# GitHub Token：生态追踪提限流；也可用于 daily-report.yml 内的 PR/发布等操作
GITHUB_TOKEN=
# GitHub Pages 站点地址（manifest/feed/web UI 内链接的 base_url）
PAGES_URL=
```

### `config.yaml`

- `llm`：模型、超时、温度、mock
- `timezone`：日报按本地日期归属（默认 `Asia/Shanghai`）
- `dedup`：跨日去重窗口（默认 7 天）、是否排除、是否忽略跟踪参数
- `topics`：主题定义（`sources` 白名单 / `limit` / `prompt` 文件）
- `sources`：数据源开关与参数
- `opml`：自定义源 OPML 路径与主题映射
- `site`：站点交付（`base_url` 供 manifest/feed/web UI 引用）
- `tracking`：生态追踪（`cli_tracker` / `agents_tracker` 的仓库列表，默认内置 AI CLI / Agent 生态仓库）

### 用户自定义订阅源（User OPML）

把常看的 RSS/Atom 写进 OPML，`--source user` 即可统一抓取：

1. **放置 OPML 文件**（按优先级查找）：
   - `~/.config/news-aggregator/user_sources.opml`
   - `<项目根>/user_sources.opml`
2. **格式**：标准 OPML 2.0，仅 `xmlUrl` 必填（参考 `user_sources.opml.example`）：

   ```xml
   <outline type="rss" text="Simon Willison" title="Simon Willison"
            xmlUrl="https://simonwillison.net/atom/everything/" />
   ```

3. **主题归属**：默认进 `general`；OPML 条目加 `data-topic="ai_daily"` 直接指定，或在 `config.yaml` 的 `opml.topic_map` 配置关键字映射：

   ```yaml
   opml:
     topic_map:
       "ai": ai_daily
       "llm": ai_daily
   ```

---

## ⚙️ 去重与幂等

| 机制 | 说明 |
|---|---|
| **同日去重** | canonical URL（去 utm/fbclid 等跟踪参数）去重；跨源同 URL 分数叠加 |
| **跨日去重** | `.state/seen.jsonl` 记录每日已产出信号指纹，7 天窗口内重复信号不再进当日日报 |
| **报告幂等** | `report/YYYY/MM/DD/{topic}.md` 已存在则跳过 LLM 调用（省成本）；`--force` 强制重跑 |
| **跨日主题去重** | `.state/taglines.jsonl` 记录每日各主题 tagline，作为次日日报避免主题重复的锚 |

`.state/` 会随 git 提交，保证 GitHub Actions 连续运行时跨日去重持续生效。

---

## 🤖 GitHub Actions

`.github/workflows/daily-report.yml`：

- 每日 UTC 定时运行 + 手动 `workflow_dispatch`
- 运行时填入 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `GITHUB_TOKEN` / `FEISHU_WEBHOOK_URLS` / `PAGES_URL` secrets
- 生成后自动 commit `report/` 与 `.state/`，并重建 `site/` 下 `manifest.json` / `feed.xml`
- 未配置 `FEISHU_WEBHOOK_URLS` 时静默跳过飞书推送

`.github/workflows/pages.yml`：手动 `workflow_dispatch` 可发布 GitHub Pages（`site/` 下的 `index.html` + `manifest.json` + `feed.xml` + `report/`），提供在线 Web UI 与 RSS 订阅。

---

## 🧩 如何扩展

### 新增数据源

1. 在 `aiaggr/fetchers/` 新建 `mydata.py`，继承 `BaseFetcher` 实现 `async fetch()`，返回 `Signal` 列表
2. 在 `aiaggr/fetchers/__init__.py` 的 `_API_CLASSES` 注册（RSS 源直接加进 `config.yaml` 的 `sources.rss`）
3. 需要 API key 时在 `.env.example` 与 workflow env 补变量
4. `--source mydata` 验证

### 新增主题

在 `config.yaml` 的 `topics` 加一项（`sources` 白名单 + `prompt` 文件），并新建 `prompts/report.{topic}.md`。

---

## 📁 项目结构

```
ai-aggregator-report/
├── aiaggr/                  # 核心包
│   ├── main.py              # CLI 入口
│   ├── config.py            # config.yaml + .env 加载
│   ├── dedup.py             # 去重幂等核心（canonical URL + 指纹）
│   ├── state.py             # seen.jsonl / taglines.jsonl 状态
│   ├── llm.py               # OpenAI 兼容客户端 + mock
│   ├── classifier.py        # 主题分类（规则 + LLM 精修）
│   ├── pipeline.py          # 主题日报生成管线
│   ├── renderer.py          # markdown 落盘 + index
│   ├── notify.py            # 飞书推送（interactive 卡片，无 webhook 静默跳过）
│   ├── site.py              # 站点交付（manifest.json + feed.xml RSS）
│   ├── tracking.py          # 生态追踪专题报告生成器
│   ├── fetchers/            # 统一数据源层
│   │   ├── github_tracker.py # cli_tracker / agents_tracker（GitHub API）
│   │   └── hn_ai.py          # HN 6 查询串 → Algolia
│   ├── prompts/             # LLM 提示词（classifier + report.* + tracking.*）
│   ├── config.yaml          # 主配置
│   ├── site/                 # 站点交付目录（统一管理，提交）
│   │   ├── index.html        # Web UI（自包含，hash 路由）
│   │   ├── manifest.json     # Web UI 数据源（提交）
│   │   └── feed.xml          # RSS 2.0（提交）
│   ├── report/              # 输出 report/YYYY/MM/DD/
│   ├── .state/              # 幂等状态（提交）
│   └── ref/                     # 参照项目（dailydawn / news-aggregator-skill）
```

---

## 依赖

`httpx · feedparser · beautifulsoup4 · lxml · python-dotenv · openai · tenacity · PyYAML · tzdata · pytrends`（`praw` 可选，Reddit 默认走公开 JSON；`markdown` 可选，缺失时 Web UI 使用内置轻量渲染器）

## License

MIT
