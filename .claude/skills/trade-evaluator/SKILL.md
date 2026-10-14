---
name: trade-evaluator
description: Evaluate or propose fantasy football trades in this ESPN league with lineup-delta math, 2-for-1 break-even, sell-high/buy-low signals and a realism check on the partner's side. Use when the user asks "is this trade good", "what can I get for X", "who should I trade for", or compares trade offers.
---

# Trade evaluator

League rules (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 D/ST, 1 K; full PPR; 1-QB league) are in `CLAUDE.md`. Evaluate from the side of the team the user names, and refer to teams by name, never as "us" or "we".

## 0. Use the script for the math
Run from the repo root. It does steps 2, 3 and 5 exactly:
```
espn-venv/Scripts/python.exe -m espn_mcp.analyze trade "<team>" --give "Tate,Burden" --partner Mayeday --get "Higgins"
espn-venv/Scripts/python.exe -m espn_mcp.analyze screen "<team>" [--partner "<team>"]
espn-venv/Scripts/python.exe -m espn_mcp.analyze breakeven "Right to Dream" --give "Adams,Judkins"
```
Player names match by substring within each team's roster. **To find trades, start with `screen`**: it tries every 1-for-1 up to 2-for-2 and applies the need, roster-limit, VORP and acceptance rules below. Then check the best ones with `trade`. Use the MCP tools for everything else, such as free agents, injuries and schedules.

## FantasyPros (second opinion)
**Always pass `scoring="PPR"`** on every FantasyPros call that takes a `scoring` parameter (`get_ecr`, `get_adp`, `get_player_comparisons`). The defaults are HALF or STD, which don't match this league's full PPR. For ECR, use `ranking_type="ROS"` for rest-of-season value, and keep rankings non-superflex (1-QB league). FantasyPros numbers are shown next to ESPN, never used in the script math (see `CLAUDE.md`).

## 1. Gather data
- `get_team_roster` for **both** teams in the trade. To find partners, fetch all 12 rosters (in parallel).
- Per player, use `projected_avg_points` (rest-of-season per game, "proj"), `season_avg_points` (actual so far) and `projected_total_points` (rest-of-season total), plus `injury_status`.
- Check `get_free_agents` at the relevant position when a trade opens a hole or a roster spot.

## 2. Build the best lineup before and after
For each team, fill QB, RB×2, WR×2, TE, FLEX (best remaining RB/WR/TE), K and D/ST by highest proj. Skip OUT/IR players. Bench players are worth **0**, except the first backup at RB, WR and TE, who counts at 10% (the script's "Value/wk").

**Trade value = (new lineup proj) − (old lineup proj)**, per week. Also compute the season change using `projected_total_points`.

## 3. Shortcuts
- **2-for-1 break-even:** giving A + B for X is only a gain if `proj(X) > proj(A) + proj(B) − proj(best bench player who moves in)`. State this number explicitly (e.g. "the incoming player must project above 16.0").
- **Consolidating bench depth:** bench-for-starter deals cost almost nothing. For example, giving two bench WRs for one WR who projects above the current FLEX is nearly a pure gain.
- **Same-slot 1-for-1:** gain = proj(in) − proj(out). If players shift slots (e.g. an incoming RB pushes the old RB2 into FLEX), recompute the whole lineup.

## 4. Sell high / buy low
Gap = actual points per game − projected points per game.
- Gap ≥ +5: **sell high**. Other managers see the inflated actual points.
- Gap ≤ −5 **and** actual ≤ 70% of projected: **buy low** target; the evaluated team shouldn't sell its own players like this. The script's `BUY LOW` flag applies both rules.
- A buy-low only works if the manager has lost faith in the player. A star still putting up starter numbers (e.g. a projected WR1 at 14.9 vs 20.2) is not discounted by anyone, so don't list him even if the gap is large. When ranking targets, prefer the worst box scores relative to projection, and teams likely to be frustrated (losing record, high points against).
- A 0.0 actual next to an injury status means missed games, not a slump. Treat it as an injury discount and check the injury news before calling it a buy.
- Don't sell a player right after a slow start (value at its lowest) unless it's part of a larger upgrade.
- **Draft pedigree counts.** Managers still value an early pick who is slumping (e.g. Chase Brown, drafted RB6) and discount a late pick running hot (e.g. Hubbard, RB33). The script's market value blends the projection with the draft slot; a `SELLS LOW` warning means the evaluated team gives away more than 2.0 of market value. Don't recommend those as main options.

## 5. Realism check (required)
The script's acceptance rating does this; read its reasons, don't just copy the label.
- **The partner must start what it gets.** A player who lands on their bench is worth ~0 to them (only the first backup per position counts, at 10%). If they're SURPLUS at that position (4+ WRs/RBs or 3+ TEs projecting 10+), they don't want him.
- **Roster spots:** 15 active + 3 IR. A team taking more players than it sends must drop someone. The script shows who.
- **2-for-1s:** the team getting two players must gain market value, not just total projection. Two average players are worth less than one starter.
- **A change of 0 is not a yes.** The partner needs a reason: a lineup gain, a filled hole or a better-looking box score.
- **Low** = starts none of the incoming players, value change below −3/wk, or VORP below −3.
- **Also consider how it looks to them:** compare the actual points per game they give up with what they get. Managers often judge by actual points, so a trade that loses on projections but looks like a win on actual points can still be accepted.
- Label each proposal's likelihood of acceptance: High / Medium / Low. Low ones go in a "long shot" section, never as the main recommendation.

## 6. Risk checks
- Injury status of every player involved (QUESTIONABLE / DOUBTFUL / OUT).
- Games left (`projected_total_points / projected_avg_points`). Fewer than about 12 signals expected missed time.
- **Depth after the trade:** does it leave a position with no bench cover (e.g. RB3 projected under 8)?
- Two trade ideas that use the same player can't both happen; say so.

## 7. Output format
1. One-line verdict.
2. A table per option: players in/out, actual points per game, projected points per game, **change per week**, **change for the season**, chance they accept.
3. Why it works for the evaluated team / why the partner says yes (with numbers).
4. Final ranking plus the order to make offers, and a "don't do" list.
5. State assumptions (e.g. "free-agent projections are for this week only").
