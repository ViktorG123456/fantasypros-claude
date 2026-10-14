---
name: team-analysis
description: Full breakdown of one team in this ESPN league (position ranks vs the league, strengths, weaknesses, over/underperformers, waiver fixes, realistic trades). Use when the user asks to "analyze <team>", "what are my weaknesses", or "how good is <team>".
---

# Team analysis

League rules are in `CLAUDE.md`. Analyze the team the user names, and refer to it by name, never as "us" or "we".

## Script shortcuts (run from the repo root)
- `espn-venv/Scripts/python.exe -m espn_mcp.analyze team "<team>"`: best lineup, actual vs projected, gap, sell-high/buy-low flag and games left (steps 3, 5, 6)
- `espn-venv/Scripts/python.exe -m espn_mcp.analyze rankings`: every team's lineup total, for league context
- Position-by-position ranks (step 4) still come from the rosters: `analyze team` for each team, or `get_team_roster`.

## FantasyPros (second opinion)
**Always pass `scoring="PPR"`** on every FantasyPros call that takes a `scoring` parameter (`get_ecr`, `get_adp`, `get_player_comparisons`). The defaults are HALF or STD, which don't match this league's full PPR. For ECR, use `ranking_type="ROS"` for rest-of-season value, and keep rankings non-superflex (1-QB league). FantasyPros numbers are shown next to ESPN, never used in the script math (see `CLAUDE.md`).

## Steps
1. **Context:** `get_league_info` (record, points for/against, current week) and `get_weekly_matchups` (this week's score and projection).
2. **Rosters:** fetch **all 12** rosters in parallel. League ranks need every team.
3. **Best lineup per team:** QB, RB×2, WR×2, TE, FLEX, K, D/ST by `projected_avg_points`, skipping OUT/IR. Sum it to get the team's weekly strength.
4. **Position ranks:** rank the target team among the 12 teams' starters for QB, RB1+RB2, WR1+WR2, TE, FLEX, K and D/ST. Note bench depth, e.g. "best RB3 in the league" or "no RB cover".
5. **Over/underperformance table:** for every relevant player, actual pts/game vs projected, and the gap. Flag sell-high (gap ≥ +5) and buy-low (gap ≤ −5 and actual ≤ 70% of projected, so the manager has actually soured on him; see `trade-evaluator` §4).
6. **Injuries and missed time:** injury status plus games left (`projected_total_points / projected_avg_points`).
7. **Waivers first (free):** `get_free_agents` for the weakest positions (often D/ST, TE, RB depth). Remember these are this week's projections only.
8. **Trades:** 1–3 realistic proposals, priced with the `trade-evaluator` skill. Trade from surplus (e.g. deep RBs or bench WRs) into the weakest starting slot.
9. **Don't do:** e.g. don't sell buy-low stars, don't take on a backup QB, don't strip the last cover at a position.

## Output format
- Header: record, points for (rank), points against (rank), this week's matchup.
- One-line summary of what kind of team this is.
- Position table: slot | starter(s) | projected pts/game | league rank.
- Over/underperformer table.
- Strengths / weaknesses as bullets, each backed by a number.
- Waiver pickups table: drop | add | why.
- Trade proposals (table per trade: gives / gets, actual, projected, change for the analyzed team, change for partner).
- Combined effect: projected pts/week before and after all proposed moves.
- "Don't do" list and a bottom-line recommendation.
