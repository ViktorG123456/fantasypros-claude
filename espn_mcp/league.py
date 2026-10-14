"""Shared ESPN Fantasy Football league connection + data-shaping helpers.

Credentials come from `.env` in the repo root (LEAGUE_ID, YEAR, ESPN_S2, SWID) --
see README.md and .env.example for how to get them.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv
from espn_api.football import League
from espn_api.football.constant import POSITION_MAP, PRO_TEAM_MAP

load_dotenv()

VALID_DRAFT_RANK_TYPES = {"STANDARD", "PPR", "SUPERFLEX", "ELIMINATION"}


@lru_cache(maxsize=1)
def get_league() -> League:
    """Returns a cached League connection. Built once per server process."""
    league_id = os.getenv("LEAGUE_ID")
    year = os.getenv("YEAR")
    if not league_id or not year:
        raise RuntimeError(
            "LEAGUE_ID and YEAR must be set in .env (see README.md and .env.example)."
        )
    return League(
        league_id=int(league_id),
        year=int(year),
        espn_s2=os.getenv("ESPN_S2") or None,
        swid=os.getenv("SWID") or None,
    )


def find_team(league: League, team_name: str):
    """Case-insensitive substring lookup by team name. Raises ValueError if not found/ambiguous."""
    matches = [t for t in league.teams if team_name.lower() in t.team_name.lower()]
    if not matches:
        names = ", ".join(t.team_name for t in league.teams)
        raise ValueError(f"No team matching '{team_name}'. Teams in this league: {names}")
    if len(matches) > 1:
        names = ", ".join(t.team_name for t in matches)
        raise ValueError(f"'{team_name}' matches multiple teams: {names}. Be more specific.")
    return matches[0]


def player_to_dict(player) -> dict[str, Any]:
    """Season-level bio + totals for a Player (from team.roster or league.player_info)."""
    return {
        "name": player.name,
        "position": player.position,
        "pro_team": player.proTeam,
        "player_id": player.playerId,
        "jersey": player.jersey,
        "eligible_slots": player.eligibleSlots,
        "lineup_slot": getattr(player, "lineupSlot", None),
        "injury_status": player.injuryStatus,
        "injured": player.injured,
        "percent_owned": player.percent_owned,
        "percent_started": player.percent_started,
        "season_total_points": player.total_points,
        "season_avg_points": player.avg_points,
        "projected_total_points": player.projected_total_points,
        "projected_avg_points": player.projected_avg_points,
    }


def box_player_to_dict(player) -> dict[str, Any]:
    """Week-level stats for a BoxPlayer (from box_scores or free_agents)."""
    breakdown = {k: round(v, 2) for k, v in (player.projected_breakdown or {}).items() if not str(k).isdigit()}
    return {
        "name": player.name,
        "position": player.position,
        "pro_team": player.proTeam,
        "slot_position": getattr(player, "slot_position", None),
        "pro_opponent": getattr(player, "pro_opponent", None),
        "points": player.points,
        "projected_points": player.projected_points,
        "projected_stat_breakdown": breakdown,
    }


_box_score_cache: dict[int, list] = {}


def get_box_scores_for_week(league: League, week: int) -> list:
    """Cached per-process; returns [] if the season/draft hasn't produced data for that week yet."""
    if week not in _box_score_cache:
        try:
            _box_score_cache[week] = league.box_scores(week=week)
        except KeyError:
            _box_score_cache[week] = []
    return _box_score_cache[week]


def find_weekly_stats(league: League, player_name: str, week: int, pool_size: int = 300):
    """Find a BoxPlayer (week-specific stats) for player_name at week.

    Tries rostered lineups first (post-draft), falls back to the free-agent pool
    (works pre-draft, or for anyone not currently rostered in this league).
    Returns None if not found anywhere.
    """
    for matchup in get_box_scores_for_week(league, week):
        for lineup in (matchup.home_lineup, matchup.away_lineup):
            for p in lineup:
                if p.name == player_name:
                    return p
    for p in league.free_agents(week=week, size=pool_size):
        if p.name == player_name:
            return p
    return None


