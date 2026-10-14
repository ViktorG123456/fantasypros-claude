---
name: trade-analyzer
description: Evaluate or find fantasy football trades in Fantasifotbollsligan using FantasyPros free-plan tools (live rosters, ROS projections, expert comparisons, partner fit). Use when the user asks "is this trade good", "should I accept this offer", "what can I get for X", "who should I trade with", or compares trade offers.
---

# Trade analyzer

Prices a trade for **both** teams with lineup math on FantasyPros rest-of-season (ROS) projections, and checks whether the partner would realistically accept.

The FantasyPros `trade_analyzer` and `trade_finder` tools are premium and not in the user's plan. Don't call them. This skill rebuilds the analysis from free tools.

League key for every league-scoped call: `nfl~d833b763-76ec-46fb-9161-749144157ea8`. Always pass `scoring="PPR"` where a tool accepts it.

## 0. Work out the request
- **Mode A, evaluate:** the user names players going each way, e.g. "Chase Brown for Jaylen Waddle".
- **Mode B, find:** the user names a player to sell or a position to fill, e.g. "what can I get for Achane?" or "I need a WR".
- **Perspective:** "my team" means Game Of Mahomes. If a different team's side is meant and it's unclear, ask. Refer to teams by name, never "we" or "us".

## 1. League context
1. `get_roster(league_key, all_teams=true)` gives every roster. Use it to confirm who owns each player in the trade. If a player is on neither team, stop and say so.
2. `league_analyzer(league_key, period="ros")` gives each team's position ranks, power rank, projected record and playoff odds. Note whether each side is contending (playoff odds ≥ 50%) or rebuilding. That changes what a fair trade looks like.
3. **Mode B only:** `rank_trade_partners(league_key, position_surplus=..., position_need=...)`. Take partners from the top of its list. A good partner is weak where the user sells and strong where the user buys. Don't reorder it by gut feel.

## 2. Player values
For every player in the trade, plus the players they'd replace or push out of each lineup:

1. `get_player_comparisons(player_names="A, B, C, D", comparison_type="ros", scoring="PPR", league_key=...)`, up to 4 players per call. From each player, record:
   - ROS position rank (e.g. RB14)
   - **Season Avg.**: actual PPR points per game so far
   - **Projection Avg.**: expected PPR points per game from here
   - Expert picks (e.g. "4 of 4"), when players at the same position are compared
2. If a starter's projection is missing, use `get_projections(position=..., projection_type="ros", limit=150)`. Use `points_ppr`, never `points`, and divide by the games the player has left.
3. **Sell-high / buy-low flags:** Season Avg. more than 3 above Projection Avg. means the user should sell high. More than 3 below means the user should buy low.

Early in the season actual averages come from a small sample. Weight Projection Avg. over Season Avg.

## 3. Lineup math (both teams)
Lineup is **1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K**. It's a 1-QB league with no superflex.

For each team, before and after the trade:
1. Build the best lineup from Projection Avg. Leave out players listed OUT or on IR.
2. Weekly change = after-lineup total minus before-lineup total, counting skill slots only (QB, K and D/ST only if traded).
3. Rest-of-season change = weekly change × weeks left. Weeks left in the regular season = 14 − current week + 1, using `nfl_week` from any tool's `data_as_of`. State this number. Also mention playoff weeks 15–17 if the team is contending.
4. **Bench value:** only the first backup at RB, WR and TE matters, at about 10% of his projection. Other bench players only take a roster spot.
5. **Roster spots:** a team taking more players than it sends must drop its lowest-projected bench players (15 active + 3 IR). Name who would be dropped.

Do this math in a short Python snippet (in the scratchpad), not by hand, when more than a few numbers are involved.

## 4. Realism check (partner's side)
Rate the partner's chance of accepting as **High**, **Medium** or **Low**:
- **Low:** the partner starts none of what they get, or loses more than 3 points a week in lineup value, or gives up a clearly higher-ranked player (by ROS position rank) for lesser ones.
- **High:** the partner gains lineup value, starts an incoming player, and fills a position where `league_analyzer` ranks them 9th–12th.
- **Medium:** everything in between.
- **Two-for-one trades:** two average players rarely add up to one star. The team receiving two players must gain a starter, not just bench depth.
- Use position ranks from `league_analyzer`. A team ranked top 3 at a position doesn't need another player there.

## 5. Output
1. **Verdict line:** accept / decline / counter, from the named team's side.
2. **Player table:**

| Player | Team now | Pos | ROS rank | Season Avg. | Proj Avg. | Flag |
|---|---|---|---|---|---|---|

3. **Lineup impact table, both teams:**

| Team | Proj/week before | After | Δ/week | Δ rest of season (N weeks) | Dropped |
|---|---|---|---|---|---|

4. **Partner check:** acceptance chance with the reasons, and their position ranks before and after.
5. **Counter-offer** (if declining or Medium/Low acceptance): one or two concrete tweaks, priced the same way.
6. **Don't do:** a short list, e.g. selling a slumping early pick at his lowest value, trading for a backup QB, or a 2-for-1 that leaves the named team unable to field a full lineup.

Mode B: run steps 2–4 for 2–4 candidate trades with partners from `rank_trade_partners`, then rank them in one table and recommend one.

All numbers are FantasyPros expert consensus, not ESPN's projections. Say so once in the answer.
