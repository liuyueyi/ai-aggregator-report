# AGENTS.md

本文件是给未来接手此仓库的 AI Agent / 协作者的开发指引。读完本文件即可接手开发。

---

## 🎯 这是什么

**AI 聚合日报（ai-aggregator-report）**：基于 LLM 的多源热点采集与多主题日报生成引擎。

- 从 45+ 数据源并发抓取新闻信号
- 本地去重幂等（canonical URL + 跨日指纹）
- 按主题分类，为每个主题用 LLM 生成一份日报
- 输出到 `report/YYYY/MM/DD/{topic}.md` + `index.md`
- 交付层：`manifest.json` + `feed.xml`（Web UI / RSS）+ 飞书推送
- 生态追踪：`cli_tracker` / `agents_tracker` 生成 `ai-cli.md` / `ai-agents.md` 专题报告

参照项目（不参与运行，仅作参考）：
- `ref/dailydawn/` → 架构蓝本（异步抓取、Signal 模型、聚合、LLM 管线、GitHub Actions）
- `ref/news-aggregator-skill/` → 流程指引（多主题、统一日报模板、反幻觉规则）
- `ref/agents-radar/` → 能力参照（Web UI / RSS / 飞书推送 / 生态追踪 / HN 并行查询）

---

## 🏃 本地运行与验证

```bash
# 安装依赖
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 无 LLM 密钥的冒烟测试（管线全流程验证，推荐每次改动后跑）
.venv/Scripts/python.exe -m aiaggr.main --mock-llm --source hackernews,weibo --topic general,tech

# 全量实跑（需 .env 配好 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）
.venv/Scripts/python.exe -m aiaggr.main

# 语法检查
.venv/Scripts/python.exe -m compileall -q aiaggr

# Agent 模式校验（--json）：进度进 stderr，stdout 只输出结果 JSON（exit_code 0 成功）
.venv/Scripts/python.exe -m aiaggr.main --mock-llm --source hackernews --topic general --json

# 采集模式（--collect）：无需 LLM key，只抓取+去重+规则分类，stdout 输出按主题分组的信号 JSON
# （配合 --json 供上层 Agent 自行写日报，见根目录 SKILL.md）
.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews --topic general

# 生态追踪冒烟（GitHub API，产出 ai-cli.md / ai-agents.md 专题报告）
.venv/Scripts/python.exe -m aiaggr.main --mock-llm --source cli_tracker,agents_tracker --topic general

# 文章生产工作流（独立入口，不依赖 main.py 的 --article）
# 冒烟测试（mock 模式，无需 LLM key）
.venv/Scripts/python.exe -m aiaggr.article_cli --mock-llm --source toutiao --topic social

# 真实 LLM 生成
.venv/Scripts/python.exe -m aiaggr.article_cli --source hn_ai --topic ai_daily --limit 12

# Agent 模式（JSON stdout）
.venv/Scripts/python.exe -m aiaggr.article_cli --mock-llm --source hackernews --topic general --json

# 选题参考模式（读取已有日报，LLM 生成选题建议，不抓取不生成文章）
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only
.venv/Scripts/python.exe -m aiaggr.article_cli --topics-only --topic general,tech --mock-llm
```

