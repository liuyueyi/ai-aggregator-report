from __future__ import annotations

import httpx

from .base import BaseFetcher, Signal, normalize_score


class HuggingFaceFetcher(BaseFetcher):
    """HF 7 日点赞排序的模型 + 数据集。"""

    source_key = "huggingface"
    source_name = "HuggingFace"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 12))
        signals: list[Signal] = []

        try:
            resp = await client.get(
                "https://huggingface.co/api/models",
                params={"sort": "likes7d", "direction": -1, "limit": limit},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            for m in resp.json():
                likes = m.get("likes", 0)
                model_id = m.get("modelId") or m.get("id", "")
                signals.append(
                    Signal(
                        source="HuggingFace Models",
                        source_key="huggingface",
                        title=model_id,
                        url=f"https://huggingface.co/{model_id}",
                        raw_score=likes,
                        score=normalize_score(likes, 500.0),
                        tags=m.get("tags", [])[:5],
                        published_at=m.get("lastModified") or m.get("createdAt"),
                    )
                )
        except Exception as e:
            print(f"[HuggingFace models] {e}")

        try:
            resp = await client.get(
                "https://huggingface.co/api/datasets",
                params={"sort": "likes7d", "direction": -1, "limit": max(5, limit // 2)},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            for d in resp.json():
                likes = d.get("likes", 0)
                ds_id = d.get("id", "")
                signals.append(
                    Signal(
                        source="HuggingFace Datasets",
                        source_key="huggingface",
                        title=ds_id,
                        url=f"https://huggingface.co/datasets/{ds_id}",
                        raw_score=likes,
                        score=normalize_score(likes, 200.0),
                        tags=d.get("tags", [])[:3],
                        published_at=d.get("lastModified") or d.get("createdAt"),
                    )
                )
        except Exception as e:
            print(f"[HuggingFace datasets] {e}")

        return signals
