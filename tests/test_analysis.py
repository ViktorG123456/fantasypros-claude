"""Unit tests for espn_mcp.analysis (pure functions, no network).

Run from the repo root:  espn-venv\\Scripts\\python.exe -m unittest discover tests
"""
import unittest

from espn_mcp import analysis as a


def pl(name, pos, proj, actual=None, status="ACTIVE", slot=None):
    return {"name": name, "position": pos, "projected_avg_points": proj,
            "projected_total_points": proj * 14, "season_avg_points": proj if actual is None else actual,
            "injury_status": status, "lineup_slot": slot}


def core():
    """A legal starting lineup with no bench."""
    return [pl("QB1", "QB", 18), pl("RB1", "RB", 15), pl("RB2", "RB", 12), pl("WR1", "WR", 15),
            pl("WR2", "WR", 12), pl("TE1", "TE", 10), pl("FX", "WR", 11), pl("K1", "K", 8), pl("D1", "D/ST", 6)]


class PositionNeed(unittest.TestCase):
    def test_statuses(self):
        roster = core() + [pl("WR3", "WR", 10.5), pl("WR4", "WR", 10.2), pl("RB3", "RB", 9.9)]
        need = a.position_need(roster)
        self.assertEqual(need["WR"]["status"], "SURPLUS")   # 5 WRs at 10+ vs 2 slots
        self.assertEqual(need["RB"]["status"], "THIN")      # RB3 is under 10
        self.assertEqual(need["TE"]["status"], "THIN")

    def test_need_and_injured_ignored(self):
        roster = core()
        roster[5] = pl("TE1", "TE", 9)  # below the 10-point bar
        roster.append(pl("TE2", "TE", 14, status="INJURY_RESERVE"))
        self.assertEqual(a.position_need(roster)["TE"]["status"], "NEED")


class Vorp(unittest.TestCase):
    def test_replacement_and_vorp(self):
        rosters = [[pl(f"WR{i}", "WR", 20 - i * 0.5) for i in range(40)]]
        repl = a.replacement_levels(rosters)
        self.assertAlmostEqual(repl["WR"], 5.5)  # 30th best: 20 - 29 * 0.5
        self.assertEqual(a.vorp(pl("x", "WR", 5), repl), 0.0)  # filler is worth nothing
        self.assertAlmostEqual(a.vorp(pl("y", "WR", 8.5), repl), 3.0)

    def test_two_for_one_prices_the_star(self):
        repl = {"WR": 10.0}
        star, mid1, mid2 = pl("S", "WR", 15), pl("M1", "WR", 11), pl("M2", "WR", 11)
        self.assertGreater(a.vorp(star, repl), a.vorp(mid1, repl) + a.vorp(mid2, repl))


class MarketValue(unittest.TestCase):
    """Draft pedigree: a slumping early pick keeps value, a hot late pick doesn't get full credit."""

    def setUp(self):
        rbs = [pl(f"RB{i}", "RB", 20 - i * 0.4) for i in range(40)]  # RB6 = 18.0, RB30 = 8.4
        self.market = a.market_context([rbs], games_played=3)          # projection weight 3/7

    def test_draft_slot_turns_into_points(self):
        brown = pl("Brown", "RB", 16.9)
        brown["draft_pos_rank"] = 6
        self.assertAlmostEqual(a.draft_implied(brown, self.market), 18.0)
        self.assertAlmostEqual(a.market_proj(brown, self.market), round(3 / 7 * 16.9 + 4 / 7 * 18.0, 2))

    def test_slumping_star_outvalues_hot_late_pick(self):
        brown, hubbard = pl("Brown", "RB", 16.9, actual=13), pl("Hubbard", "RB", 14.9, actual=17.7)
        brown["draft_pos_rank"], hubbard["draft_pos_rank"] = 6, 33
        gap_proj = a.vorp(brown, self.market["repl"]) - a.vorp(hubbard, self.market["repl"])
        gap_market = a.market_value(brown, self.market) - a.market_value(hubbard, self.market)
        self.assertGreater(gap_market, gap_proj + 1)

    def test_undrafted_uses_replacement_and_weight_grows(self):
        waiver = pl("Waiver", "RB", 12)
        self.assertAlmostEqual(a.draft_implied(waiver, self.market), self.market["repl"]["RB"])
        late = a.market_context([[pl(f"RB{i}", "RB", 20 - i * 0.4) for i in range(40)]], games_played=12)
        self.assertGreater(late["w"], self.market["w"])

    def test_sells_low_flag(self):
        me = core()
        me[1] = pl("Brown", "RB", 16.9)
        me[1]["draft_pos_rank"] = 6
        hub = pl("Hubbard", "RB", 16.95)
        hub["draft_pos_rank"] = 33
        side = a.trade_side(me, [me[1]], [hub], market=self.market)
        self.assertGreaterEqual(side["weekly_delta"], 0)   # lineup says fine...
        self.assertTrue(a.sells_low(side))                  # ...but it gives away market value