> Windows cmd 落盘 UTF-8 JSON 用 `cmd /c "... > out.json"`（PowerShell `1>` 会转 UTF-16）。Agent 接入规范见根目录 `SKILL.md`。
```

Windows 控制台 GBK 编码：`aiaggr/main.py` 的 `main()` 已对 stdout/stderr 做 UTF-8 reconfigure，不要移除（否则 `✓/✗` 会抛 `UnicodeEncodeError`）。

---

## 🗂 文件地图

```
aiaggr/
├── main.py           ⭐ CLI 入口（热点日报）：幂等检查 → 抓取 → 聚合 → 跨日去重 → 分类 → 逐主题生成 → 落盘 → 选题建议 → 站点产物 → 飞书
├── article_cli.py    ⭐ CLI 入口（文章生产）：独立于热点日报，走选题→证据→计划→草稿→审稿→排版流水线；也提供 --topics-only 选题参考模式
├── config.py         加载 config.yaml + .env；提供 topics/sources/report/state/site/tracking 等访问器
├── dedup.py          canonical_url / fingerprint / aggregate（同日去重+分数叠加）
├── state.py          StateStore：seen.jsonl（跨日指纹）+ taglines.jsonl（跨日主题锚）
├── llm.py            OpenAI 兼容客户端（response_format json 降级 + tenacity 重试 + mock）
├── classifier.py     rule_assign（源白名单）+ _llm_refine（LLM 精修）→ classify()
├── pipeline.py       generate_topic_report（拼 prompt → call_json → 兜底 fallback_report）
├── topics.py         选题建议生成器（generate_topic_suggestions + _compute_diff + render_topics_md）
├── renderer.py       save_report / save_index / report_exists（report/YYYY/MM/DD/）
├── notify.py         飞书推送（interactive 卡片；FEISHU_WEBHOOK_URLS 未配置静默跳过）
├── site.py           build_manifest / build_feed / build_site（markdown 可选，缺失时 _md_to_html_simple 降级）
├── tracking.py       生态追踪专题报告生成器（_calc/_tagline/_fallback/generate）
├── article/          ⭐ 文章生产工作流（--article）：rank→topic→decision→evidence→plan→draft→title→review→gate→revision→cover→render
│   ├── workflow.py   run_article 调度 + 产物落盘（每阶段失败走确定性兜底）
│   ├── common.py     signal→item 序列化 + llm_stage 统一调用 + host 分类/噪声域
│   ├── rank.py       排序（LLM 行式打分 / rank_items_local 兜底）
│   ├── topic.py      选题聚类（8 维评分 + recommendedUse + 接地守卫）
│   ├── decision.py   编辑决策（主线/格式/duplicationRisk/sourceJudgements）
│   ├── evidence.py   证据补全（Jina Reader 补抓 + host 分类 + supports/confidence）
│   ├── plan.py       文章计划（sections/itemIds + 接地守卫 + 证据深度门禁降级）
│   ├── draft.py      草稿（只允许输入事实 + 编辑标注清洗）
│   ├── title.py      标题（titleDirections→thesis→leadTitle，低质正则过滤，≤60 字）
│   ├── review.py     质量审稿（5 维分 + issues + recommendedAction + 一致性守卫）
│   ├── gate.py       质量门禁（dry-run/disabled/block/allow + 安全 issue 判定）
│   ├── revision.py   修订循环（只修安全项，复审后分数单调才采纳）
│   ├── cover.py      配图方案（本期仅生成 prompt 方案，不接生图 API）
│   └── render.py     排版（Markdown + 微信兼容 HTML 白名单清洗）
└── fetchers/
    ├── base.py       Signal dataclass + BaseFetcher ABC + safe_fetch + normalize_score
    ├── __init__.py   _API_CLASSES 注册表 + build_fetchers + select_fetchers
    ├── rss.py        RssFetcher（feedparser，hours 窗口过滤，fail-open）
    ├── rsshub.py     RsshubFetcher（RSSHub JSON 路由：公众号/小红书/X，fail-open）
    ├── twitter.py    TwitterFetcher（TwitterAPI.io + Xquik 双后端，env TWITTER_API_KEY/XQUIK_API_KEY）
    ├── toutiao.py    ToutiaoHotFetcher（头条热榜公开 PC 接口直连，不经 RSSHub）
    ├── user_opml.py  UserOpmlFetcher（OPML 解析 + 主题映射）
    ├── hn_ai.py      HN 6 查询串 → Algolia（source_key=hn_ai）
    ├── github_tracker.py  RepoTrackerFetcher + build_fetchers（cli_tracker/agents_tracker）
    └── (专用源…)
prompts/
├── classifier.md
├── report.{topic}.md   （general/tech/ai_daily/finance/social/international）
├── article.{topic,decision,plan,draft,review,revision}.md  （文章工作流各阶段，严格 JSON 契约）
├── article_topics.md   （选题参考模式：读日报生成选题建议）
└── tracking.{cli,agents}.md  （生态追踪专题模板）
config.yaml            主配置（llm / timezone / dedup / report / state / site / tracking / article / topics / sources(rss+rsshub) / opml）
report/               输出目录（YYYY/MM/DD/{topic}.md + index.md + topic_suggestions.md + ai-cli.md/ai-agents.md）
article/              文章工作流产物（YYYY/MM/DD/{slug}.md + .html + .plan.json）
.state/               幂等状态（必须随 git 提交，CI 连续去重依赖它）
  ├── seen.jsonl        最近 N 天已产出信号指纹（自动归档，只保留 window_days 天）
  ├── taglines.jsonl    每日各主题一句话摘要
  └── arch/             归档目录（超过 window_days 天的旧指纹按月归档）
      └── YYYYMM-seen.jsonl  月度归档文件（如 202608-seen.jsonl）
