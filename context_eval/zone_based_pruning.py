from transcript import Turn
def apply(
    turns: list[Turn], 
    anchor_turns: int = 4, 
    recent_turns: int = 8
) -> list[Turn]:
    """
    Strategy 4: Zone-Based Pruning.
    Segments the transcript into 4 functional zones:
      - Zone 1 (Anchor): System header/early turns kept verbatim.
      - Zone 2 (Light Pruning): Middle-older turns with tool output masking.
      - Zone 3 (Aggressive Compression): Middle-newer routine tools collapsed into 
        a single summary turn; critical turns are preserved verbatim.
      - Zone 4 (Recent History): Recent tail end kept verbatim.
    """
    n = len(turns)
    if n <= anchor_turns + recent_turns:
        return list(turns)

    # 1. Slice zones
    zone1 = turns[:anchor_turns]
    zone4 = turns[-recent_turns:]
    middle = turns[anchor_turns:-recent_turns]

    midpoint = len(middle) // 2
    zone2_raw = middle[:midpoint]
    zone3_raw = middle[midpoint:]

    # 2. Zone 2: Mask tool outputs
    zone2: list[Turn] = []
    for t in zone2_raw:
        if t.is_tool_output:
            zone2.append(
                Turn(
                    role=t.role,
                    content="[tool output omitted]",
                    is_tool_output=True,
                    critical=t.critical,
                    turn_index=t.turn_index,
                )
            )
        else:
            zone2.append(t)

    # 3. Zone 3: Isolate non-critical tool outputs to avoid double-counting
    non_critical_tool_count = sum(
        1 for t in zone3_raw if t.is_tool_output and not t.critical
    )
    
    # Retain all critical turns (even tool outputs) verbatim
    zone3: list[Turn] = [t for t in zone3_raw if t.critical]

    # Append a single summary turn for non-critical routine tools
    if non_critical_tool_count > 0:
        fallback_index = zone3_raw[0].turn_index if zone3_raw else 0
        zone3.append(
            Turn(
                role="assistant",
                content=f"[{non_critical_tool_count} routine tool checks omitted]",
                is_tool_output=False,
                turn_index=fallback_index,
            )
        )

    # 4. Assemble final pruned transcript
    return zone1 + zone2 + zone3 + zone4