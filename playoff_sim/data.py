"""Builds simulation inputs from the live ESPN league: records, points for, the remaining schedule,
and each team's expected weekly score (blend of best projected lineup and actual average) and spread.
"""
from __future__ import annotations

from statistics import mean, pstdev, stdev
from typing import Any

from espn_mcp.analysis import best_lineup
from espn_mcp.league import get_league, player_to_dict
from playoff_sim.simulation import blend_mean, shrunk_sd, strength_sd


def load_inputs(prior_games: float = 5.0, sd_prior_games: float = 5.0,
                exclude_doubtful: bool = False) -> dict[str, Any]:
    league = get_league()
    reg_weeks = league.settings.reg_season_count
    playoff_teams = league.settings.playoff_team_count

    played: dict[str, list[float]] = {}
    remaining: list[tuple[int, str, str]] = []
    for t in league.teams:
        scores = []
        for week, (opp, score, outcome) in enumerate(zip(t.schedule, t.scores, t.outcomes), start=1):
            if week > reg_weeks:
                break
            if outcome in ("W", "L", "T"):
                scores.append(float(score))
            elif t.team_id < opp.team_id:  # unplayed (or in progress): add each game once
                remaining.append((week, t.team_name, opp.team_name))
        played[t.team_name] = scores

    # League-wide weekly spread: deviation of each score from its own team's average.
    residuals = [s - mean(v) for v in played.values() if len(v) >= 2 for s in v]
    league_sd = pstdev(residuals) * (len(residuals) / (len(residuals) - len(played))) ** 0.5 \
        if len(residuals) > len(played) else 25.0

    teams: dict[str, dict[str, Any]] = {}
    for t in league.teams:
        scores = played[t.team_name]
        games = len(scores)
        projected = best_lineup([player_to_dict(p) for p in t.roster], exclude_doubtful)["weekly"]
        actual = mean(scores) if scores else projected
        team_sd = stdev(scores) if games >= 2 else None
        sd = shrunk_sd(team_sd, games, league_sd, sd_prior_games)
        teams[t.team_name] = {
            "wins": t.wins, "losses": t.losses, "ties": t.ties,
            "points_for": round(t.points_for, 2),
            "games": games,
            "projected": projected,
            "actual": round(actual, 2),
            "mean": round(blend_mean(projected, actual, games, prior_games), 2),
            "team_sd": round(team_sd, 2) if team_sd is not None else None,
            "sd": round(sd, 2),
            "strength_sd": round(strength_sd(sd, games, prior_games), 2),
        }
    remaining.sort()
    return {
        "week": league.current_week,
        "reg_season_weeks": reg_weeks,
        "playoff_teams": playoff_teams,
        "league_sd": round(league_sd, 2),
        "teams": teams,
        "remaining": remaining,
    }