site/                站点交付目录（统一管理 index.html / manifest.json / feed.xml，提交 git）
```

---

## 🔄 数据流

```
main.py
 ├─ 1. 幂等：主题日报已存在且未 --force → 跳过（早退，省 LLM 成本）
 ├─ 2. select_fetchers(cfg, --source) → asyncio.gather(safe_fetch) 并发抓取
 ├─ 3. dedup.aggregate()：canonical URL 去重 + 跨源同 URL 分数叠加 + age_bucket
 ├─ 4. state.mark_seen()：7 天窗口内更早日期出现过的指纹 → signal.seen_on
 ├─ 5. classifier.classify()：规则分配 + LLM 精修 → {topic: [signals]}
 ├─ 6. 每主题：过滤 seen_on → 取 score 前 N → generate_topic_report → renderer.save_report
 ├─ 6b. 生态追踪：cli_tracker/agents_tracker 信号独立走 tracking.py → ai-cli.md/ai-agents.md（不占主题位）
 ├─ 7. state.record_emitted() + state.append_tagline() + renderer.save_index()
 ├─ 8. topics.generate_topic_suggestions() → topic_suggestions.md（含前日 diff + 为什么值得写）
  └─ 9. site.build_site()（写入 site/：manifest.json + feed.xml）+ notify.send_feishu()（仅非 collect）

> record_emitted 会自动归档超过 window_days 天的旧指纹到 .state/arch/YYYYMM-seen.jsonl
```

---

## 📌 核心约定

### Signal 数据模型（`fetchers/base.py`）
所有抓取器必须输出此结构：
```python
@dataclass
class Signal:
    source: str            # 显示名（"HackerNews" / "Reddit /r/x"）
    title: str
    url: str
    source_key: str        # 注册表 key（主题分配依赖，必须填）
    raw_score: float
    score: float           # 归一化 0-1（normalize_score(raw, typical_max)）
    comments: int
    author: str
    heat: str              # 原始热度文本（微博"108万"原样保留）
    summary: str
    tags: list[str]
    published_at: str|None # ISO 8601 UTC；无单条发布时间概念留 None（如 GitHub Trending）
    hn_url: str            # HN 讨论链接（如有）
    gh_url: str            # GitHub 仓库链接（如有）
    extra: dict            # 源特有字段
    topics: list[str]      # classifier 运行时填充
    seen_on: str|None      # state 运行时填充（跨日重复日期）
    age_bucket: str        # dedup 运行时填充（today/past_72h/older/unknown）
```

### 新增数据源
1. 建 `aiaggr/fetchers/mydata.py`，继承 `BaseFetcher`：
   - 类属性：`source_key`（必须与 config.yaml 的 key 一致）、`source_name`
   - 实现 `async def fetch(self, client) -> list[Signal]`（httpx.AsyncClient）
   - 每个 Signal 必须带 `source_key`
2. 在 `aiaggr/fetchers/__init__.py` 的 `_API_CLASSES` 注册（`key: 类`）
3. **纯 RSS 源**不需要写类：直接在 `config.yaml` 的 `sources.rss` 加一条 `{name, url, hours, enabled}` 即可
4. 需要 API key：`.env.example` 加变量 + workflow 加 secret 引用
5. 验证：`--source mydata --mock-llm`

**评分归一化约定**：`score = normalize_score(raw, typical_max)`。不同源 typical_max 不同：HN 500、GitHub stars 1000、Reddit 2000、微博 100万、RSS 按位置序 20。

### 社交数据源（公众号/小红书/头条/Twitter，`fetchers/rsshub.py` + `fetchers/twitter.py` + `fetchers/toutiao.py`）
这些平台多数无公开 API，接入路径分三类：
- **头条走直连 API**（`fetchers/toutiao.py`）：`ToutiaoHotFetcher` 直接命中公开 PC 热榜接口 `https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc`，**不依赖 RSSHub**，config 用 `sources.toutiao: {type: api, limit}`（已注册 `_API_CLASSES`，sources 里也保留 `toutiao` key 于 social 主题）。`rsshub` 段**不要**再放 `/toutiao/hot`，否则与直连抓取器 source_key 冲突。
- **RSSHub 路由**（公众号/小红书等）：在 `config.yaml` 的 `sources.rsshub` 加一个 `{name, path, hours, enabled}` 条目即可（如 `/wechat/{公众号名}`、`/xhs/user/{uid}`、`/twitter/user/{screen_name}`）。`RsshubFetcher` 请求 `{base}{path}?format=json&limit=N&sorted=1`，`base` 取自 env `RSSHUB_BASE_URL`（默认 `https://rsshub.app`）。公众号/小红书部分路由需自建 RSSHub + token/cookie，公共实例大多 404/503，失败走 `safe_fetch` 返回空，fail-open。
- **Twitter 专用 API**（`fetchers/twitter.py`）：双后端。首选 TwitterAPI.io（`X-API-Key` = `TWITTER_API_KEY`），失败 fallback Xquik（`x-api-key` = `XQUIK_API_KEY` + 契约头）。`config.accounts` 列账号；至少一个 key 才启用，否则返回空并提示。
- 新增 RSSHub 条目**无需写代码**；新增某平台专用抓取器才需要建类 + 注册 `_API_CLASSES` + 加 `.env.example`。

