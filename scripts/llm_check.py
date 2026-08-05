"""验证 LLM API Key 配置是否可用的脚本：与模型做一次简单对话。

用法：
    .venv/Scripts/python.exe scripts/llm_check.py
    .venv/Scripts/python.exe scripts/llm_check.py "说一句问候语"

原理：复用项目的 config.yaml + .env（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），
直接向模型发起一次 chat.completions 请求。成功则打印回复，失败则给出定位提示。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiaggr.config import load_config, llm_settings
from aiaggr.llm import call_text

PROMPT = "请用一句话回复：你的 API Key 配置是有效的。输出简体中文。"


def main() -> int:
    cfg = load_config()
    settings = llm_settings(cfg)

    missing = [k for k in ("api_key", "base_url", "model") if not settings[k]]
    if missing:
        names = {
            "api_key": "LLM_API_KEY",
            "base_url": "LLM_BASE_URL",
            "model": "LLM_MODEL",
        }
        print(f"[失败] 缺少配置：{', '.join(names[k] for k in missing)}")
        print("  请在 .env 中补全后重试（参考 .env.example）。")
        return 2

    if settings["mock"]:
        print("[提示] 当前为 mock 模式（AGGR_MOCK_LLM=1 或 config.yaml llm.mock=true），不会真实调用模型。")
        print("  如需验证真实 Key，请先关闭 mock。")

    prompt = sys.argv[1] if len(sys.argv) > 1 else PROMPT
    print(f"模型: {settings['model']}")
    print(f"接口: {settings['base_url']}/chat/completions")
    print(f"对话: {prompt}")
    print("请求中 ...")

    try:
        reply = call_text(
            system="你是配置检查助手，回答要简短。",
            user=prompt,
            settings=settings,
            temperature=0.3,
        )
    except Exception as err:
        print("[失败] 调用出错：")
        print(f"  {err}")
        hint = str(err).lower()
        if "401" in hint or "unauthorized" in hint or "api key" in hint:
            print("  提示：API Key 无效或无权访问该模型，请检查 LLM_API_KEY / LLM_MODEL。")
        elif "404" in hint or "not found" in hint:
            print("  提示：接口路径或模型名不对，请检查 LLM_BASE_URL（需指向 .../v4 一级）与 LLM_MODEL。")
        elif "timeout" in hint or "timed out" in hint:
            print("  提示：网络超时，请检查网络或 LLM_BASE_URL 可达性。")
        else:
            print("  提示：检查 LLM_BASE_URL / LLM_MODEL 是否与所选服务商一致。")
        return 1

    if not reply:
        print("[失败] 模型返回空内容。")
        return 1

    print("=== 回复 ===")
    print(reply)
    print("=== 配置验证成功 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
