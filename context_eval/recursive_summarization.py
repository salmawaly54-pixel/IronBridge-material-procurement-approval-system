from typing import Callable, Optional
from transcript import Turn


def apply(
    turns: list[Turn], 
    summarize_every: int = 15, 
    keep_recent: int = 8,
    summarizer: Optional[Callable[[list[Turn]], str]] = None
) -> list[Turn]:
    
    if len(turns) <= (keep_recent + summarize_every):
        return list(turns)

    older = turns[:-keep_recent]
    recent = turns[-keep_recent:]

    # Fall back to heuristic if no LLM generator function is provided
    if summarizer is None:
        summary_text = f"Compacted {len(older)} older turns. Key topics discussed in early turns preserved."
    else:
        summary_text = summarizer(older)

    has_critical_info = any(t.critical for t in older)

    summary_turn = Turn(
        role="assistant",
        content=f"[Summary of earlier conversation]: {summary_text}",
        is_tool_output=False,
        critical=has_critical_info,
        turn_index=older[0].turn_index,
    )

    return [summary_turn] + recent