### 文章生产工作流（`aiaggr/article_cli.py`，独立入口）
独立于主题日报：抓取 → 聚合 → 跨日去重 → `rank → topic → decision → evidence → plan → draft → title → review → gate → revision → cover → render`。产出 `article/YYYY/MM/DD/{slug}.md` + `.html`（微信兼容）+ `.plan.json`（含 decision/topic/evidence/plan/review/gate/cover 全链路）。入参上限 `article.input_limit`（默认 40，按 score 取前 N）。
- 选题参考模式（`--topics-only`）：读取当日已有日报，逐主题调 LLM 生成选题建议，输出 `report/YYYY/MM/DD/topic_suggestions.md`（Markdown + 前日 diff + 每条选题的「为什么值得写」）。不抓取、不生成文章。
- 证据链贯穿全程：`topic.clusters[].itemIds` → `plan.sections[].itemIds` → `draft` 仅用来源事实 → `review` 对照来源审 fact。
- **每一阶段 LLM 失败/空返回都走确定性兜底**（topic/decision/plan/draft/review 的 `fallback_*`）；`--mock-llm` 时管线用兜底产物，不阻塞。
- 接地守卫：`topic._grounding_guard`（高风险断言须见于源文本）、`plan._ground_entities`（未见于源的专名实体 → 风险注记抑制扩展）、`plan._enforce_depth_gate`（深度格式却无直接证据 → 降级 daily-brief）。
- 质量门禁（`gate.evaluate_gate`）：dry-run 只管 `allow-dry-run`；blocker/高 fact/不放行/分数不足 → block。修订（`revision`）只修安全 issue，复审后分数单调不降才采纳，否则回滚。
- 配图（`cover`）本期仅生成封面/正文配图 **prompt 方案**（`mode: plan-only`），不接生图 API，后续接 DashScope/MiniMax。
- 幂等：`article_cli.py` 的 `amain` 会 `record_emitted` **实际进入文章的**信号（`used_item_ids`），维持跨日去重。

### 新增主题
在 `config.yaml` `topics` 加一项：
```yaml
mytopic:
  name: 我的主题
  icon: 🚀
  prompt: report.mytopic.md
  limit: 10
  sources: [hackernews, ...]
  enabled: true
```
并新建 `prompts/report.mytopic.md`。prompt 里的占位符：`{{date}}` / `{{topic_name}}` / `{{signals_json}}` / `{{recent_taglines}}`，必须让模型严格输出 `{"tagline": "...", "markdown": "..."}`。

### LLM 调用（`llm.py`）
- 配置契约：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 三个环境变量（无默认值）
- `call_json` 优先 `response_format={"type":"json_object"}`，模型不支持时自动降级 + `_extract_json` 兼容 code fence
- tenacity 指数退避重试；`mock` 模式下返回 `{}`，**管线层必须在 mock 时走 fallback_report 而非依赖 call_json**
- 调整日报质量 → **改 prompts，不要改代码**（见 `prompts/report.*.md`）

