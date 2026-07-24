from runbookiq.domain.retrieval import RankedChunk


def reciprocal_rank_fusion(
    lexical: list[RankedChunk],
    vector: list[RankedChunk],
    *,
    rank_constant: int = 60,
) -> list[RankedChunk]:
    by_chunk_id: dict[str, RankedChunk] = {}
    rrf_scores: dict[str, float] = {}

    for channel, results in (("bm25", lexical), ("vector", vector)):
        for position, result in enumerate(results, start=1):
            chunk_id = result.chunk.id
            by_chunk_id.setdefault(chunk_id, result)
            component = by_chunk_id[chunk_id].component_scores
            component[channel] = round(result.score, 6)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1 / (
                rank_constant + position
            )

    ordered = sorted(
        by_chunk_id.values(),
        key=lambda item: (-rrf_scores[item.chunk.id], item.chunk.id),
    )
    return [
        item.model_copy(
            update={
                "rank": rank,
                "score": round(rrf_scores[item.chunk.id], 6),
                "component_scores": {
                    **item.component_scores,
                    "rrf": round(rrf_scores[item.chunk.id], 6),
                },
            }
        )
        for rank, item in enumerate(ordered, start=1)
    ]

