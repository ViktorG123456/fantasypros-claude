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
- Unknown (ask the user, then record here): waiver type (FAAB or priority).

## Data source: FantasyPros MCP (`.mcp.json`)
`fantasypros` is a remote HTTP server (sign in once via `/mcp` → FantasyPros in a terminal). It gives expert consensus from across the industry: expert consensus rankings (ECR), rest-of-season rankings, start/sit, and trade and waiver views.

Rules:
- **FantasyPros doesn't know this league.** It can't tell who owns whom, who is a free agent, records or scores. Ask the user for rosters and league facts instead of guessing.
- Use **PPR** rankings (full-PPR league) and **non-superflex** rankings (1-QB league).
- If the FantasyPros tools don't load, the sign-in has expired or wasn't done. Say so; don't guess expert rankings.
- Once the FantasyPros tool list has been checked, record the tool names here.

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
