# ESPN Fantasy — agent instructions

## Perspective
Analyze from the point of view of the team the user names. Refer to teams by name, never as "us", "we" or "our". If a request doesn't make clear which team's side to take, ask.

## Git workflow
- **Never commit directly to `main`.** Before changing any file, create a branch from an up-to-date `main` (e.g. `git switch -c feature/<short-name>`), and commit the work there.
- **Ask the user before anything reaches `main`**, whether by merge, push or pull request: show what will land (branch, commits, a short diff summary) and wait for an explicit yes. Approval covers only that one merge or push.
- Never force-push, and never commit `.env` or other credentials.

## League: Fantasifotbollsligan
- 12 teams, ESPN, league id/credentials fixed server-side in `.env`. Call `get_league_info` first for the current week and records.
- **6 playoff teams, 14-game regular season** (same every season 2022–2026), trade deadline 2026-12-09 (from ESPN settings).
- **Roster:** 9 starters + 6 bench = 15 active, plus 3 IR slots.
- Unknown (ask the user, then record here): waiver type (FAAB or priority).
- **League history:** use the `get_league_history` tool (seasons 2022–2025: final rank, seed, record, PF/PA, plus all-time totals per franchise). ESPN returns no owners, weekly matchups or playoff W-L for past seasons, so franchises are grouped by ESPN team id (stable across renames) and labelled with the current manager. Team id 8 (champion in 2024 as Svenska Landslaget) left the league before 2026.

## Data sources (two MCP servers, both in `.mcp.json`)
| Server | What it is | Use it for |
|---|---|---|
| `espn-fantasy-football` (local, `espn_mcp/`) | This league's own data. Credentials are in `.env`. | **Everything league-specific:** teams, rosters, records, schedule, matchups, free agents in *this* league, league history. ESPN projections are already in league scoring (full PPR). |
| `fantasypros` (remote HTTP; sign in once via `/mcp` → FantasyPros in a terminal) | Expert consensus from across the industry, not tied to this league | **A second opinion on player value:** expert consensus rankings (ECR), rest-of-season rankings, start/sit, and trade and waiver views. |

Rules:
- **League facts come only from ESPN.** Who owns whom, who is a free agent, records and scores. FantasyPros doesn't know this league, so never use it to decide whether a player is available.
- **Lineup, trade and playoff math uses ESPN projections**, through the `analyze` script and `playoff_sim`. FantasyPros numbers never go into those calculations.
- **Show FantasyPros next to ESPN as a second opinion** when judging player value (trades, sell-high/buy-low, waivers). Use **PPR** rankings, matching the league's full-PPR scoring. Use **non-superflex** rankings (1-QB league). Flag big disagreements, e.g. a player ESPN projects as a WR2 but experts rank as a WR4. Those point to stale ESPN projections (as with Achane's ACL) or to trade leverage.
- If the FantasyPros tools don't load, the sign-in has expired or wasn't done. Say so and carry on with ESPN only. Don't guess expert rankings.
- The skills in `.claude/skills/` don't call FantasyPros yet. Wire them in once its tool list has been checked, and record the tool names here.

## Scoring
**Full PPR** (1 point per reception), verified from ESPN projection breakdowns. The ESPN tools already return points in league scoring, so use them as-is. Pass-catching RBs and high-volume WRs/TEs gain value; early-down-only RBs lose value.

## Lineup
Starting lineup is **1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K**.

- This is a **1-QB league — not superflex.** Ignore the "OP" slot in ESPN's `eligible_slots` data; it is not a starting slot here.
- Only one QB scores per week, so backup QBs have little value. Don't recommend trading for a QB unless the team's starting QB is out long-term with no adequate replacement.
- When valuing trades or lineups, count 7 skill starters (2 RB, 2 WR, 1 TE, 1 FLEX) plus QB, K and D/ST; everyone else is bench.

## Reading the ESPN data
- `season_avg_points` = actual points per game so far. `projected_avg_points` = ESPN's rest-of-season projection per game. `projected_total_points` = rest-of-season total.
- `projected_total_points / projected_avg_points` ≈ games ESPN expects the player to play. A low number flags expected missed time (injury, suspension, bye).
- `get_free_agents` returns **this week's** projection only, not a rest-of-season average. Label it when comparing a free agent to a rostered player's per-game projection.
- Early in the season, actual points come from a tiny sample. Weight projections over actuals, and use the gap between them to find sell-high and buy-low players.
- Players listed OUT or INJURY_RESERVE are excluded from best-lineup calculations.

