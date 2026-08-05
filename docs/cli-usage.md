# 将本项目作为 CLI 使用

本项目是纯命令行工具，入口为 `python -m aiaggr.main`，可被脚本、定时任务、CI 或上层系统直接调用。核心设计：**进度日志走 stderr，stdout 只输出结构化 JSON**（`--json` 时），便于程序消费。

## 安装

```bash
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

Windows 的可执行文件路径是 `.venv/Scripts/python.exe`；Linux/macOS 为 `.venv/bin/python`。

## 全部参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--date YYYY-MM-DD` | 报告日期（按配置时区） | 今天 |
| `--topic general,tech` | 只看指定主题（逗号分隔） | 全部 |
| `--source hackernews,github` | 数据源 key（逗号分隔）；`user` 为 OPML 自定义源 | `all` |
| `--limit N` | 覆盖每个数据源的抓取条数上限 | 各源配置 |
| `--force` | 强制重跑，覆盖已存在日报 | 否 |
| `--collect` | 采集模式：只抓取+去重+规则分类，不调 LLM、不生成日报 | 否 |
| `--mock-llm` | 模拟 LLM，无需密钥（验证管线） | 否 |
| `--no-llm` | 跳过 LLM 主题精修（仅规则分类） | 否 |
| `--json` | 进度进 stderr，stdout 只输出结果 JSON | 否 |
| `--list-sources` | 列出所有数据源 key | — |
| `--config PATH` | 指定 config.yaml | `config.yaml` |

```bash
.venv/Scripts/python.exe -m aiaggr.main --help
.venv/Scripts/python.exe -m aiaggr.main --list-sources
```

## 三种典型调用方式

### 1. 采集模式（`--collect`，无 LLM key）

只抓取+去重+规则分类，**不调用任何 LLM**，stdout 输出按主题分组的信号 JSON：

```bash
.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews,weibo --topic general
```

适合：由上层脚本/Agent 消费信号后自己写内容，或做数据分析、喂给其他系统。

### 2. 自动生成日报（需 `.env` 配 LLM）

全自动抓取 → 分类 → LLM 生成 → 落盘 → 更新站点产物：

```bash
.venv/Scripts/python.exe -m aiaggr.main --json
.venv/Scripts/python.exe -m aiaggr.main --json --topic general,tech --source hackernews,github
.venv/Scripts/python.exe -m aiaggr.main --json --date 2026-08-05
```

stdout 结果示例：

```jsonc
{
  "exit_code": 0,                 // 0 成功 / 1 部分失败 / 2 配置错误
  "date": "2026-08-05", "mode": "llm",
  "fetched": 156, "unique": 98, "sources": 40,
  "sources_empty": ["v2ex"],
  "topics": [{ "key": "general", "name": "综合早报", "icon": "🌍",
               "tagline": "综合早报 · 15 条信号",
               "file": "report\\2026\\08\\05\\general.md", "count": 15,
               "skipped": false }],
  "index": "report\\2026\\08\\05\\index.md",
  "new_fingerprints": 15
}
```

> `--json` 时当天日报已存在会 `skipped: true` 早退（`exit_code 0`），不是失败；重跑需 `--force`。

### 3. 冒烟验证（`--mock-llm`）

无密钥跑通整条管线，适合 CI 自检或改动后验证：

```bash
.venv/Scripts/python.exe -m aiaggr.main --mock-llm --source hackernews,weibo --topic general,tech
```

## 在脚本 / 定时任务 / 其他系统中集成

### 判断成败

先看 stdout JSON 的 `exit_code`：`0` 成功 / `1` 部分失败（某些源超时，结果仍可用）/ `2` 配置错误。

### 每天定时生成日报

- **Linux/macOS（crontab）**：

  ```cron
  # 每天 06:00（北京时间，服务器本地时区需自行换算）
  0 6 * * * cd /path/to/ai-aggregator-report && .venv/bin/python -m aiaggr.main --json >> daily.log 2>&1
  ```

- **Windows 任务计划程序**：新建计划任务 → 操作 = `C:\...\.venv\Scripts\python.exe -m aiaggr.main --json`，起始于 = 项目根目录。

- **GitHub Actions**：见 [github-actions-usage.md](./github-actions-usage.md)。

### 采集模式接入数据管道

```bash
# 抓取信号 → 交给下游（如另一个脚本/服务消费）
.venv/Scripts/python.exe -m aiaggr.main --collect --json --source hackernews > signals.json
```

下游按 `topics` 键遍历信号即可，无需理解抓取细节。

## 进阶配置

- **自定义配置**：`--config path/to/config.yaml` 可指定不同的主题/源/输出目录配置。
- **用户自定义订阅源**：把 RSS/Atom 写进 OPML，`--source user` 统一抓取（见 README「用户自定义订阅源」）。
- **环境变量**（`.env` 或进程环境）：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`、`FEISHU_WEBHOOK_URLS`、`GITHUB_TOKEN`、`PAGES_URL`、`AGGR_MOCK_LLM=1`（等价 `--mock-llm`）。

## 常见问题

- **Windows 控制台中文乱码 / `UnicodeEncodeError`**：程序已自动对 stdout/stderr 做 UTF-8 reconfigure，直接运行即可；不要把该逻辑移除。
- **Windows 落盘 JSON 变成 UTF-16**：PowerShell `1>` 会转 UTF-16，用 `cmd /c ".venv\Scripts\python.exe -m aiaggr.main --collect --json > out.json"`。
- **`--json` 当天日报已存在**：是幂等早退（`skipped: true`），想重跑加 `--force`。
- **`--collect` 会写 .state 吗**：会。`--collect` 仍会把每主题 top-N 信号 `record_emitted`，以维持跨日去重连续性；不需要时可只读不写状态，或用临时 `--config` 指向别的 `.state`。
- **单源失败**：V2EX/Reddit/36Kr/Google Trends 偶发超时属正常，`sources_empty` 非空不影响整体结果。