### 生态追踪（`tracking.py` / `fetchers/github_tracker.py`）
- `cli_tracker` / `agents_tracker` 是**专题追踪源**，信号不参与主题日报分类，专供 `ai-cli.md` / `ai-agents.md`
- `RepoTrackerFetcher` 走 GitHub REST API（`issues?sort=comments` + `releases`）；有 `GITHUB_TOKEN` 用 Bearer，匿名限 60 次/小时
- 追踪信号在 `extra` 里带 `project` / `repo` / `kind`（issue/pr/release）；`_collect_signal` 会原样带出供 Agent 用
- `tracking.generate` 在 `settings["mock"]` 时走 `_fallback` 确定性模板（同 pipeline 的 mock 语义），不注入新 key
- 报告计数与 index.md 自动并入当日归档；单仓库/单次请求失败由 `safe_fetch` 兜底

### 站点交付（`site.py` / `notify.py`）
- `build_site` 每次日报后重建 `site/` 下 `manifest.json` + `feed.xml`（RSS 2.0 `content:encoded` 全文，最新 30 条）；目录可通过 `config.yaml site.dir` 配置（默认 `site/`）；`--collect` 不构建
- `markdown` 依赖可选：ImportError 时走 `_md_to_html_simple` 内置轻量渲染器（标题/列表/引用/加粗/链接/代码子集），CI 联网装全量包
- 飞书 webhook 用 `FEISHU_WEBHOOK_URLS`（逗号分隔，兼容旧 `FEISHU_WEBHOOK_URL`）；未配置**静默跳过**，不报错
- `index.html` 为自包含 Web UI（hash 路由 `#date/topic`，CDN marked）；`pages.yml` 打包 `site/`（index/manifest/feed）与 `report/` 到 GitHub Pages

### 去重/幂等语义（重要）
- `dedup.fingerprint(signal)`：优先 `sha1(canonical_url)`，无有效 URL 回退归一化标题
- **跨日去重只排除「更早日期」的指纹**：`state.seen_fingerprints(before_date=today)` 只返回 `date < today` 的记录。所以 `--force` 重跑当日不会把今天已产出的信号全判为重复而产空日报——不要改成包含当日
- `state.record_emitted` 只记录「实际进入日报」的信号（`emitted` 列表），不记录全部抓取结果
- **`--collect` 采集模式**：只抓取+去重+规则分类（`classify(use_llm=False)`），不调 LLM、不生成日报；跳过「日报已存在」幂等早退；仍会把每主题 top-N 信号 `record_emitted`（这批信号视为当日被消费，维持跨日去重连续性）。stdout JSON 的 `topics` 为 `{key: [signal...]}`
- **归档机制**：`record_emitted` 会自动将超过 `window_days`（默认 7 天）的旧指纹归档到 `.state/arch/YYYYMM-seen.jsonl`（按月分组），主 `seen.jsonl` 只保留最近 N 天数据，避免文件无限增长
- `.state/` 提交 git，勿加入 .gitignore
- GitHub Trending / Google Trends 无逐条发布时间 → `published_at=None`，prompt 会按 age_bucket=unknown 处理，不要硬造时间

---

## ⚠️ 已知坑

1. **Windows 控制台 GBK**：打印 `✓/✗` 前必须确保 UTF-8 reconfigure（main.py 已处理）
2. **网络脆弱源**：V2EX/Reddit/36Kr 等在部分网络环境超时/限流属正常，`safe_fetch` 兜底空列表，单源失败不阻塞
3. **pytrends 未公开接口**：偶发 429，Google Trends 全部失败时管线降级为"低信号日"，属预期
4. **LLM 输出校验**：`generate_topic_report` 对空 markdown / 非 dict 返回值做了 fallback_report 兜底；新加 LLM 调用务必同样兜底
5. **age_bucket 幻觉防护**：prompt 强制要求时间描述基于 `age_bucket` 字段；不要在代码里给 unknown 编造时间

---

## ✅ 改动后自检清单

- [ ] `python -m compileall -q aiaggr`
- [ ] `--mock-llm --source <新源> --topic <相关主题>` 跑通
- [ ] 新源返回的 Signal 都带 `source_key`
- [ ] RSS 源新条目都带 `hours` 窗口（国际源 24h / tldr 48h / import_ai 168h）
- [ ] 新增/改动 RSSHub 或 Twitter 源后跑一次 `python -m aiaggr.article_cli --mock-llm`，确认 md/html/plan.json 产物与门禁结果正常
- [ ] `python -m aiaggr.article_cli --topics-only --mock-llm` 确认选题建议 JSON 产物正常
- [ ] 动了 site/tracking 后跑一次 `--mock-llm` 全量，确认 manifest/feed/专题报告正常
- [ ] `.state/` 未被误加 gitignore