## How to answer
- Back every recommendation with data, in tables: actual points per game, projected points per game, and the change per week and for the season.
- End with a clear ranking or recommendation, not an open-ended survey.
- **Realistic trades only.** Check the other team's side as well, as described in the `trade-evaluator` skill.
- Include a short "don't do" list when relevant (e.g. selling a star at his lowest value).
- **Use the analysis script for lineup and trade math** instead of adding numbers by hand (run from the repo root; add `--json` for machine output):
  - `espn-venv/Scripts/python.exe -m espn_mcp.analyze rankings`: every team's best projected lineup, actual pts/week, points-against rank, gap to 6th place
  - `... analyze team "<team>"`: best lineup plus actual vs projected, sell-high/buy-low flags and games left per player (always pass the team name)
  - `... analyze trade "<team>" --give "A,B" --partner "<team>" --get "X"`: for **both** teams: lineup change per week and rest of season, value change (lineup + 10% of the first bench backup at RB/WR/TE), market value balance (projection + draft pedigree) with a sells-low warning, forced roster drops, position need, and a chance of acceptance with reasons
  - `... analyze screen "<team>" [--partner "<team>"]`: searches every 1-for-1 up to 2-for-2 RB/WR/TE trade and lists the best ones the partner isn't likely to reject (about 30 s). Options: `--min-gain`, `--max-players`, `--top`, `--include-low`
  - `... analyze breakeven "<team>" --give "A,B"`: the projection one incoming RB/WR/TE must beat
  - `... analyze playoffs [--team "<team>"]`: Monte Carlo playoff odds (10,000 runs) with three methods side by side: **score** (main one), **slump** and **50/50**. Shows playoff %, top-2 %, seed 1 % and average wins, plus the average wins of the 6th seed. `--team` adds each remaining game's playoff % if the team wins vs loses. Other options: `--method`, `--sims`, `--prior-games` (default 5), `--slump`, `--seed`. It takes about 25 s with `--team`.
  - Trade model (tunable constants at the top of `analysis.py`):
    - **Position need:** players projecting 10+ at RB/WR/TE vs starting slots (2/2/1): fewer = NEED, equal = THIN, +1 = OK, +2 or more = SURPLUS. A stacked team doesn't want another player there.
    - **Bench value:** only the first backup at RB, WR and TE counts, at 10%. Other bench players are worth 0; they only take a roster spot.
    - **Roster limit:** a team taking more players than it sends drops its lowest-projected non-starters (IR = ESPN's IR slot, max 3).
    - **VORP:** projection minus replacement level (30th RB/WR, 13th TE among rostered players). Two average players add up to little, so the team getting two players for one must gain market value.
    - **Market value (draft pedigree):** how managers price a player = blend of ESPN projection and his draft slot in this league (drafted RB6 -> worth today's RB6 projection; undrafted -> replacement level). Projection share = games/(games+4): 43% after 3 games, 71% after 10. Market value = market projection minus replacement. Keeps a slumping early pick (Chase Brown, RB6) from being sold for a hot late pick (Hubbard, RB33).
    - **Sells low:** the evaluated team gives away more than 2.0 of market value. `trade` prints a warning; `screen` hides these unless `--include-low`.
    - **Acceptance:** Low if the partner starts none of what it gets, loses more than 3/wk of value, or more than 3 of market value. High if it gains value, starts an incoming player and loses at most 0.5 market value. Otherwise Medium.
  - Tests: `espn-venv/Scripts/python.exe -m unittest discover tests`.
  - Math lives in `espn_mcp/analysis.py` (pure functions); the CLI is `espn_mcp/analyze.py`. The playoff simulation is in `playoff_sim/`: `simulation.py` is pure stdlib, `data.py` loads from ESPN.
  - The playoff sim uses **current rosters**. A team's expected score blends its projected lineup with its actual average, weighting actual by games/(games+5). Pending trades and pickups aren't modelled, so re-run after roster moves.
- Skills in `.claude/skills/`: `trade-evaluator` (price any trade), `team-analysis` (full breakdown of one team), `power-rankings` (league-wide projected strength, luck, "is it panic time?").
