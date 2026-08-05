# 使用 GitHub Actions 进行数据采集

本项目内置两个 GitHub Actions 工作流，可**免费托管**在 GitHub 上实现每日定时采集与日报生成，无需本地服务器、无需手动运行。

## 工作流总览

| 文件 | 触发方式 | 作用 |
|---|---|---|
| `.github/workflows/daily-report.yml` | 每日定时 `cron` + 手动 `workflow_dispatch` | 抓取数据源 → 去重 → LLM 生成日报 → 提交 `report/` / `.state/` / `site/` |
| `.github/workflows/pages.yml` | 手动 + `main` 分支 push | 把 `site/`（Web UI + manifest + feed）与 `report/` 发布到 GitHub Pages |

## 一、一次性准备：配置 Secrets

在仓库 **Settings → Secrets and variables → Actions** 中配置（Secrets 用 `Actions secrets`，公开值用 `Variables`，放在 Repository secrets下）：

| 名称 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| `LLM_API_KEY` | Secret | 生成日报**必填** | LLM 密钥（OpenAI / DeepSeek / Doubao / OneAPI 等兼容协议） |
| `LLM_BASE_URL` | Secret | 生成日报**必填** | LLM API 地址，如 `https://api.openai.com/v1` |
| `LLM_MODEL` | Secret | 生成日报**必填** | 模型名，如 `gpt-4o-mini` |
| `GITHUB_TOKEN` | Secret | 可选 | 生态追踪提限流（匿名 60 次/小时 → 5000 次/小时） |
| `FEISHU_WEBHOOK_URLS` | Secret | 可选 | 飞书机器人 Webhook（多个用英文逗号分隔），未配置则静默跳过推送 |
| `PAGES_URL` | Variable | 可选 | 站点部署根 URL，如 `https://<user>.github.io/<repo>` |

> 未配置 `LLM_*` 时，工作流仍会运行，但日报会走 mock/降级路径——不建议这样做。若只想在云端「采集信号」而不生成日报，见下文「采集模式」。

## 二、日常运行

### 每日定时（已内置）

`daily-report.yml` 默认在 **UTC 22:00（北京时间 06:00）** 自动运行，执行全量抓取并生成全部主题日报。如需调整时间，修改 `cron` 表达式：

```yaml
on:
  schedule:
    # UTC 22:00 = 北京时间 06:00（Asia/Shanghai 时区）
    - cron: "0 22 * * *"
```

### 手动触发

仓库 **Actions** 页面 → 选中 **Daily Report** → **Run workflow** → 选分支 → 运行。

### 运行完成后自动提交

`daily-report.yml` 的最后一步会自动 `git add report .state site` 并 commit/push（无改动则跳过），因此：

- `report/YYYY/MM/DD/` 下的日报会实时进入仓库
- `.state/` 随 git 提交，保证跨日去重连续生效
- `site/` 下的 `manifest.json` / `feed.xml` 同步更新，RSS 订阅者自动拿到最新内容

## 三、部署在线 Web UI + RSS（pages.yml）

1. 仓库 **Settings → Pages**：Source 选 **GitHub Actions**（不要选 branch）。
2. 触发 `pages.yml`（push 到 `main` 会自动触发，也可手动）。
3. 部署完成后获得 `<user>.github.io/<repo>` 地址，把 `PAGES_URL` 配成该地址（供 manifest/feed 里的链接使用）。

## 四、常见的自定义场景

### 1. 云端只采集、不生成日报

若不想在云端消耗 LLM，可把 `daily-report.yml` 的 `Run pipeline` 改为采集模式（把信号 JSON 提交进仓库，供 Agent / 人工写日报）：

```yaml
- name: Run pipeline (collect mode)
  run: python -m aiaggr.main --collect --json --source hackernews,weibo > collect.json
```

> 注意 Windows 无此问题，但 CI 是 Linux，直接 `>` 重定向是 UTF-8，安全。

### 2. 只生成部分主题 / 部分源

修改 `run` 参数即可：

```yaml
run: python -m aiaggr.main --topic general,tech --source hackernews,github
```

### 3. 改推送频道或时区

- 推送：修改 `aiaggr/notify.py`（目前支持飞书 interactive 卡片，多 webhook）。
- 时区：改 `config.yaml` 的 `timezone`（日报按该时区归属日期，与 cron 时间无关）。

## 五、失败排查

- **看 Action 日志**：Actions 页面点击某次运行 → 查看失败步骤输出。
- **网络脆弱源**：V2EX / Reddit / 36Kr / Google Trends 偶发超时属正常，`safe_fetch` 会跳过单个失败源，不影响整条管线。
- **日报缺失**：确认 `LLM_*` Secrets 已配置且模型名/Base URL 正确；同一天日报已存在会被幂等跳过（属预期）。
- **Pages 404**：确认 Pages Source 选的是 **GitHub Actions**，且 `pages.yml` 至少成功运行过一次。
