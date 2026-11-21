def rrf(rank_lists: list[list[str]], alpha: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum_i 1 / (alpha + rank_i(d)), rank starting at 1."""
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for r, d in enumerate(lst, start=1):
            scores[d] = scores.get(d, 0.0) + 1.0 / (alpha + r)
    return sorted(scores.items(), key=lambda x: -x[1])
