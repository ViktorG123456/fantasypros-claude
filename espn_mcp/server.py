"""MCP server exposing ESPN Fantasy Football league data as tools for Claude.

Run directly for local stdio testing:
    python -m espn_mcp.server

Register with Claude Desktop / Claude Code via .mcp.json (see README.md).
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from espn_mcp.league import (
    box_player_to_dict,
    find_team,
    find_weekly_stats,
    get_box_scores_for_week,
    get_league,
    player_to_dict,
)
from espn_mcp.league import get_draft_rankings as _get_draft_rankings
from espn_mcp.league import get_league_history as _get_league_history

mcp = FastMCP(
    "espn-fantasy-football",
    instructions=(
        "Tools for reading data out of one ESPN Fantasy Football league "
        "(league id / credentials are fixed server-side via .env). "
        "Use get_league_info first to see team names and the current week."
    ),
)


@mcp.tool()
def get_league_info() -> dict[str, Any]:
    """Basic league info: name, scoring period, and every team's name/record/owners."""
    league = get_league()
    return {
        "league_name": league.settings.name,
        "year": league.year,
        "current_week": league.current_week,
        "teams": [
            {
                "team_name": t.team_name,
                "wins": t.wins,
                "losses": t.losses,
                "ties": t.ties,
                "points_for": t.points_for,
                "points_against": t.points_against,
                "owners": [o.get("displayName") for o in (t.owners or [])],
            }
            for t in league.teams
        ],
    }


@mcp.tool()
def get_standings() -> list[dict[str, Any]]:
    """Current league standings, ranked 1st to last."""
    league = get_league()
    return [
        {
            "rank": i,
            "team_name": t.team_name,
            "wins": t.wins,
            "losses": t.losses,
            "ties": t.ties,
            "points_for": t.points_for,
        }
        for i, t in enumerate(league.standings(), start=1)
    ]


@mcp.tool()
def get_weekly_matchups(week: int | None = None) -> dict[str, Any]:
    """Every matchup for a given week, one entry per team (opponent, score, projected score).

    Args:
        week: NFL week number. Defaults to the league's current week.
    """
    league = get_league()
    week = week or league.current_week or 1
    box_scores = get_box_scores_for_week(league, week)
    if not box_scores:
        return {
            "week": week,
            "matchups": {},
            "note": "No matchup data for this week yet (season/draft may not have started).",
        }

    matchups: dict[str, Any] = {}
    for m in box_scores:
        if m.home_team:
            matchups[m.home_team.team_name] = {
                "opponent": m.away_team.team_name if m.away_team else "BYE",
                "score": m.home_score,
                "projected_score": m.home_projected,
                "opponent_score": m.away_score,
            }
        if m.away_team:
            matchups[m.away_team.team_name] = {
                "opponent": m.home_team.team_name if m.home_team else "BYE",
                "score": m.away_score,
                "projected_score": m.away_projected,
                "opponent_score": m.home_score,
            }
    return {"week": week, "matchups": matchups}


@mcp.tool()
def get_team_schedule(team_name: str) -> dict[str, Any]:
    """Full-season schedule and results for one team (opponent/score/outcome per week).

    Args:
        team_name: Team name, or a substring of it (case-insensitive).
    """
    league = get_league()
    team = find_team(league, team_name)
    teams_by_id = {t.team_id: t for t in league.teams}

    schedule = []
    for wk, (opp_id, score, outcome) in enumerate(
        zip(team.schedule, team.scores, team.outcomes), start=1
    ):
        opp_name = (
            teams_by_id[opp_id].team_name
            if opp_id in teams_by_id and opp_id != team.team_id
            else "BYE"
        )
        schedule.append({"week": wk, "opponent": opp_name, "score": score, "outcome": outcome})

    return {"team_name": team.team_name, "schedule": schedule}


@mcp.tool()
def get_team_roster(team_name: str) -> dict[str, Any]:
    """Full roster for one team, with season totals per player.

    Args:
        team_name: Team name, or a substring of it (case-insensitive).
    """
    league = get_league()
    team = find_team(league, team_name)
    return {
        "team_name": team.team_name,
        "roster": [player_to_dict(p) for p in team.roster],
    }


@mcp.tool()
def get_player_info(player_name: str) -> dict[str, Any]:
    """Bio, ownership, injury status, and season totals for a specific player.

    Args:
        player_name: Full player name as ESPN spells it, e.g. "Christian McCaffrey".
    """
    league = get_league()
    player = league.player_info(name=player_name)
    if player is None:
        return {"error": f"No player found matching '{player_name}'."}
    if isinstance(player, list):
        # Ambiguous name match -- return the list so the caller can disambiguate.
        return {"matches": [player_to_dict(p) for p in player]}

    result = player_to_dict(player)
    result["pro_schedule"] = {
        wk: {"opponent": g["team"], "date": g["date"].strftime("%Y-%m-%d")}
        for wk, g in sorted(player.schedule.items(), key=lambda kv: int(kv[0]))
    }
    return result


@mcp.tool()
def get_player_weekly_projection(player_name: str, week: int) -> dict[str, Any]:
    """Projected (or actual, if the game already happened) stats for one player in one week.

    Includes a stat-level breakdown (projected rushing yards, receptions, TDs, etc.),
    not just the point total. Works whether or not the player has been drafted yet.

    Args:
        player_name: Full player name as ESPN spells it.
        week: NFL week number (1-18).
    """
    league = get_league()
    player = find_weekly_stats(league, player_name, week)
    if player is None:
        return {"error": f"No data found for '{player_name}' in week {week}."}
    result = box_player_to_dict(player)
    result["week"] = week
    return result


@mcp.tool()
def get_free_agents(
    week: int | None = None, position: str | None = None, size: int = 25
) -> list[dict[str, Any]]:
    """Top available free agents for a given week, optionally filtered by position.

    Args:
        week: NFL week number. Defaults to the league's current week.
        position: e.g. "QB", "RB", "WR", "TE", "K", "D/ST". Omit for all positions.
        size: Max number of players to return (default 25).
    """
    league = get_league()
    week = week or league.current_week or 1
    free_agents = league.free_agents(week=week, size=size, position=position)
    return [box_player_to_dict(p) for p in free_agents]


@mcp.tool()
def get_draft_rankings(size: int = 10, rank_type: str = "PPR") -> list[dict[str, Any]]:
    """ESPN's actual pre-draft consensus rankings (not a points-based estimate).

    This is ESPN's real overall draft rank -- who's actually projected to go 1.01,
    1.02, etc. -- across every position, not a specific stat projection.

    Args:
        size: How many top-ranked players to return (default 10).
        rank_type: Scoring format to rank by -- "PPR", "STANDARD", "SUPERFLEX", or
            "ELIMINATION". Match this to the league's actual scoring settings
            (check get_league_info / league scoring rules) for a meaningful order.
    """
    league = get_league()
    return _get_draft_rankings(league, size=size, rank_type=rank_type)


@mcp.tool()
def get_league_history() -> dict[str, Any]:
    """Every past season's final standings (rank, playoff seed, record, points for/against)
    plus all-time totals per franchise: titles, runner-ups, playoff trips, win %, average finish.

    Franchises are grouped by ESPN team id and labelled with the current team name and manager,
    because ESPN returns no owner data for past seasons. Playoff W-L and head-to-head are not
    available from ESPN for past seasons.
    """
    return _get_league_history()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
