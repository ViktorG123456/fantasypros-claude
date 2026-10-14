"""Command-line fantasy analysis for this league (lineups, rankings, trades).

Run from the repo root with the project venv:
    espn-venv\\Scripts\\python.exe -m espn_mcp.analyze rankings
    espn-venv\\Scripts\\python.exe -m espn_mcp.analyze team "Game Of Mahomes"
    espn-venv\\Scripts\\python.exe -m espn_mcp.analyze trade "Game Of Mahomes" --give "Tate,Burden" --partner Mayeday --get "Higgins"
    espn-venv\\Scripts\\python.exe -m espn_mcp.analyze screen "Game Of Mahomes" [--partner Mayeday]
    espn-venv\\Scripts\\python.exe -m espn_mcp.analyze breakeven "Right to Dream" --give "Adams,Judkins"
    espn-venv\\Scripts\\python.exe -m espn_mcp.analyze playoffs --team "Game Of Mahomes"

Add --json to any command for machine-readable output. --exclude-doubtful also benches DOUBTFUL players.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from espn_mcp import analysis as a
from espn_mcp.league import draft_positions, find_team, get_league, player_to_dict

MY_TEAM = "Game Of Mahomes"


def load_teams(with_draft: bool = False) -> tuple[Any, dict[str, dict[str, Any]]]:
    """All rosters as player dicts. with_draft adds draft_pick / draft_pos_rank from this league's
    draft (one extra ESPN request), used by the trade market value."""
    league = get_league()
    draft = draft_positions(league) if with_draft else {}
    teams = {}
    for t in league.teams:
        games = t.wins + t.losses + t.ties
        roster = [player_to_dict(p) for p in t.roster]
        for p in roster:
            d = draft.get(p["player_id"])
            p["draft_pick"] = d["draft_pick"] if d else None
            p["draft_pos_rank"] = d["draft_pos_rank"] if d and d["draft_position"] == p["position"] else None
        teams[t.team_name] = {
            "team": t,
            "roster": roster,
            "games": games,
            "actual_weekly": round(t.points_for / games, 2) if games else 0.0,
        }
    return league, teams


def market_ctx(teams) -> dict[str, Any]:
    games = max((t["games"] for t in teams.values()), default=0)
    return a.market_context([t["roster"] for t in teams.values()], games)


def roster_of(league, teams, name: str) -> tuple[str, list[dict[str, Any]]]:
    team = find_team(league, name)
    return team.team_name, teams[team.team_name]["roster"]


def pick(roster, names: str) -> list[dict[str, Any]]:
    return [a.find_player(roster, n.strip()) for n in names.split(",") if n.strip()]


def fmt(x: float) -> str:
    return f"{x:+.2f}"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    cells = [headers] + [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    lines = [" | ".join(c.ljust(w) for c, w in zip(r, widths)) for r in cells]
    lines.insert(1, "-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def lineup_rows(lineup) -> list[list[Any]]:
    rows = []
    for slot, p in lineup["starters"]:
        if p is None:
            rows.append([slot, "(empty)", "", "", ""])
        else:
            rows.append([slot, p["name"], p["injury_status"], p["season_avg_points"], round(a.proj(p), 2)])
    return rows


def cmd_rankings(args) -> dict[str, Any]:
    league, teams = load_teams()
    pa_sorted = sorted(teams, key=lambda n: teams[n]["team"].points_against, reverse=True)
    rows = []
    for name, info in teams.items():
        t = info["team"]
        lineup = a.best_lineup(info["roster"], args.exclude_doubtful)
        rows.append({
            "team": name,
            "record": f"{t.wins}-{t.losses}" + (f"-{t.ties}" if t.ties else ""),
            "points_for": round(t.points_for, 2),
            "points_against": round(t.points_against, 2),
            "pa_rank": pa_sorted.index(name) + 1,
            "projected_weekly": lineup["weekly"],
            "actual_weekly": info["actual_weekly"],
            "gap": round(info["actual_weekly"] - lineup["weekly"], 2),
        })
    rows.sort(key=lambda r: r["projected_weekly"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    sixth = rows[5]["projected_weekly"] if len(rows) >= 6 else None
    out = {"week": league.current_week, "rankings": rows, "sixth_place_projected": sixth}
    if not args.json:
        print(f"Power rankings, week {league.current_week} (best projected lineup, per week)\n")
        print(table(
            ["#", "Team", "Rec", "PF", "PA (rank)", "Proj/wk", "Actual/wk", "Actual-Proj"],
            [[r["rank"], r["team"] + (" *" if r["team"] == MY_TEAM else ""), r["record"], r["points_for"],
              f"{r['points_against']} ({r['pa_rank']})", r["projected_weekly"], r["actual_weekly"], fmt(r["gap"])]
             for r in rows],
        ))
        mine = next((r for r in rows if r["team"] == MY_TEAM), None)
        if mine and sixth is not None:
            print(f"\n* {MY_TEAM}: rank {mine['rank']}, {fmt(mine['projected_weekly'] - sixth)} per week vs 6th place.")
    return out


def cmd_team(args) -> dict[str, Any]:
    league, teams = load_teams()
    name, roster = roster_of(league, teams, args.team)
    lineup = a.best_lineup(roster, args.exclude_doubtful)
    players = []
    for p in sorted(roster, key=a.proj, reverse=True):
        players.append({
            "name": p["name"], "position": p["position"], "injury_status": p["injury_status"],
            "actual": p["season_avg_points"], "projected": round(a.proj(p), 2),
            "gap": a.gap(p), "signal": a.signal(p), "games_left": a.games_left(p),
        })
    out = {"team": name, "weekly": lineup["weekly"], "ros": lineup["ros"],
           "starters": [{"slot": s, "name": p["name"] if p else None} for s, p in lineup["starters"]],
           "players": players}
    if not args.json:
        print(f"{name}: best lineup {lineup['weekly']} projected pts/week ({lineup['ros']} rest of season)\n")
        print(table(["Slot", "Player", "Status", "Actual/g", "Proj/g"], lineup_rows(lineup)))
        print("\nAll players (actual vs projected):\n")
        print(table(["Player", "Pos", "Status", "Actual/g", "Proj/g", "Gap", "Signal", "Games left"],
                    [[r["name"], r["position"], r["injury_status"], r["actual"], r["projected"],
                      fmt(r["gap"]), r["signal"], r["games_left"] or ""] for r in players]))
    return out


def drafted(p) -> str:
    if not p.get("draft_pick"):
        return "undrafted"
    return f"#{p['draft_pick']} ({p['position']}{p['draft_pos_rank'] or '?'})"


def cmd_trade(args) -> dict[str, Any]:
    league, teams = load_teams(with_draft=True)
    my_name, my_roster = roster_of(league, teams, args.team)
    partner_name, partner_roster = roster_of(league, teams, args.partner)
    give = pick(my_roster, args.give)
    get = pick(partner_roster, args.get)
    market = market_ctx(teams)
    repl = market["repl"]
    mine = a.trade_side(my_roster, give, get, args.exclude_doubtful, market)
    theirs = a.trade_side(partner_roster, get, give, args.exclude_doubtful, market)
    label, reasons = a.acceptance(theirs)
    out = {
        "team": my_name, "partner": partner_name,
        "give": [p["name"] for p in give], "get": [p["name"] for p in get],
        "replacement_levels": repl, "market_projection_weight": round(market["w"], 2),
        "team_weekly_delta": mine["weekly_delta"], "team_ros_delta": mine["ros_delta"],
        "team_value_delta": mine["value_delta"], "team_vorp_net": mine["vorp_net"],
        "team_market_net": mine["market_net"], "team_sells_low": a.sells_low(mine),
        "team_dropped": mine["dropped"],
        "partner_weekly_delta": theirs["weekly_delta"], "partner_ros_delta": theirs["ros_delta"],
        "partner_value_delta": theirs["value_delta"], "partner_vorp_net": theirs["vorp_net"],
        "partner_market_net": theirs["market_net"],
        "partner_dropped": theirs["dropped"],
        "partner_incoming_starters": theirs["incoming_starters"],
        "need": {my_name: mine["need_before"], partner_name: theirs["need_before"]},
        "players": [{"name": p["name"], "position": p["position"], "to": dest, "proj": round(a.proj(p), 2),
                     "actual": p["season_avg_points"], "draft_pick": p.get("draft_pick"),
                     "draft_pos_rank": p.get("draft_pos_rank"), "market_proj": a.market_proj(p, market),
                     "vorp": a.vorp(p, repl), "market_value": a.market_value(p, market)}
                    for players, dest in ((give, partner_name), (get, my_name)) for p in players],
        "acceptance": label, "acceptance_reasons": reasons,
        "partner_sees_actual": {"gives": theirs["actual_out"], "gets": theirs["actual_in"]},
    }
    if not args.json:
        print(f"{my_name} gives {', '.join(out['give'])}  <->  {partner_name} gives {', '.join(out['get'])}\n")
        print(table(["Team", "Before/wk", "After/wk", "Change/wk", "Change ROS", "Value/wk", "Market net",
                     "Must drop"], [
            [n, s["before"]["weekly"], s["after"]["weekly"], fmt(s["weekly_delta"]), fmt(s["ros_delta"]),
             fmt(s["value_delta"]), fmt(s["market_net"]), ", ".join(s["dropped"]) or "-"]
            for n, s in ((my_name, mine), (partner_name, theirs))
        ]))
        if a.sells_low(mine):
            print(f"\nWARNING: {my_name} SELLS LOW: gives {mine['market_out']} of market value for "
                  f"{mine['market_in']}. The lineup gain comes from selling pedigree at its lowest.")
        print("\nPosition need before the trade (players projecting 10+ vs starting slots):\n")
        print(table(["Team", "RB", "WR", "TE"], [
            [n] + [f"{need[p]['status']} ({need[p]['depth']}/{need[p]['slots']})" for p in ("RB", "WR", "TE")]
            for n, need in out["need"].items()
        ]))
        print(f"\nPlayer value. Market proj = {market['w']:.0%} ESPN projection + {1 - market['w']:.0%} "
              f"draft pedigree; market value = market proj minus replacement ("
              + ", ".join(f"{p} {v}" for p, v in repl.items() if p in a.POSITION_SLOTS) + "):\n")
        print(table(["Player", "Pos", "Goes to", "Actual/g", "Proj/g", "Drafted", "Market proj", "Market value",
                     "Starts there?"], [
            [r["name"], r["position"], r["to"], r["actual"], r["proj"], drafted(p), r["market_proj"],
             r["market_value"], "yes" if r["name"] in side["incoming_starters"] else "no (bench)"]
            for r, p, side in zip(out["players"], give + get, [theirs] * len(give) + [mine] * len(get))
        ]))
        print(f"\nAcceptance: {label}. " + "; ".join(reasons) + ".")
        print(f"\n{my_name} lineup after trade:\n")
        print(table(["Slot", "Player", "Status", "Actual/g", "Proj/g"], lineup_rows(mine["after"])))
    return out


def cmd_screen(args) -> dict[str, Any]:
    league, teams = load_teams(with_draft=True)
    name, roster = roster_of(league, teams, args.team)
    market = market_ctx(teams)
    if args.partner:
        partner_name, _ = roster_of(league, teams, args.partner)
        partners = {partner_name: teams[partner_name]["roster"]}
    else:
        partners = {n: t["roster"] for n, t in teams.items() if n != name}
    rows = a.screen_trades(roster, partners, market, args.min_gain, args.max_players, args.include_low,
                           args.exclude_doubtful)[:args.top]
    out = {"team": name, "replacement_levels": market["repl"],
           "market_projection_weight": round(market["w"], 2), "trades": rows}
    if not args.json:
        print(f"Trade screen for {name}: lineup gain >= {args.min_gain}/wk, up to {args.max_players}-for-"
              f"{args.max_players}, {'all' if args.include_low else 'High/Medium, no sell-lows'}, top {args.top}. "
              f"Market value = {market['w']:.0%} projection + {1 - market['w']:.0%} draft pedigree.\n")
        print(table(["#", "Partner", "Give", "Get", "Change/wk", "Change ROS", "Market net", "Partner value/wk",
                     "Partner market", "Accept"], [
            [i, r["partner"], ", ".join(r["give"]), ", ".join(r["get"]), fmt(r["team_weekly_delta"]),
             fmt(r["team_ros_delta"]), fmt(r["team_market_net"]) + (" SELLS LOW" if r["team_sells_low"] else ""),
             fmt(r["partner_value_delta"]), fmt(r["partner_market_net"]), r["acceptance"]]
            for i, r in enumerate(rows, 1)
        ]))
        if rows:
            print("\nWhy the partner would (or wouldn't) accept:\n")
            for i, r in enumerate(rows, 1):
                print(f"{i}. {r['partner']}: " + "; ".join(r["reasons"]))
    return out


def cmd_breakeven(args) -> dict[str, Any]:
    league, teams = load_teams()
    name, roster = roster_of(league, teams, args.team)
    give = pick(roster, args.give)
    be = a.break_even(roster, give, args.exclude_doubtful)
    out = {"team": name, "give": [p["name"] for p in give], "break_even": be}
    if not args.json:
        print(f"{name} trading {', '.join(out['give'])} for ONE player: "
              f"the incoming player must project above (pts/game)\n")
        print(table(["Position", "Break-even"], [[k, v] for k, v in be.items()]))
    return out


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def cmd_playoffs(args) -> dict[str, Any]:
    from playoff_sim import simulation as sim
    from playoff_sim.data import load_inputs

    data = load_inputs(args.prior_games, args.prior_games, args.exclude_doubtful)
    teams, remaining, n_po = data["teams"], data["remaining"], data["playoff_teams"]
    methods = sim.METHODS if args.method == "all" else (args.method,)
    runs = {m: sim.simulate(teams, remaining, m, args.sims, n_po, args.slump, args.seed) for m in methods}
    out: dict[str, Any] = {
        "week": data["week"], "games_left_per_team": len(remaining) * 2 // max(len(teams), 1),
        "league_sd": data["league_sd"], "inputs": teams, "runs": runs,
    }
    focus = find_team(get_league(), args.team).team_name if args.team else None
    if focus:
        out["crucial_games"] = {"team": focus, "method": methods[0], "games": sim.crucial_games(
            teams, remaining, focus, methods[0], max(args.sims // 2, 1000), n_po, args.slump, args.seed)}

    if not args.json:
        main_run = runs[methods[0]]
        by_team = {m: {r["team"]: r for r in runs[m]["results"]} for m in methods}
        print(f"Playoff odds, week {data['week']}: {args.sims} simulations, top {n_po} make it, "
              f"{out['games_left_per_team']} games left per team\n")
        headers = ["Team", "Rec", "Mean", "SD"] + [f"PO% {m}" for m in methods] + \
                  [f"Avg W ({methods[0]})", "Top 2", "Seed 1"]
        rows = []
        for r in main_run["results"]:
            t = r["team"]
            i = teams[t]
            rows.append([t + (" *" if t == focus else ""), f"{i['wins']}-{i['losses']}", i["mean"], i["sd"]]
                        + [pct(by_team[m][t]["playoff_pct"]) for m in methods]
                        + [r["avg_wins"], pct(r["top2_pct"]), pct(r["first_pct"])])
        print(table(headers, rows))
        print(f"\nAverage wins of the #{n_po} seed ({methods[0]}): {main_run['cutoff_avg_wins']}. "
              f"Mean = blend of projected lineup and actual avg (actual weight games/(games+{args.prior_games:g})); "
              f"SD shrunk toward league spread {data['league_sd']}.")
        if focus:
            print(f"\nCrucial games for {focus} ({methods[0]} method):\n")
            print(table(["Week", "Opponent", "PO% if win", "PO% if loss", "Swing"],
                        [[g["week"], g["opponent"], pct(g["if_win"]), pct(g["if_loss"]), pct(g["swing"])]
                         for g in out["crucial_games"]["games"]]))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print JSON instead of tables")
    parser.add_argument("--exclude-doubtful", action="store_true", help="treat DOUBTFUL players as unavailable")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("rankings", help="power rankings by best projected lineup")
    p_team = sub.add_parser("team", help="lineup and actual-vs-projected table for one team")
    p_team.add_argument("team", nargs="?", default=MY_TEAM)
    p_trade = sub.add_parser("trade", help="evaluate a trade for both teams")
    p_trade.add_argument("team", nargs="?", default=MY_TEAM)
    p_trade.add_argument("--give", required=True, help="comma-separated players the team sends")
    p_trade.add_argument("--partner", required=True)
    p_trade.add_argument("--get", required=True, help="comma-separated players the team receives")
    p_sc = sub.add_parser("screen", help="search every realistic trade for a team")
    p_sc.add_argument("team", nargs="?", default=MY_TEAM)
    p_sc.add_argument("--partner", help="only screen trades with this team")
    p_sc.add_argument("--min-gain", type=float, default=0.5, help="minimum lineup gain per week (default 0.5)")
    p_sc.add_argument("--max-players", type=int, default=2, help="max players per side (default 2)")
    p_sc.add_argument("--top", type=int, default=15, help="how many trades to show (default 15)")
    p_sc.add_argument("--include-low", action="store_true", help="also show trades the partner likely rejects")
    p_be = sub.add_parser("breakeven", help="projection a single incoming player must beat")
    p_be.add_argument("team", nargs="?", default=MY_TEAM)
    p_be.add_argument("--give", required=True)
    p_po = sub.add_parser("playoffs", help="Monte Carlo playoff odds for every team")
    p_po.add_argument("--method", choices=["all", "score", "slump", "50/50"], default="all")
    p_po.add_argument("--sims", type=int, default=10000)
    p_po.add_argument("--team", help="also show win/loss playoff swing for each of this team's games")
    p_po.add_argument("--prior-games", type=float, default=5.0,
                      help="games of 'projection weight' in the blend and SD shrinkage (default 5)")
    p_po.add_argument("--slump", type=float, default=0.10, help="slump method's +/- factor (default 0.10)")
    p_po.add_argument("--seed", type=int, help="random seed for reproducible runs")

    args = parser.parse_args(argv)
    handlers = {"rankings": cmd_rankings, "team": cmd_team, "trade": cmd_trade, "screen": cmd_screen,
                "breakeven": cmd_breakeven,
                "playoffs": cmd_playoffs}
    try:
        result = handlers[args.command](args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
