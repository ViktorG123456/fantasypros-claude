"""Pure lineup / trade math for this league. No network calls -- works on player dicts
shaped like `league.player_to_dict` output, so it can be tested with plain data.

League rules (see CLAUDE.md): 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K.
Full PPR, but ESPN already returns points in league scoring so no rescoring is done here.
"""
from __future__ import annotations

from typing import Any

LINEUP_SLOTS: list[tuple[str, tuple[str, ...]]] = [
    ("QB", ("QB",)),
    ("RB", ("RB",)),
    ("RB", ("RB",)),
    ("WR", ("WR",)),
    ("WR", ("WR",)),
    ("TE", ("TE",)),
    ("FLEX", ("RB", "WR", "TE")),  # filled last, from whatever is left
    ("K", ("K",)),
    ("D/ST", ("D/ST",)),
]

UNAVAILABLE = {"OUT", "INJURY_RESERVE", "SUSPENSION"}

SELL_HIGH_GAP = 5.0
BUY_LOW_GAP = -5.0
# A buy-low also needs a slump bad enough that the manager has soured on him: actual at most
# this share of projected. Stops a WR1 at 14.9 vs 20.2 (74%) being flagged -- nobody discounts him.
BUY_LOW_MAX_RATIO = 0.70

# Roster: 9 starters + 6 bench = 15 active, plus 3 IR slots.
ROSTER_ACTIVE = 15
IR_SLOTS = 3

# Position need: players projecting at least this many points count as real depth.
POSITION_SLOTS = {"RB": 2, "WR": 2, "TE": 1}
NEED_THRESHOLD = 10.0

# Bench: only the first backup at RB, WR and TE has any value (injury / bye cover), at this share.
BENCH_BACKUP_WEIGHT = 0.10

# Replacement level = the Nth best rostered player: 12 teams x starting slots, plus the FLEX share.
REPLACEMENT_RANK = {"QB": 13, "RB": 30, "WR": 30, "TE": 13, "K": 13, "D/ST": 13}

# Market value = how other managers price a player: a blend of ESPN's projection and his draft
# pedigree in this league (drafted as RB6 -> expected to score like today's RB6). The projection's
# share is games / (games + MARKET_PRIOR_GAMES): 3 games in -> 43%, 10 games in -> 71%. It keeps
# early slumps (sell low) and hot starts (buy high) from being taken at face value.
MARKET_PRIOR_GAMES = 4.0
# The evaluated team shouldn't give away more market value than this in one trade ("sells low").
SELL_LOW_LIMIT = 2.0

Player = dict[str, Any]


def proj(p: Player) -> float:
    return float(p.get("projected_avg_points") or 0.0)


def is_available(p: Player, exclude_doubtful: bool = False) -> bool:
    status = (p.get("injury_status") or "").upper()
    if status in UNAVAILABLE:
        return False
    return not (exclude_doubtful and status == "DOUBTFUL")


def best_lineup(roster: list[Player], exclude_doubtful: bool = False) -> dict[str, Any]:
    """Highest-projected legal lineup. Greedy is optimal here: every dedicated slot takes the
    best player at its position, and FLEX then takes the best leftover RB/WR/TE."""
    pool = sorted(
        (p for p in roster if is_available(p, exclude_doubtful)),
        key=proj,
        reverse=True,
    )
    used: set[int] = set()
    starters: list[tuple[str, Player | None]] = []
    for slot, positions in LINEUP_SLOTS:
        pick = next((p for p in pool if id(p) not in used and p.get("position") in positions), None)
        if pick is not None:
            used.add(id(pick))
        starters.append((slot, pick))
    bench = [p for p in roster if id(p) not in used]
    filled = [p for _, p in starters if p is not None]
    return {
        "starters": starters,
        "bench": sorted(bench, key=proj, reverse=True),
        "weekly": round(sum(proj(p) for p in filled), 2),
        "ros": round(sum(float(p.get("projected_total_points") or 0.0) for p in filled), 2),
    }


def games_left(p: Player) -> float | None:
    avg = proj(p)
    if avg <= 0:
        return None
    return round(float(p.get("projected_total_points") or 0.0) / avg, 1)


