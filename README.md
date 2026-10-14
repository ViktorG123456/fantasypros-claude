# ESPN Fantasy Football assistant

Ask an AI questions about your ESPN Fantasy Football league and get answers backed by real data:

- *"Should I trade Chase Brown for Judkins and Adams?"*
- *"Which free agents should I pick up?"*
- *"Find me a running back I can realistically trade for."*
- *"What are my playoff odds?"*

The AI reads your league straight from ESPN (rosters, records, free agents, matchups). It runs the lineup and trade math with a script instead of guessing, and it checks industry expert rankings from FantasyPros as a second opinion.

It was built for the league **Fantasifotbollsligan** (12 teams, full PPR, 1 QB) but works with any ESPN league.

---

## Quick start (the easy way)

You need three things installed:

1. **[Git](https://git-scm.com/downloads)**, to download this project
2. **[Python 3.10 or newer](https://www.python.org/downloads/)**. On Windows, tick *"Add python.exe to PATH"* during install.
3. **[Claude Code](https://claude.com/claude-code)**, the AI that does the work. Use the desktop app or the terminal version.

Then:

**Step 1: Download the project.** Open a terminal and run:

```bash
git clone https://github.com/ViktorG123456/mcp-fantasy-fotball.git
```

**Step 2: Open the folder in Claude Code.** In the desktop app, pick the `mcp-fantasy-fotball` folder. In a terminal, run `cd mcp-fantasy-fotball` and then `claude`.

**Step 3: Paste this prompt**, with your team name filled in:

> Set up this project for me. I'm not a programmer, so explain each step simply.
>
> 1. Create a Python virtual environment called `espn-venv` in this folder and install `requirements.txt` into it.
> 2. Copy `.env.example` to `.env`. Walk me through finding my ESPN league ID and my `ESPN_S2` and `SWID` cookies. Don't ask me to paste the cookies into the chat; tell me where in `.env` to put them myself.
> 3. If I'm on Mac or Linux, change the `command` in `.mcp.json` to `espn-venv/bin/python`.
> 4. Run the unit tests, then run `analyze rankings` to check that the league loads.
> 5. Tell me how to restart so the ESPN and FantasyPros tools load, and how to sign in to FantasyPros.
>
> My team is called "YOUR TEAM NAME".

**If your league isn't Fantasifotbollsligan**, add this to the prompt:

> My league is a different ESPN league. After setup, call `get_league_info` and update the league section of `CLAUDE.md` (teams, roster slots, scoring, playoff spots) to match my league.

**Step 4: Restart Claude Code** so the ESPN tools load, then ask something like:

> Analyze my team "YOUR TEAM NAME". What are its weaknesses, and which trades or free agents fix them?

The AI always answers from the point of view of the team you name, so include your team name in questions.

---

## Finding your ESPN details

These go in the `.env` file. The AI will help you, but this is where they are:

| Setting | Where to find it |
|---|---|
| `LEAGUE_ID` | Open your league on fantasy.espn.com. It's the number after `leagueId=` in the address bar. |
| `YEAR` | The season, e.g. `2026`. |
| `ESPN_S2` and `SWID` | **Private leagues only.** These are login cookies. Log in to fantasy.espn.com in Chrome or Edge, press **F12**, open the **Application** tab, go to **Cookies → https://fantasy.espn.com**, and copy the values of `espn_s2` and `SWID`. |

> ⚠️ **Keep `.env` private.** Your cookies work like a password to your ESPN account. The file is already excluded from git, so don't share it, post it or paste its contents anywhere.

---

## Manual setup (without the AI)

**Windows:**

```bash
python -m venv espn-venv
espn-venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
```

**Mac / Linux:**

```bash
python3 -m venv espn-venv
espn-venv/bin/pip install -r requirements.txt
cp .env.example .env
```

On Mac or Linux, also change `"command"` in `.mcp.json` to `"espn-venv/bin/python"`.

Fill in `.env` (see the table above), then check that it works:

```bash
espn-venv\Scripts\python.exe -m espn_mcp.analyze rankings
```

On Mac or Linux, replace `espn-venv\Scripts\python.exe` with `espn-venv/bin/python` here and in every command below.

To use FantasyPros expert rankings, run `claude` in a terminal inside the folder, type `/mcp`, choose **fantasypros** and sign in. Everything still works without it, just without the expert second opinion.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `LEAGUE_ID and YEAR must be set` | `.env` is missing or empty. Copy `.env.example` to `.env` and fill it in. |
| ESPN returns an access error | The league is private and `ESPN_S2`/`SWID` are missing or expired. Copy fresh cookies from the browser. |
| The AI says it has no ESPN tools | Restart Claude Code in this folder. Check that `espn-venv` exists and that the `command` path in `.mcp.json` matches your system. |
| FantasyPros tools missing | The sign-in has expired or was never done. Run `/mcp` in a terminal and sign in again. |
| `python` not found | Reinstall Python and tick *"Add python.exe to PATH"*, or use `py` instead of `python` on Windows. |

---

## What's inside (for the curious)

```
mcp-fantasy-fotball/
├── espn_mcp/              ESPN data server + analysis command line
│   ├── league.py          talks to ESPN (via the espn_api library)
│   ├── server.py          the MCP server that gives the AI its ESPN tools
│   ├── analysis.py        lineup and trade math (no network)
│   └── analyze.py         command line: rankings, team, trade, screen, breakeven, playoffs
├── playoff_sim/           Monte Carlo playoff odds
├── tests/                 unit tests
├── .claude/skills/        ready-made AI workflows: trades, team analysis, power rankings
├── .mcp.json              tells Claude Code which data servers to start
├── CLAUDE.md              league rules and how the AI should answer
├── .env.example           template for your private settings
└── requirements.txt       Python packages
```

### Data sources

| Server | What it is | Used for |
|---|---|---|
| `espn-fantasy-football` | Runs on your computer, from `espn_mcp/` | Everything about your league: teams, rosters, records, free agents, history |
| `fantasypros` | Online service | Expert consensus rankings as a second opinion. Never used to decide who is available in your league. |

### ESPN tools the AI can use

| Tool | Returns |
|---|---|
| `get_league_info` | League name, current week, every team's record and owners |
| `get_standings` | Ranked standings |
| `get_weekly_matchups(week?)` | Every matchup for a week: opponent, score, projection |
| `get_team_schedule(team_name)` | One team's season schedule and results |
| `get_team_roster(team_name)` | Roster with actual and rest-of-season projected points per player |
| `get_player_info(player_name)` | Bio, ownership, injury status, season totals |
| `get_player_weekly_projection(player_name, week)` | One player's projected or actual stat line for a week |
| `get_free_agents(week?, position?, size?)` | Best available players, with this week's projection |
| `get_draft_rankings(size?, rank_type?)` | ESPN's pre-draft rankings |
| `get_league_history` | Final standings for past seasons, plus all-time totals per franchise |

Team names match on part of the name, ignoring case. Player names must match ESPN's spelling. Your credentials stay in `.env` and are never sent to the AI.

### Analysis command line

The AI runs these for you, but you can also run them yourself from the project folder. Put your own team name in the quotes:

```bash
espn-venv\Scripts\python.exe -m espn_mcp.analyze rankings
espn-venv\Scripts\python.exe -m espn_mcp.analyze team "Game Of Mahomes"
espn-venv\Scripts\python.exe -m espn_mcp.analyze trade "Game Of Mahomes" --give "Tate,Burden" --partner Mayeday --get "Higgins"
espn-venv\Scripts\python.exe -m espn_mcp.analyze screen "Game Of Mahomes"
espn-venv\Scripts\python.exe -m espn_mcp.analyze breakeven "Game Of Mahomes" --give "Tate,Burden"
espn-venv\Scripts\python.exe -m espn_mcp.analyze playoffs --team "Game Of Mahomes"
```

| Command | What it does |
|---|---|
| `rankings` | Every team's best projected lineup, actual points per week, schedule luck and gap to the last playoff spot |
| `team` | Best lineup, actual vs projected points, sell-high/buy-low flags, games left |
| `trade` | For **both** teams: lineup change, market value, forced roster drops, position need, and how likely the other team is to accept |
| `screen` | Tries every 1-for-1 up to 2-for-2 trade and lists the best realistic ones (about 30 seconds) |
| `breakeven` | How good one incoming player must be for a 2-for-1 to pay off |
| `playoffs` | Playoff odds from 10,000 simulated seasons. `--team` shows how much each remaining game matters. About 25 seconds. |

Add `--json` right after `analyze` (e.g. `analyze --json rankings`) for machine-readable output. The playoff sim uses current rosters, so re-run it after trades or pickups.

Run the unit tests with `espn-venv\Scripts\python.exe -m unittest discover tests`.

### AI skills

| Skill | Ask things like |
|---|---|
| `trade-evaluator` | "Is this trade good?", "What can I get for X?" |
| `team-analysis` | "Analyze Game Of Mahomes", "What are my weaknesses?" |
| `power-rankings` | "Who's the best team?", "Should I panic?" |

League rules, data-source rules and answer format are in [CLAUDE.md](CLAUDE.md).

### Using it from the Claude Desktop chat app

Add this to `%APPDATA%\Claude\claude_desktop_config.json` (Windows), replacing the path with where you cloned the project, then restart the app:

```json
{
  "mcpServers": {
    "espn-fantasy-football": {
      "command": "C:\\path\\to\\mcp-fantasy-fotball\\espn-venv\\Scripts\\python.exe",
      "args": ["-m", "espn_mcp.server"],
      "cwd": "C:\\path\\to\\mcp-fantasy-fotball"
    }
  }
}
```

Built on [cwendt94/espn-api](https://github.com/cwendt94/espn-api).
