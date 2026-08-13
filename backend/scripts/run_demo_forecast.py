"""Run and persist one evidence-led end-to-end competition demo forecast."""

from __future__ import annotations

import asyncio
import json

from eufy_security_agents.api.dependencies import repository, workflow
from eufy_security_agents.domain.models import (
    ForecastRequest,
    ProductSelectionRequest,
    RunStatus,
)


async def main() -> None:
    request = ForecastRequest(
        question=(
            "预测未来三年美国与西欧家庭中，隐私优先、无强制订阅、能够从事后检测"
            "转向事前预防的 AI 原生 eufy Security 消费电子产品机会"
        ),
        forecast_horizon_years=3,
        regions=["United States", "Germany"],
        target_users=["Detached-home households", "Families with children or older adults"],
        price_segment="mid-to-premium",
        constraints=[
            "privacy-first",
            "no mandatory subscription",
            "manufacturable within three years",
            "must include meaningful consumer hardware",
        ],
        candidate_count=5,
    )
    run_id = workflow.create(request)
    print(json.dumps({"run_id": run_id, "status": "started"}, ensure_ascii=False), flush=True)
    await workflow.execute(run_id)
    result = workflow.get_result(run_id)
    if result.run.status != RunStatus.COMPLETED:
        raise RuntimeError(result.run.error or f"run stopped at {result.run.stage}")
    if len(result.lens_deliberations) != 4 or result.forecast_consensus is None:
        raise RuntimeError("deliberation or consensus output is incomplete")
    if not result.candidates:
        raise RuntimeError("no ranked candidates were produced")

    chosen = result.candidates[0]
    product = await workflow.define_selected_product(
        run_id,
        ProductSelectionRequest(
            candidate_id=chosen.candidate.id,
            selection_reason=(
                "选择综合排名最高且具备明确竞争差异和可证伪验证问题的方向，作为比赛端到端演示结果。"
            ),
            idempotency_key=f"demo-selection:{run_id}",
        ),
    )
    artifacts = repository.list_artifacts(run_id)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": result.run.status,
                "deliberations": len(result.lens_deliberations),
                "consensus_claims": len(result.forecast_consensus.consensus_claims),
                "unresolved_disagreements": len(result.forecast_consensus.unresolved_disagreements),
                "candidate_count": len(result.candidates),
                "ranked_candidates": [
                    {
                        "rank": item.rank,
                        "name": item.candidate.name,
                        "score": item.weighted_score,
                    }
                    for item in result.candidates
                ],
                "selected_product_id": product.id,
                "selected_product_name": product.name,
                "artifact_count": len(artifacts),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