def draft_positions(league: League) -> dict[int, dict[str, Any]]:
    """This league's own draft: {playerId: {draft_pick (overall), draft_pos_rank (e.g. 6 = 6th RB
    taken), draft_position}}. Undrafted players are absent."""
    picks = list(getattr(league, "draft", None) or [])
    if not picks:
        return {}
    n = len(league.teams)
    info = league.player_info(playerId=[p.playerId for p in picks]) or []
    if not isinstance(info, list):
        info = [info]
    position = {p.playerId: p.position for p in info}
    counts: dict[str, int] = {}
    result = {}
    for p in sorted(picks, key=lambda d: (d.round_num - 1) * n + d.round_pick):
        pos = position.get(p.playerId)
        if pos is None:
            continue
        counts[pos] = counts.get(pos, 0) + 1
        result[p.playerId] = {"draft_pick": (p.round_num - 1) * n + p.round_pick,
                              "draft_pos_rank": counts[pos], "draft_position": pos}
    return result


def get_draft_rankings(league: League, size: int = 10, rank_type: str = "PPR") -> list[dict[str, Any]]:
    """ESPN's consensus pre-draft rank (draftRanksByRankType), not a points-projection proxy.

    rank_type must be one of VALID_DRAFT_RANK_TYPES -- match it to the league's actual
    scoring format (e.g. PPR for leagues that score receptions) for the ranking to be
    meaningful for that league.
    """
    rank_type = rank_type.upper()
    if rank_type not in VALID_DRAFT_RANK_TYPES:
        raise ValueError(f"rank_type must be one of {sorted(VALID_DRAFT_RANK_TYPES)}, got '{rank_type}'.")

    params = {"view": "kona_player_info", "scoringPeriodId": 1}
    filters = {
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
            "limit": size,
            "sortDraftRanks": {"sortPriority": 1, "sortAsc": True, "value": rank_type},
        }
    }
    headers = {"x-fantasy-filter": json.dumps(filters)}
    data = league.espn_request.league_get(params=params, headers=headers)

    results = []
    for item in data.get("players", []):
        p = item["player"]
        rank_info = p.get("draftRanksByRankType", {}).get(rank_type, {})
        results.append(
            {
                "draft_rank": rank_info.get("rank"),
                "name": p.get("fullName"),
                "position": _primary_position(p),
                "pro_team": PRO_TEAM_MAP.get(p.get("proTeamId")),
                "auction_value": rank_info.get("auctionValue"),
                "rank_type": rank_type,
            }
        )
    return results


HISTORY_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/leagueHistory/{league_id}"


