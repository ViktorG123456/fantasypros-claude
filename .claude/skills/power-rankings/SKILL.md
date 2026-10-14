---
name: power-rankings
description: League-wide power rankings for this ESPN league: each team's projected best-lineup strength vs actual scoring, schedule luck (points against), and an "is it panic time?" verdict. Use when the user asks who's best, who's lucky or unlucky, playoff outlook, or "should I panic".
---

# Power rankings and panic meter

League rules are in `CLAUDE.md`. If the user names a team, always show where it ranks.

## Script shortcut
`espn-venv/Scripts/python.exe -m espn_mcp.analyze rankings` (from the repo root) does steps 1–3 in one call: projected lineup, actual pts/week, gap, points-against rank, and a gap to 6th place (the script marks its default team; use the gap-to-6th column for whichever team the user asked about). Then add step 4 with `get_weekly_matchups`.

For **playoff outlook or panic questions**, also run `espn-venv/Scripts/python.exe -m espn_mcp.analyze playoffs --team "<team>"` (Monte Carlo, ~25 s). Report the **score** method's playoff % as the main number. Show slump and 50/50 next to it:
- 50/50 = what the current record alone implies.
- Score much lower than 50/50 = the roster is weaker than the record.
- Score much higher than 50/50 = the roster is better than the record.

Quote the 6th seed's average wins as the target, and use the crucial-games table to say which matchups swing the most.

## FantasyPros (second opinion)
**Always pass `scoring="PPR"`** on every FantasyPros call that takes a `scoring` parameter (`get_ecr`, `get_adp`, `get_player_comparisons`). The defaults are HALF or STD, which don't match this league's full PPR. For ECR, use `ranking_type="ROS"` for rest-of-season value, and keep rankings non-superflex (1-QB league). FantasyPros numbers are shown next to ESPN, never used in the script math (see `CLAUDE.md`).

## Steps
1. `get_league_info` and `get_standings`: record, points for, points against, current week.
2. Fetch **all 12** rosters in parallel. Build each team's best projected lineup (QB, RB×2, WR×2, TE, FLEX, K, D/ST by `projected_avg_points`, skipping OUT/IR) and sum it: **projected pts/week**.
3. Per team, compute:
   - **Actual points per week** = points for / games played.
   - **Gap to projection** = actual − projected. Large negative means likely to improve.
   - **Luck** = points-against rank. High points against with a poor record means unlucky.
4. `get_weekly_matchups` for the current week: live score and projections for each matchup.

## Output
- Table ranked by projected pts/week: rank | team | record | points for | points against | projected pts/week | actual pts/week.
- Short notes: who is better than their record, who is worse, and the biggest luck swings.
- **Gap to the playoff line:** projected pts/week needed to match the 6th-ranked team (or the actual playoff cutoff, if recorded in `CLAUDE.md`).

## Panic meter (for the team the user names)
Weigh:
- **Calm:** scoring well below projection (should improve), high points against (bad luck), strong core that's underperforming, only one game behind the pack.
- **Urgent:** projected pts/week in the bottom third, a clear gap to 6th place, likely losing this week.

Verdict: one of **No panic / Act now (not panic) / Panic**. Use the score method's playoff % as a guide: roughly ≥ 60% No panic, 25–60% Act now, < 25% Panic. Include:
- Moves to make now (waivers, realistic trades via `trade-evaluator`) and their projected effect on rank.
- What NOT to do (sell buy-low stars).
- A concrete checkpoint, e.g. "if 0–4 after Week 4, switch to high-variance consolidation trades."
