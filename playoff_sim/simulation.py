"""Monte Carlo playoff odds. Pure functions -- no network, stdlib only (the venv has no numpy),
so it can be tested with plain data. `playoff_sim.data` builds the inputs from ESPN.

Three simulation methods:

- "score":  each simulation first draws every team's true strength from Normal(mean, strength_sd)
            (the mean is only an estimate from a few games and a projection), then every game
            draws a fresh score for both teams from Normal(strength, sd); the higher score wins,
            and simulated points count toward the points-for tiebreak. Without the strength draw
            the odds come out far too certain early in the season.
- "slump":  the original method -- win probability = adj_home / (adj_home + adj_away), where
            adj = mean * (1 + U(-slump, +slump)). The slump is redrawn in every simulation.
- "50/50":  every remaining game is a coin flip. Shows how much the current record alone decides.

Standings: most wins (ties count half), then most points for -- ESPN's default tiebreaker.
"""
from __future__ import annotations

import random
from typing import Any

METHODS = ("score", "slump", "50/50")


def blend_mean(projected: float, actual: float, games: int, prior_games: float) -> float:
    """Weight actual scoring by games / (games + prior_games): early in the season the projected
    lineup dominates (it reacts to injuries and trades), later the actual average takes over."""
    w = games / (games + prior_games) if games + prior_games > 0 else 0.0
    return (1 - w) * projected + w * actual


def shrunk_sd(team_sd: float | None, games: int, league_sd: float, prior_games: float) -> float:
    """A team's weekly spread from 2-3 games is noise, so shrink it toward the league-wide spread."""
    if team_sd is None or games < 2:
        return league_sd
    w = (games - 1) / (games - 1 + prior_games)
    return w * team_sd + (1 - w) * league_sd


def strength_sd(sd: float, games: int, prior_games: float) -> float:
    """Uncertainty of a team's true mean: shrinks like a standard error as games are played."""
    return sd / (games + prior_games) ** 0.5


def _standings_key(wins: dict[str, float], points: dict[str, float], coin: dict[str, float]):
    # coin: random last tiebreak, so exact ties don't always favour the team listed first
    return lambda t: (wins[t], points[t], coin[t])


def simulate(
    teams: dict[str, dict[str, Any]],
    remaining: list[tuple[int, str, str]],
    method: str = "score",
    sims: int = 10000,
    playoff_teams: int = 6,
    slump: float = 0.10,
    seed: int | None = None,
    forced: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Run the simulation.

    teams:     name -> {"wins", "losses", "ties", "points_for", "mean", "sd", optional "strength_sd"}
    remaining: unplayed games as (week, home, away)
    forced:    optional {index into remaining: winner} to fix outcomes (used for crucial games)

    Returns per-team playoff %, seed distribution, average wins, plus the average number of
    wins the last playoff seed needed.
    """
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got '{method}'.")
    rng = random.Random(seed)
    forced = forced or {}
    names = list(teams)
    n = len(names)
    base_wins = {t: teams[t]["wins"] + 0.5 * teams[t]["ties"] for t in names}
    base_pts = {t: float(teams[t]["points_for"]) for t in names}
    mean = {t: float(teams[t]["mean"]) for t in names}
    sd = {t: float(teams[t]["sd"]) for t in names}
    str_sd = {t: float(teams[t].get("strength_sd") or 0.0) for t in names}

    seed_counts = {t: [0] * n for t in names}
    win_totals = {t: 0.0 for t in names}
    cutoff_wins = 0.0

    for _ in range(sims):
        wins = dict(base_wins)
        pts = dict(base_pts)
        if method == "score":
            strength = {t: rng.gauss(mean[t], str_sd[t]) for t in names}
        for i, (_, home, away) in enumerate(remaining):
            if method == "score":
                hs = max(0.0, rng.gauss(strength[home], sd[home]))
                as_ = max(0.0, rng.gauss(strength[away], sd[away]))
                home_wins = hs > as_
            elif method == "slump":
                hs = mean[home] * (1 + rng.uniform(-slump, slump))
                as_ = mean[away] * (1 + rng.uniform(-slump, slump))
                home_wins = rng.random() < hs / (hs + as_)
            else:
                hs, as_ = mean[home], mean[away]
                home_wins = rng.random() < 0.5
            if i in forced:
                home_wins = forced[i] == home
            pts[home] += hs
            pts[away] += as_
            wins[home if home_wins else away] += 1

        coin = {t: rng.random() for t in names}
        order = sorted(names, key=_standings_key(wins, pts, coin), reverse=True)
        for rank, t in enumerate(order):
            seed_counts[t][rank] += 1
            win_totals[t] += wins[t]
        if len(order) >= playoff_teams:
            cutoff_wins += wins[order[playoff_teams - 1]]

    results = []
    for t in names:
        dist = [c / sims for c in seed_counts[t]]
        results.append({
            "team": t,
            "playoff_pct": round(sum(dist[:playoff_teams]), 4),
            "top2_pct": round(sum(dist[:2]), 4),
            "first_pct": round(dist[0], 4),
            "avg_wins": round(win_totals[t] / sims, 2),
            "seed_distribution": [round(d, 4) for d in dist],
        })
    results.sort(key=lambda r: (r["playoff_pct"], r["avg_wins"]), reverse=True)
    return {
        "method": method,
        "sims": sims,
        "playoff_teams": playoff_teams,
        "cutoff_avg_wins": round(cutoff_wins / sims, 2),
        "results": results,
    }


def crucial_games(
    teams: dict[str, dict[str, Any]],
    remaining: list[tuple[int, str, str]],
    team: str,
    method: str = "score",
    sims: int = 5000,
    playoff_teams: int = 6,
    slump: float = 0.10,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """For each of `team`'s remaining games: playoff % if it wins vs if it loses. The same seed is used for both branches to cut noise."""
    out = []
    for i, (week, home, away) in enumerate(remaining):
        if team not in (home, away):
            continue
        opp = away if home == team else home
        pct = {}
        for label, winner in (("win", team), ("loss", opp)):
            res = simulate(teams, remaining, method, sims, playoff_teams, slump, seed, forced={i: winner})
            pct[label] = next(r["playoff_pct"] for r in res["results"] if r["team"] == team)
        out.append({"week": week, "opponent": opp, "if_win": pct["win"], "if_loss": pct["loss"],
                    "swing": round(pct["win"] - pct["loss"], 4)})
    return out