def gap(p: Player) -> float:
    """Actual points per game minus projected. Positive = over-performing (sell-high candidate)."""
    return round(float(p.get("season_avg_points") or 0.0) - proj(p), 2)


def signal(p: Player) -> str:
    g = gap(p)
    if g >= SELL_HIGH_GAP:
        return "SELL HIGH"
    actual = float(p.get("season_avg_points") or 0.0)
    if g <= BUY_LOW_GAP and actual <= BUY_LOW_MAX_RATIO * proj(p):
        return "BUY LOW"
    return ""


def find_player(roster: list[Player], name: str) -> Player:
    matches = [p for p in roster if name.lower() in p["name"].lower()]
    if not matches:
        raise ValueError(f"No player matching '{name}' on this roster.")
    exact = [p for p in matches if p["name"].lower() == name.lower()]
    if len(exact) == 1:
        return exact[0]
    if len(matches) > 1:
        raise ValueError(f"'{name}' matches several players: {', '.join(p['name'] for p in matches)}.")
    return matches[0]


def position_need(roster: list[Player], exclude_doubtful: bool = False) -> dict[str, dict[str, Any]]:
    """How much a team wants another RB / WR / TE. Depth = available players projecting at least
    NEED_THRESHOLD; compared with the starting slots at that position (FLEX not counted):
    fewer = NEED, equal = THIN, one extra = OK, two or more extra = SURPLUS."""
    result = {}
    for pos, slots in POSITION_SLOTS.items():
        depth = sum(1 for p in roster
                    if p.get("position") == pos and is_available(p, exclude_doubtful) and proj(p) >= NEED_THRESHOLD)
        if depth < slots:
            status = "NEED"
        elif depth == slots:
            status = "THIN"
        elif depth == slots + 1:
            status = "OK"
        else:
            status = "SURPLUS"
        result[pos] = {"depth": depth, "slots": slots, "status": status}
    return result


def replacement_levels(rosters: list[list[Player]]) -> dict[str, float]:
    """Projection of the last player who would start league-wide at each position (the
    REPLACEMENT_RANK-th best available rostered player). Anyone at or below it is roster filler."""
    levels = {}
    for pos, rank in REPLACEMENT_RANK.items():
        projs = sorted((proj(p) for r in rosters for p in r if p.get("position") == pos and is_available(p)),
                       reverse=True)
        levels[pos] = projs[rank - 1] if len(projs) >= rank else (projs[-1] if projs else 0.0)
    return levels


def vorp(p: Player, repl: dict[str, float]) -> float:
    """Value over replacement per game: what a player is worth on the trade market. Two average
    players add up to little, while one star is worth a lot -- this is what prices 2-for-1s."""
    if not is_available(p):
        return 0.0
    return round(max(proj(p) - repl.get(p.get("position"), 0.0), 0.0), 2)


def market_context(rosters: list[list[Player]], games_played: float) -> dict[str, Any]:
    """Everything market_value needs: replacement levels, every position's current projections
    (best first) to turn a draft slot into points, and the projection's weight in the blend."""
    pos_projs = {}
    for pos in REPLACEMENT_RANK:
        pos_projs[pos] = sorted((proj(p) for r in rosters for p in r
                                 if p.get("position") == pos and is_available(p)), reverse=True)
    return {"repl": replacement_levels(rosters), "pos_projs": pos_projs,
            "w": games_played / (games_played + MARKET_PRIOR_GAMES) if games_played > 0 else 0.0,
            "games": games_played}


def _ctx(market: dict[str, Any] | None) -> dict[str, Any] | None:
    """Accept a full market_context or a bare replacement-level dict (projection only)."""
    if market is None or "repl" in market:
        return market
    return {"repl": market, "pos_projs": None, "w": 1.0, "games": None}


def draft_implied(p: Player, market: dict[str, Any]) -> float:
    """Points per game his draft slot stands for: today's projection of the player ranked where he
    was drafted at his position. Undrafted players get replacement level."""
    pos = p.get("position")
    rank = p.get("draft_pos_rank")
    projs = (market.get("pos_projs") or {}).get(pos) or []
    if not rank or not projs:
        return market["repl"].get(pos, 0.0)
    return projs[min(rank, len(projs)) - 1]


