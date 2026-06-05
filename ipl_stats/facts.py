"""Fun-facts and what-if computations for the Insights page.

Pure functions over the deliveries DataFrame — no Streamlit here. Each fun-fact returns a
small dict the UI renders into an animated card; each what-if returns the data needed to
drive its interactive widget / animation.
"""

from __future__ import annotations

import pandas as pd

from ipl_stats import data


# ============================================================================ fun facts


MIN_BALLS_FACT = 50  # qualification for the dot-ball / extras fun-facts


def fact_batsman(df: pd.DataFrame) -> dict:
    """The batter who faced the most dot balls (min 50 balls faced)."""
    legal = df[df["legal_ball"] == 1]
    agg = (
        legal.groupby("striker")
        .agg(balls=("legal_ball", "sum"),
             dots=("runs_of_bat", lambda s: int((s == 0).sum())),
             team=("batting_team", "first"))
        .reset_index()
    )
    agg = agg[agg["balls"] >= MIN_BALLS_FACT]
    row = agg.sort_values("dots", ascending=False).iloc[0]
    pct = row["dots"] / row["balls"] * 100 if row["balls"] else 0
    return {
        "kind": "batsman", "icon": "🏏", "team": row["team"],
        "headline": f"{row['striker']} soaked up {int(row['dots'])} dot balls",
        "value": int(row["dots"]), "value_label": "dot balls faced",
        "detail": f"Out of {int(row['balls'])} balls faced for {row['team']}, {pct:.0f}% went without "
                  f"a run off the bat — the most dots of any batter (min {MIN_BALLS_FACT} balls).",
    }


def fact_bowler(df: pd.DataFrame) -> dict:
    """The bowler who conceded the most extras (min 50 balls bowled)."""
    agg = (
        df.groupby("bowler")
        .agg(balls=("legal_ball", "sum"), extras=("extras", "sum"),
             wides=("wide", "sum"), noballs=("noballs", "sum"),
             team=("bowling_team", "first"))
        .reset_index()
    )
    agg = agg[agg["balls"] >= MIN_BALLS_FACT]
    row = agg.sort_values("extras", ascending=False).iloc[0]
    w, nb = int(row["wides"]), int(row["noballs"])
    wides = f"{w} wide" + ("s" if w != 1 else "")
    noballs = f"{nb} no-ball" + ("s" if nb != 1 else "")
    return {
        "kind": "bowler", "icon": "🔴", "team": row["team"],
        "headline": f"{row['bowler']} leaked {int(row['extras'])} in extras",
        "value": int(row["extras"]), "value_label": "extras conceded",
        "detail": f"More than any other bowler for {row['team']} — including {wides} "
                  f"and {noballs} (min {MIN_BALLS_FACT} balls bowled).",
    }


def fact_team(df: pd.DataFrame) -> dict:
    """The biggest six-hitting team of the season."""
    six = df[df["runs_of_bat"] == 6].groupby("batting_team").size().sort_values(ascending=False)
    team, n = six.index[0], int(six.iloc[0])
    total_team_sixes = int(six.sum())
    share = n / total_team_sixes * 100 if total_team_sixes else 0
    return {
        "kind": "team", "icon": "💥", "team": team,
        "headline": f"{team} cleared the ropes {n} times",
        "value": n, "value_label": "sixes this season",
        "detail": f"The most by any side — {share:.0f}% above the league six-hitting average. "
                  f"Pure power.",
    }


def fact_venue(df: pd.DataFrame) -> dict:
    """The highest team total and where it was hammered."""
    tot = data.innings_totals(df)
    row = tot.sort_values("runs", ascending=False).iloc[0]
    venue_short = data._short_venue(row["venue"])
    return {
        "kind": "venue", "icon": "🏟️", "team": row["batting_team"],
        "headline": f"{int(row['runs'])} runs lit up {venue_short}",
        "value": int(row["runs"]), "value_label": "the season's highest total",
        "detail": f"Posted by {row['batting_team']} at {row['venue']} — the most runs piled on in "
                  f"a single innings all season.",
    }


def all_fun_facts(df: pd.DataFrame) -> list[dict]:
    return [fact_batsman(df), fact_bowler(df), fact_team(df), fact_venue(df)]


# ============================================================================ what-ifs