class TeamValue(unittest.TestCase):
    def test_only_first_backup_counts(self):
        base = a.team_value(core())["value"]
        one = a.team_value(core() + [pl("RB3", "RB", 10)])["value"]
        two = a.team_value(core() + [pl("RB3", "RB", 10), pl("RB4", "RB", 9)])["value"]
        self.assertAlmostEqual(one - base, a.BENCH_BACKUP_WEIGHT * 10)
        self.assertAlmostEqual(two, one)  # second backup adds nothing


class RosterLimit(unittest.TestCase):
    def test_drops_worst_bench_and_respects_ir_slot(self):
        bench = [pl(f"B{i}", "WR", 5 + i) for i in range(6)]
        ir = [pl("Hurt", "RB", 14, status="QUESTIONABLE", slot="IR")]
        roster = core() + bench + ir  # 15 active + 1 IR: full
        kept, dropped = a.apply_roster_limit(roster + [pl("New", "RB", 9)])
        self.assertEqual([p["name"] for p in dropped], ["B0"])
        self.assertIn("Hurt", [p["name"] for p in kept])


class TradeSideAndAcceptance(unittest.TestCase):
    def setUp(self):
        self.repl = {"QB": 15, "RB": 10, "WR": 10, "TE": 8, "K": 7, "D/ST": 5}

    def test_partner_that_cannot_start_players_says_no(self):
        # Partner is stacked at WR: two bench WRs for its RB2 gets a Low.
        partner = core() + [pl("WR3", "WR", 10.8), pl("WR4", "WR", 10.6)] + \
            [pl(f"B{i}", "RB", 4) for i in range(4)]
        give = [pl("G1", "WR", 10.5), pl("G2", "WR", 9)]
        side = a.trade_side(partner, [partner[2]], give, market=self.repl)
        label, reasons = a.acceptance(side)
        self.assertEqual(label, "Low")
        self.assertEqual(side["incoming_starters"], [])
        self.assertTrue(side["dropped"])  # 2-for-1 forces a drop on a full roster

    def test_partner_filling_a_need_says_yes(self):
        partner = core()
        partner[5] = pl("TE1", "TE", 6)  # weak TE
        partner.append(pl("RB3", "RB", 13))
        side = a.trade_side(partner, [partner[-1]], [pl("TEx", "TE", 11)], market=self.repl)
        label, _ = a.acceptance(side)
        self.assertGreater(side["value_delta"], 0)
        self.assertEqual(label, "High")

    def test_zero_change_is_not_high(self):
        partner = core() + [pl("WR3", "WR", 9)]
        side = a.trade_side(partner, [partner[-1]], [pl("WRx", "WR", 9)], market=self.repl)
        self.assertNotEqual(a.acceptance(side)[0], "High")


class Screen(unittest.TestCase):
    def test_finds_mutual_need_trade_without_throw_ins(self):
        me = core()
        me[5] = pl("MyTE", "TE", 6)
        me += [pl("MyWR3", "WR", 11.5), pl("Filler", "RB", 3)]
        partner = core()
        partner[4] = pl("TheirWR2", "WR", 7)
        partner += [pl("TheirTE2", "TE", 11), pl("Junk", "RB", 2)]
        repl = {"QB": 15, "RB": 10, "WR": 10, "TE": 8, "K": 7, "D/ST": 5}
        rows = a.screen_trades(me, {"P": partner}, repl)
        trades = [(r["give"], r["get"]) for r in rows]
        self.assertIn((["MyWR3"], ["TheirTE2"]), trades)
        self.assertFalse(any("Junk" in r["get"] and set(r["give"]) == {"MyWR3"} for r in rows))


if __name__ == "__main__":
    unittest.main()