def market_proj(p: Player, market: dict[str, Any]) -> float:
    market = _ctx(market)
    w = market["w"]
    if w >= 1.0:
        return proj(p)
    return round(w * proj(p) + (1 - w) * draft_implied(p, market), 2)


def market_value(p: Player, market: dict[str, Any]) -> float:
    """VORP of the market projection: what the player is worth in a trade, pedigree included."""
    market = _ctx(market)
    if not is_available(p):
        return 0.0
    return round(max(market_proj(p, market) - market["repl"].get(p.get("position"), 0.0), 0.0), 2)


def team_value(roster: list[Player], exclude_doubtful: bool = False) -> dict[str, Any]:
    """Best-lineup points plus BENCH_BACKUP_WEIGHT of the first bench backup at RB, WR and TE.
    Every other bench player is worth 0 -- he only takes up a roster spot."""
    lineup = best_lineup(roster, exclude_doubtful)
    backups = []
    for pos in POSITION_SLOTS:
        bench = [p for p in lineup["bench"] if p.get("position") == pos and is_available(p, exclude_doubtful)]
        if bench:
            backups.append(bench[0])  # lineup["bench"] is sorted by projection
    value = lineup["weekly"] + BENCH_BACKUP_WEIGHT * sum(proj(p) for p in backups)
    return {"lineup": lineup, "backups": backups, "value": round(value, 2)}


def apply_roster_limit(roster: list[Player], exclude_doubtful: bool = False,
                       active_limit: int = ROSTER_ACTIVE, ir_slots: int = IR_SLOTS) -> tuple[list[Player], list[Player]]:
    """Cut the roster down to what fits: up to ir_slots players sit on IR (those in ESPN's IR slot,
    else those listed INJURY_RESERVE), the rest must fit in active_limit. Drops the lowest-projected
    non-starters first. Returns (kept, dropped)."""
    ir = [p for p in roster if _on_ir(p)][:ir_slots]
    ir_ids = {id(p) for p in ir}
    active = [p for p in roster if id(p) not in ir_ids]
    excess = len(active) - active_limit
    if excess <= 0:
        return roster, []
    starter_ids = {id(p) for _, p in best_lineup(roster, exclude_doubtful)["starters"] if p is not None}
    candidates = sorted((p for p in active if id(p) not in starter_ids), key=proj)
    dropped = candidates[:excess]
    dropped_ids = {id(p) for p in dropped}
    return [p for p in roster if id(p) not in dropped_ids], dropped


def _on_ir(p: Player) -> bool:
    if p.get("lineup_slot") is not None:
        return p["lineup_slot"] == "IR"
    return (p.get("injury_status") or "").upper() == "INJURY_RESERVE"


def trade_side(roster: list[Player], out: list[Player], incoming: list[Player],
               exclude_doubtful: bool = False, market: dict[str, Any] | None = None) -> dict[str, Any]:
    """One team's view of a trade. `weekly_delta` / `ros_delta` = starting-lineup change;
    `value_delta` also counts the first bench backups at 10%. The roster limit is applied after the
    trade, so a team taking more players than it sends drops its worst bench players. With `market`
    (a market_context, or bare replacement levels) it adds VORP and market value (with pedigree)."""
    market = _ctx(market)
    out_ids = {id(p) for p in out}
    before = team_value(roster, exclude_doubtful)
    # A roster already over the limit isn't the trade's fault: only drop what the trade adds.
    current_active = len(roster) - min(sum(1 for p in roster if _on_ir(p)), IR_SLOTS)
    after_roster, dropped = apply_roster_limit(
        [p for p in roster if id(p) not in out_ids] + incoming, exclude_doubtful,
        active_limit=max(ROSTER_ACTIVE, current_active))
    after = team_value(after_roster, exclude_doubtful)
    starter_ids = {id(p) for _, p in after["lineup"]["starters"] if p is not None}
    need = position_need(roster, exclude_doubtful)
    side = {
        "before": before["lineup"],
        "after": after["lineup"],
        "weekly_delta": round(after["lineup"]["weekly"] - before["lineup"]["weekly"], 2),
        "ros_delta": round(after["lineup"]["ros"] - before["lineup"]["ros"], 2),
        "value_delta": round(after["value"] - before["value"], 2),
        "actual_out": round(sum(float(p.get("season_avg_points") or 0) for p in out), 2),
        "actual_in": round(sum(float(p.get("season_avg_points") or 0) for p in incoming), 2),
        "need_before": need,
        "need_after": position_need(after_roster, exclude_doubtful),
        "incoming_starters": [p["name"] for p in incoming if id(p) in starter_ids],
        "incoming_bench": [p["name"] for p in incoming if id(p) not in starter_ids],
        "incoming_positions": {p["name"]: need.get(p.get("position"), {}).get("status", "-") for p in incoming},
        "dropped": [p["name"] for p in dropped],
    }
    if market is not None:
        repl = market["repl"]
        side["vorp_out"] = round(sum(vorp(p, repl) for p in out), 2)
        side["vorp_in"] = round(sum(vorp(p, repl) for p in incoming), 2)
        side["vorp_net"] = round(side["vorp_in"] - side["vorp_out"], 2)
        side["market_out"] = round(sum(market_value(p, market) for p in out), 2)
        side["market_in"] = round(sum(market_value(p, market) for p in incoming), 2)
        side["market_net"] = round(side["market_in"] - side["market_out"], 2)
    return side