@lru_cache(maxsize=16)
def _past_season(year: int) -> dict[str, Any]:
    """One finished season via ESPN's leagueHistory endpoint. espn_api's League(year=past)
    raises "League does not exist" for this league, but this endpoint works with the same cookies.
    Past seasons come back without owners or weekly schedules -- only final team records."""
    league = get_league()
    resp = requests.get(
        HISTORY_URL.format(league_id=league.league_id),
        params={"seasonId": year, "view": ["mTeam", "mSettings"]},
        cookies=league.espn_request.cookies,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()[0]


def get_league_history() -> dict[str, Any]:
    """Final standings for every past season plus all-time totals per franchise.

    Franchises are keyed by ESPN team id, which stays with a team slot across seasons even when
    it is renamed. Past seasons carry no owner data, so each franchise is labelled with its
    *current* manager; a slot could in principle have changed hands without us seeing it.
    """
    league = get_league()
    status = league.espn_request.league_get(params={"view": "mSettings"}).get("status", {})
    years = sorted(status.get("previousSeasons") or [])

    current_owner = {}
    for t in league.teams:
        names = [" ".join(filter(None, (o.get("firstName"), o.get("lastName")))) or o.get("displayName")
                 for o in (t.owners or [])]
        current_owner[t.team_id] = {"team_name": t.team_name, "managers": names}

    seasons = []
    franchises: dict[int, dict[str, Any]] = {}
    for year in years:
        data = _past_season(year)
        playoff_count = data.get("settings", {}).get("scheduleSettings", {}).get("playoffTeamCount") or 0
        teams = data.get("teams", [])
        pf_order = sorted(teams, key=lambda t: t["record"]["overall"]["pointsFor"], reverse=True)
        pf_rank = {t["id"]: i for i, t in enumerate(pf_order, start=1)}
        rows = []
        for t in teams:
            rec = t["record"]["overall"]
            seed = t.get("playoffSeed") or 0
            row = {
                "team_id": t["id"],
                "team_name": t.get("name"),
                "final_rank": t.get("rankCalculatedFinal") or t.get("rankFinal"),
                "playoff_seed": seed,
                "made_playoffs": 0 < seed <= playoff_count,
                "wins": rec["wins"], "losses": rec["losses"], "ties": rec["ties"],
                "points_for": round(rec["pointsFor"], 2),
                "points_against": round(rec["pointsAgainst"], 2),
                "points_for_rank": pf_rank[t["id"]],
            }
            rows.append(row)

            f = franchises.setdefault(t["id"], {
                "team_id": t["id"], "names": [], "seasons": 0, "wins": 0, "losses": 0, "ties": 0,
                "points_for": 0.0, "championships": [], "runner_ups": 0, "top3": 0,
                "playoffs": 0, "finishes": [], "points_for_ranks": [],
            })
            if row["team_name"] not in f["names"]:
                f["names"].append(row["team_name"])
            f["seasons"] += 1
            f["wins"] += row["wins"]; f["losses"] += row["losses"]; f["ties"] += row["ties"]
            f["points_for"] += row["points_for"]
            f["playoffs"] += row["made_playoffs"]
            f["finishes"].append(row["final_rank"])
            f["points_for_ranks"].append(row["points_for_rank"])
            if row["final_rank"] == 1:
                f["championships"].append(year)
            f["runner_ups"] += row["final_rank"] == 2
            f["top3"] += (row["final_rank"] or 99) <= 3
        seasons.append({
            "year": year,
            "playoff_teams": playoff_count,
            "standings": sorted(rows, key=lambda r: r["final_rank"] or 99),
        })

    all_time = []
    for tid, f in franchises.items():
        games = f["wins"] + f["losses"] + f["ties"]
        all_time.append({
            **{k: v for k, v in f.items() if k not in ("points_for",)},
            "current": current_owner.get(tid, {"team_name": None, "managers": []}),
            "win_pct": round((f["wins"] + 0.5 * f["ties"]) / games, 3) if games else None,
            "points_for_per_season": round(f["points_for"] / f["seasons"], 1),
            "avg_finish": round(sum(f["finishes"]) / len(f["finishes"]), 2),
        })
    all_time.sort(key=lambda r: (-len(r["championships"]), r["avg_finish"]))

    return {
        "seasons_covered": years,
        "note": ("Past seasons have no owner or weekly-matchup data from ESPN; franchises are "
                 "grouped by team id and labelled with the current manager. Playoff W-L and "
                 "head-to-head are not available."),
        "seasons": seasons,
        "all_time_by_franchise": all_time,
    }


def _primary_position(raw_player: dict[str, Any]) -> str:
    """Mirrors espn_api's Player.__init__ position logic (single position, not a flex slot)."""
    name = raw_player.get("fullName", "")
    for slot_id in raw_player.get("eligibleSlots", []):
        mapped = POSITION_MAP.get(slot_id, "")
        if (slot_id != 25 and "/" not in mapped) or "/" in name:
            return mapped
    return ""
