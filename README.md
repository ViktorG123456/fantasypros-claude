# FantasyPros fantasy football assistant

Ask Claude fantasy football questions and get answers backed by FantasyPros expert consensus rankings:

- *"Should I start Chase Brown or Judkins this week?"*
- *"Is Higgins for Tate a fair trade?"*
- *"Which waiver-wire running backs do the experts like?"*

It was set up for the league **Fantasifotbollsligan** (12 teams, full PPR, 1 QB). League rules and how Claude should answer are in [CLAUDE.md](CLAUDE.md). Edit that file to match your own league.

FantasyPros doesn't know your league, so tell Claude your roster and any other league facts it needs.

---

## Setup

1. Install **[Git](https://git-scm.com/downloads)** and **[Claude Code](https://claude.com/claude-code)**.
2. Download the project:
   ```bash
   git clone https://github.com/ViktorG123456/fantasypros-claude.git
   ```
3. Open the `fantasypros-claude` folder in Claude Code and approve the `fantasypros` MCP server when asked.
4. Sign in to FantasyPros: run `claude` in a terminal inside the folder, type `/mcp`, choose **fantasypros** and sign in.

Then ask something like:

> My team "YOUR TEAM NAME" has these players: ... Who should I start this week?

---

## Troubleshooting

| Problem | Fix |
|---|---|
| FantasyPros tools missing | The sign-in has expired or was never done. Run `/mcp` in a terminal and sign in again, then restart Claude Code in this folder. |

---

## What's inside

```
fantasypros-claude/
├── .mcp.json     tells Claude Code to connect to the FantasyPros MCP server
└── CLAUDE.md     league rules and how the AI should answer
```