def sells_low(side: dict[str, Any]) -> bool:
    """The team gives away clearly more market value than it gets (e.g. a slumping early pick for
    a hot waiver-level player)."""
    return side.get("market_net") is not None and side["market_net"] < -SELL_LOW_LIMIT


def acceptance(partner: dict[str, Any]) -> tuple[str, list[str]]:
    """Likelihood the partner says yes, from its own `trade_side` result. Returns (label, reasons).
    Low: it starts none of what it gets, its value drops by more than 3/wk, or it loses more than 3
    of market value. High: it gains value, starts at least one incoming player and gives up at
    most 0.5 of market value. Anything else is Medium. Market value includes draft pedigree when
    available (market_net), else plain VORP."""
    reasons = []
    starters = partner["incoming_starters"]
    value = partner["value_delta"]
    vorp_net = partner.get("market_net", partner.get("vorp_net"))
    surplus_in = [n for n, s in partner["incoming_positions"].items() if s == "SURPLUS"]
    need_in = [n for n, s in partner["incoming_positions"].items() if s in ("NEED", "THIN") and n in starters]

    if starters:
        reasons.append(f"starts {', '.join(starters)}")
    else:
        reasons.append("starts none of the incoming players")
    if need_in:
        reasons.append(f"fills a thin position with {', '.join(need_in)}")
    if surplus_in:
        reasons.append(f"already stacked at the position of {', '.join(surplus_in)}")
    if partner["dropped"]:
        reasons.append(f"must drop {', '.join(partner['dropped'])} to fit the roster")
    reasons.append(f"value {value:+.2f}/wk")
    if vorp_net is not None:
        reasons.append(f"market value {vorp_net:+.2f}")
    diff = partner["actual_in"] - partner["actual_out"]
    if abs(diff) >= 3:
        reasons.append(f"looks like a {'win' if diff > 0 else 'loss'} on actual points "
                       f"({partner['actual_out']} -> {partner['actual_in']}/g)")

    if not starters or value < -3 or (vorp_net is not None and vorp_net < -3):
        label = "Low"
    elif value > 0 and (vorp_net is None or vorp_net >= -0.5):
        label = "High"
    else:
        label = "Medium"
    return label, reasons