def whatif_nailbiters(df: pd.DataFrame, run_threshold: int, wicket_threshold: int) -> dict:
    """Flip every result decided within a margin and reshuffle the standings.

    A match is a "nail-biter" if the batting-first side defended by ``<= run_threshold``
    runs, or the chasing side won with ``<= wicket_threshold`` wickets in hand. Flipping
    such a result moves the two competition points from the winner to the loser; NRR (a
    function of runs, not results) is left unchanged and used only as the tie-breaker.
    """
    res = data.match_results(df)
    base = data.teams_table(df).copy()
    base = base.sort_values(["points", "nrr"], ascending=False).reset_index(drop=True)
    base["actual_rank"] = range(1, len(base) + 1)

    wins = dict(zip(base["team"], base["wins"]))
    losses = dict(zip(base["team"], base["losses"]))
    no_result = dict(zip(base["team"], base["no_result"]))
    nrr = dict(zip(base["team"], base["nrr"]))

    flipped = []
    for r in res.itertuples():
        close = (r.result == "runs" and r.margin <= run_threshold) or (
            r.result == "wickets" and r.margin <= wicket_threshold
        )
        if not close or r.winner not in wins or r.loser not in losses:
            continue
        wins[r.winner] -= 1
        losses[r.winner] += 1
        wins[r.loser] += 1
        losses[r.loser] -= 1
        flipped.append({
            "match_id": r.match_id, "from": r.winner, "to": r.loser,
            "result": r.result, "margin": int(r.margin), "venue": data._short_venue(r.venue),
        })

    rows = [{
        "team": t, "wins": wins[t], "losses": losses[t], "no_result": no_result[t],
        "points": wins[t] * 2 + no_result[t], "nrr": nrr[t],
    } for t in base["team"]]
    new = pd.DataFrame(rows).sort_values(["points", "nrr"], ascending=False).reset_index(drop=True)
    new["new_rank"] = range(1, len(new) + 1)

    out = new.merge(base[["team", "actual_rank", "points"]].rename(columns={"points": "actual_points"}), on="team")
    out["delta"] = out["actual_rank"] - out["new_rank"]  # +ve = climbs after flips
    return {
        "table": out[["team", "points", "actual_points", "nrr", "actual_rank", "new_rank", "delta"]],
        "flipped": flipped, "n_flips": len(flipped),
    }


def whatif_powerplay(df: pd.DataFrame) -> dict:
    """Re-decide every match on first-6-over (powerplay) runs only.

    Returns the alternate standings (wins) and how many results would flip.
    """
    pp = df[(df["innings"] <= 2) & (df["over"] < 6.0)]
    pp_tot = pp.groupby(["match_id", "innings"]).agg(
        team=("batting_team", "first"), runs=("total_runs", "sum")).reset_index()

    actual = data.match_results(df).set_index("match_id")
    flips, pp_wins = 0, {}
    decided = 0
    for mid, g in pp_tot.groupby("match_id"):
        i1 = g[g["innings"] == 1]
        i2 = g[g["innings"] == 2]
        if i1.empty or i2.empty:
            continue
        r1, r2 = i1["runs"].iloc[0], i2["runs"].iloc[0]
        if r1 == r2:
            continue
        decided += 1
        pp_winner = i1["team"].iloc[0] if r1 > r2 else i2["team"].iloc[0]
        pp_wins[pp_winner] = pp_wins.get(pp_winner, 0) + 1
        real_winner = actual.loc[mid, "winner"] if mid in actual.index else None
        if real_winner is not None and pp_winner != real_winner:
            flips += 1
    table = (
        pd.Series(pp_wins, name="pp_wins").rename_axis("team").reset_index()
        .sort_values("pp_wins", ascending=False).reset_index(drop=True)
    )
    return {"table": table, "flips": flips, "decided": decided}


def whatif_no_boundaries(df: pd.DataFrame, player: str) -> dict:
    """Strip a batter's 4s and 6s: how do their runs and season rank collapse?"""
    bat = data.batsmen_table(df)
    row = bat[bat["player"] == player].iloc[0]
    boundary_runs = int(row["fours"]) * 4 + int(row["sixes"]) * 6
    adjusted_runs = int(row["runs"]) - boundary_runs

    actual_rank = int(bat.sort_values("runs", ascending=False)
                      .reset_index(drop=True).query("player == @player").index[0]) + 1
    adj = bat.copy()
    adj.loc[adj["player"] == player, "runs"] = adjusted_runs
    adj_rank = int(adj.sort_values("runs", ascending=False)
                   .reset_index(drop=True).query("player == @player").index[0]) + 1
    return {
        "player": player, "team": row["team"],
        "actual_runs": int(row["runs"]), "adjusted_runs": adjusted_runs,
        "boundary_runs": boundary_runs, "fours": int(row["fours"]), "sixes": int(row["sixes"]),
        "actual_rank": actual_rank, "adjusted_rank": adj_rank,
        "pct_from_boundaries": boundary_runs / int(row["runs"]) * 100 if row["runs"] else 0,
    }
