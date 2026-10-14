# Fantasy football — agent instructions

## Perspective
Analyze from the point of view of the team the user names. Refer to teams by name, never as "us", "we" or "our". If a request doesn't make clear which team's side to take, ask.

## Git workflow
- **Never commit directly to `main`.** Before changing any file, create a branch from an up-to-date `main` (e.g. `git switch -c feature/<short-name>`), and commit the work there.
- **Ask the user before anything reaches `main`**, whether by merge, push or pull request: show what will land (branch, commits, a short diff summary) and wait for an explicit yes. Approval covers only that one merge or push.
- Never force-push, and never commit `.env` or other credentials.

## League: Fantasifotbollsligan
- 12 teams on ESPN.
- **6 playoff teams, 14-game regular season**, trade deadline 2026-12-09.
- **Roster:** 9 starters + 6 bench = 15 active, plus 3 IR slots.
- **The user's team is Game Of Mahomes** (ESPN team id 5). "My team" means Game Of Mahomes.
- Unknown (ask the user, then record here): waiver type (FAAB or priority).

## Data source: FantasyPros MCP (`.mcp.json`)
`fantasypros` is a remote HTTP server (sign in once via `/mcp` → FantasyPros in a terminal). It gives expert consensus from across the industry plus this league's synced rosters and power rankings.

- **League key:** `nfl~d833b763-76ec-46fb-9161-749144157ea8`. The server is stateless: pass `league_key` on every league-scoped call.
- The account is on the **free plan** (checked 2026-10-14).

| Tool | Status | Use it for |
|---|---|---|
| `get_leagues` | ✅ | League key and the user's team |
| `get_roster` | ✅ | Live rosters: own team (default), `team_name` / `team_id`, or `all_teams=true` |
| `league_analyzer` | ✅ | Power rankings, position ranks per team, projected record, playoff odds (`period`: `ros`, `week`, `dyn`, `draft`) |
| `rank_trade_partners` | ✅ | Teams ranked by fit for a position swap (`position_surplus`, `position_need`) |
| `get_player_comparisons` | ✅ | 2–4 players: ROS position rank, season avg, projected avg per game, expert picks |
| `get_ecr` | ✅ | Expert consensus rankings (`ranking_type` `ROS`/`WEEKLY`, `scoring="PPR"`) |
| `get_projections` | ✅ | ROS or weekly projections; use the `points_ppr` field (the default `points` is standard scoring) |
| `trade_analyzer`, `trade_finder`, `waiver_finder`, `start_sit_assistant` | ❌ Premium | Not in the plan. Do the analysis with the tools above instead |

Other tools (`get_player_stats`, `injury_status`, `get_nfl_depth_charts`, `get_schedule_and_strength`, `get_adp`, `get_league_settings`, `matchup_analyzer`, `get_player_ownership`, `get_leaders`) are untested. Record their status here once tried.

Rules:
- **League facts come from `get_roster` and `league_analyzer`**: who owns whom and position strength. There's no free-agent tool on this plan, so a player is only a free agent if he's on no team in `get_roster(all_teams=true)`. Ask the user about records and scores if a tool doesn't return them.
- Use **PPR** rankings (full-PPR league) and **non-superflex** rankings (1-QB league). Pass `scoring="PPR"` explicitly; several tools default to half-PPR or standard.
- If the FantasyPros tools don't load, the sign-in has expired or wasn't done. Say so; don't guess expert rankings.
- When a tool returns `premium_required`, tell the user once that it isn't in their plan, then answer with the tools that are.

## Scoring
**Full PPR** (1 point per reception). Pass-catching RBs and high-volume WRs/TEs gain value; early-down-only RBs lose value.

## Lineup
Starting lineup is **1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K**.

- This is a **1-QB league — not superflex.**
- Only one QB scores per week, so backup QBs have little value. Don't recommend trading for a QB unless the team's starting QB is out long-term with no adequate replacement.
- When valuing trades or lineups, count 7 skill starters (2 RB, 2 WR, 1 TE, 1 FLEX) plus QB, K and D/ST; everyone else is bench.

## How to answer
- Back every recommendation with data, in tables.
- End with a clear ranking or recommendation, not an open-ended survey.
- **Realistic trades only.** Check the other team's side as well: would they start what they get, and do they lose value?
- Include a short "don't do" list when relevant (e.g. selling a star at his lowest value).

## Skills (`.claude/skills/`)
- `trade-analyzer`: evaluate a proposed trade, or find realistic trades for a team, using the free-plan tools above.