def screen_trades(roster: list[Player], partners: dict[str, list[Player]], market: dict[str, Any],
                  min_gain: float = 0.5, max_players: int = 2, include_low: bool = False,
                  exclude_doubtful: bool = False) -> list[dict[str, Any]]:
    """Try every 1-for-1 up to max_players-for-max_players RB/WR/TE trade with every partner.
    Keeps trades where the team's starting lineup gains at least min_gain per week and (unless
    include_low) the partner's acceptance isn't Low and the team doesn't sell low (give away more
    than SELL_LOW_LIMIT of market value). Trades that are a simpler trade plus throw-ins are dropped.
    Sorted by acceptance, then the team's weekly gain less any partner loss and half of any market
    value the team gives away."""
    market = _ctx(market)
    from itertools import combinations

    def tradeable(p: Player) -> bool:
        return p.get("position") in POSITION_SLOTS and is_available(p, exclude_doubtful)

    mine = [p for p in roster if tradeable(p)]
    found: dict[str, list[dict[str, Any]]] = {}
    for partner, theirs_roster in partners.items():
        theirs = [p for p in theirs_roster if tradeable(p)]
        for n_give in range(1, max_players + 1):
            for give in combinations(mine, n_give):
                for n_get in range(1, max_players + 1):
                    for get in combinations(theirs, n_get):
                        me = trade_side(roster, list(give), list(get), exclude_doubtful, market)
                        if me["weekly_delta"] < min_gain or (sells_low(me) and not include_low):
                            continue
                        them = trade_side(theirs_roster, list(get), list(give), exclude_doubtful, market)
                        label, reasons = acceptance(them)
                        if label == "Low" and not include_low:
                            continue
                        row = {
                            "partner": partner,
                            "give": [p["name"] for p in give], "get": [p["name"] for p in get],
                            "team_weekly_delta": me["weekly_delta"], "team_ros_delta": me["ros_delta"],
                            "team_vorp_net": me["vorp_net"], "team_market_net": me["market_net"],
                            "team_sells_low": sells_low(me), "team_dropped": me["dropped"],
                            "partner_weekly_delta": them["weekly_delta"], "partner_value_delta": them["value_delta"],
                            "partner_vorp_net": them["vorp_net"], "partner_market_net": them["market_net"],
                            "acceptance": label, "reasons": reasons,
                            "partner_starts": them["incoming_starters"],
                        }
                        row["_score"] = (_ORDER[label],
                                         row["team_weekly_delta"] + min(row["partner_value_delta"], 0)
                                         + 0.5 * min(row["team_market_net"], 0))
                        found.setdefault(partner, []).append(row)
    rows = [r for group in found.values() for r in group if not _has_simpler_version(r, group)]
    rows.sort(key=lambda r: r["_score"], reverse=True)
    # Same partner, same incoming players, same players the partner actually starts: only the
    # extra bench piece differs, so keep the best-scoring version.
    seen, unique = set(), []
    for r in rows:
        key = (r["partner"], tuple(sorted(r["get"])), tuple(sorted(r["partner_starts"])))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    rows = unique
    for r in rows:
        del r["_score"]
    return rows


def _has_simpler_version(row: dict[str, Any], group: list[dict[str, Any]]) -> bool:
    """True if the same partner has a trade using a subset of these players that scores at least as
    well -- i.e. the extra players are throw-ins that change nothing."""
    give, get = set(row["give"]), set(row["get"])
    for other in group:
        if other is row:
            continue
        o_give, o_get = set(other["give"]), set(other["get"])
        if o_give <= give and o_get <= get and (o_give, o_get) != (give, get) \
                and other["_score"] >= (row["_score"][0], row["_score"][1] - 0.01):
            return True
    return False


_ORDER = {"High": 2, "Medium": 1, "Low": 0}


def break_even(roster: list[Player], give: list[Player], exclude_doubtful: bool = False) -> dict[str, Any]:
    """For an N-for-1 trade: the per-game projection a single incoming player must beat for the
    lineup to improve. Found by binary search on a hypothetical player at each skill position."""
    base = best_lineup(roster, exclude_doubtful)["weekly"]
    give_ids = {id(p) for p in give}
    remaining = [p for p in roster if id(p) not in give_ids]
    result = {}
    for pos in ("RB", "WR", "TE"):
        lo, hi = 0.0, 60.0
        for _ in range(40):
            mid = (lo + hi) / 2
            dummy = {"name": "?", "position": pos, "projected_avg_points": mid,
                     "projected_total_points": 0, "injury_status": "ACTIVE"}
            if best_lineup(remaining + [dummy], exclude_doubtful)["weekly"] > base:
                hi = mid
            else:
                lo = mid
        result[pos] = round(hi, 2)
    return result
