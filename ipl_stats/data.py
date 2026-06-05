"""Data layer for IPL Stats.

Loads a single ball-by-ball deliveries CSV from ``data/`` and derives every metric the
app needs: match results, the four leaderboards (batsmen / bowlers / teams / venues) and
the raw aggregates the Insights page builds fun-facts and what-ifs from.

See ``SCHEMA.md`` for the input format and its quirks. The important ones:

* ``wide`` / ``legbyes`` / ``byes`` / ``noballs`` are 0/1 flags, not run counts. Actual
  extra runs live in ``extras``. A *legal ball* is ``wide == 0 and noballs == 0``.
* total runs on a delivery = ``runs_of_bat + extras``.
* there is no winner column — results are derived from innings totals.
"""

from __future__ import annotations

import glob
import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Dismissals that are credited to the bowler.
BOWLER_WICKETS = {"caught", "bowled", "lbw", "stumped", "hit wicket"}
# Dismissals that count against the batter / team but not a specific delivery type.
TEAM_WICKETS = BOWLER_WICKETS | {"runout"}

MIN_BALLS_BATTING = 40  # qualification threshold for batting average / strike-rate
MIN_BALLS_BOWLING = 60  # qualification threshold for economy / dot-ball rate


# --------------------------------------------------------------------------- loading


def _find_csv() -> str:
    """Return the path to the deliveries CSV in ``data/``."""
    candidates = sorted(glob.glob(os.path.join(DATA_DIR, "*deliveries*.csv")))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    if not candidates:
        raise FileNotFoundError(
            f"No deliveries CSV found in {DATA_DIR}. Drop a Cricsheet-style ball-by-ball "
            "file there (see SCHEMA.md)."
        )
    return candidates[0]


def load_deliveries() -> pd.DataFrame:
    """Load and normalise the raw deliveries file.

    Adds convenience columns used everywhere downstream:
    ``total_runs``, ``legal_ball``, ``is_wicket``, ``is_bowler_wicket``, ``is_dot``.
    """
    df = pd.read_csv(_find_csv())

    # Normalise text columns.
    df["wicket_type"] = (
        df["wicket_type"].astype("string").str.strip().str.lower().replace({"hitwicket": "hit wicket"})
    )
    for col in ("batting_team", "bowling_team", "striker", "bowler", "venue", "phase"):
        df[col] = df[col].astype("string").str.strip()

    df["total_runs"] = df["runs_of_bat"] + df["extras"]
    df["legal_ball"] = ((df["wide"] == 0) & (df["noballs"] == 0)).astype(int)
    df["is_wicket"] = df["wicket_type"].notna() & df["wicket_type"].isin(TEAM_WICKETS)
    df["is_bowler_wicket"] = df["wicket_type"].notna() & df["wicket_type"].isin(BOWLER_WICKETS)
    df["is_dot"] = ((df["legal_ball"] == 1) & (df["total_runs"] == 0)).astype(int)
    # Runs charged to the bowler = off the bat + all extras except byes / leg-byes.
    df["bowler_runs"] = df["runs_of_bat"] + df["extras"] * ((df["byes"] == 0) & (df["legbyes"] == 0)).astype(int)

    return df


def season(df: pd.DataFrame) -> int:
    """The (latest) season present in the data — the 'current' season for fun-facts."""
    return int(df["season"].max())


# --------------------------------------------------------------- match results / standings


def innings_totals(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (match, innings) for the two main innings, with totals and wickets."""
    main = df[df["innings"] <= 2]
    grp = main.groupby(["match_id", "innings"], as_index=False)
    out = grp.agg(
        batting_team=("batting_team", "first"),
        bowling_team=("bowling_team", "first"),
        venue=("venue", "first"),
        phase=("phase", "first"),
        date=("date", "first"),
        runs=("total_runs", "sum"),
        wickets=("is_wicket", "sum"),
        balls=("legal_ball", "sum"),
    )
    return out


def match_results(df: pd.DataFrame) -> pd.DataFrame:
    """Derive one row per match: who batted first, who won, result type and margin.

    ``result`` is ``runs`` (batting-first side defended), ``wickets`` (chasing side won) or
    ``no_result`` (abandoned). Super-over ties are resolved via innings 3/4 totals.
    """
    tot = innings_totals(df)
    rows = []
    for mid, g in tot.groupby("match_id"):
        i1 = g[g["innings"] == 1]
        i2 = g[g["innings"] == 2]
        meta = dict(
            match_id=mid,
            venue=g["venue"].iloc[0],
            phase=g["phase"].iloc[0],
            date=g["date"].iloc[0],
        )
        if i1.empty or i2.empty:
            rows.append({**meta, "bat_first": i1["batting_team"].iloc[0] if not i1.empty else None,
                         "chaser": None, "winner": None, "loser": None,
                         "result": "no_result", "margin": 0,
                         "first_innings_runs": int(i1["runs"].iloc[0]) if not i1.empty else 0,
                         "second_innings_runs": 0})
            continue
        bf, ch = i1["batting_team"].iloc[0], i2["batting_team"].iloc[0]
        t1, t2 = int(i1["runs"].iloc[0]), int(i2["runs"].iloc[0])
        w2 = int(i2["wickets"].iloc[0])
        if t1 > t2:
            winner, loser, result, margin = bf, ch, "runs", t1 - t2
        elif t2 > t1:
            winner, loser, result, margin = ch, bf, "wickets", 10 - w2
        else:
            # Tie in main innings -> decide on super over (innings 3 vs 4) if present.
            so = df[(df["match_id"] == mid) & (df["innings"] > 2)]
            if not so.empty:
                so_tot = so.groupby("innings")["total_runs"].sum()
                so3 = so_tot.get(3, 0)
                so4 = so_tot.get(4, 0)
                so3_team = so[so["innings"] == 3]["batting_team"].iloc[0]
                so4_team = so[so["innings"] == 4]["batting_team"].iloc[0]
                if so3 >= so4:
                    winner, loser = so3_team, so4_team
                else:
                    winner, loser = so4_team, so3_team
                result, margin = "super_over", 0
            else:
                winner, loser, result, margin = None, None, "tie", 0
        rows.append({**meta, "bat_first": bf, "chaser": ch, "winner": winner, "loser": loser,
                     "result": result, "margin": margin,
                     "first_innings_runs": t1, "second_innings_runs": t2})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------- leaderboards


def batsmen_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-batter aggregates with average and strike-rate."""
    g = df.groupby("striker")
    out = pd.DataFrame({
        "runs": g["runs_of_bat"].sum(),
        "balls": g["legal_ball"].sum(),
        "fours": g.apply(lambda d: int(((d["runs_of_bat"] == 4)).sum()), include_groups=False),
        "sixes": g.apply(lambda d: int(((d["runs_of_bat"] == 6)).sum()), include_groups=False),
        "team": g["batting_team"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0]),
    })
    # innings = distinct matches batted in.
    out["innings"] = g["match_id"].nunique()
    # dismissals where this batter was out.
    dis = df[df["player_dismissed"].notna()].groupby("player_dismissed").size()
    out["dismissals"] = dis.reindex(out.index).fillna(0).astype(int)
    out["average"] = out["runs"] / out["dismissals"].where(out["dismissals"] > 0)
    out["strike_rate"] = out["runs"] / out["balls"].where(out["balls"] > 0) * 100
    out = out.reset_index().rename(columns={"striker": "player"})
    return out.sort_values("runs", ascending=False).reset_index(drop=True)


def bowlers_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-bowler aggregates with economy and dot-ball counts."""
    g = df.groupby("bowler")
    out = pd.DataFrame({
        "wickets": g["is_bowler_wicket"].sum(),
        "runs_conceded": g["bowler_runs"].sum(),
        "balls": g["legal_ball"].sum(),
        "dot_balls": g["is_dot"].sum(),
        "team": g["bowling_team"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0]),
    })
    out["innings"] = g["match_id"].nunique()
    out["overs"] = (out["balls"] // 6 + (out["balls"] % 6) / 10).round(1)
    out["economy"] = out["runs_conceded"] / out["balls"].where(out["balls"] > 0) * 6
    out = out.reset_index().rename(columns={"bowler": "player"})
    return out.sort_values("wickets", ascending=False).reset_index(drop=True)


def teams_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-team standings: wins / losses / points / NRR."""
    res = match_results(df)
    tot = innings_totals(df)

    teams = sorted(set(df["batting_team"].dropna()) | set(df["bowling_team"].dropna()))
    rec = {t: dict(played=0, wins=0, losses=0, no_result=0,
                   runs_for=0, balls_for=0, runs_against=0, balls_against=0) for t in teams}

    # played / wins / losses
    for _, r in res.iterrows():
        for team in (r["bat_first"], r["chaser"]):
            if team in rec:
                rec[team]["played"] += 1
        if r["result"] in ("no_result", "tie"):
            # Abandoned or tied with no super over -> points shared (1 each).
            for team in (r["bat_first"], r["chaser"]):
                if team in rec:
                    rec[team]["no_result"] += 1
        elif r["winner"] in rec:
            rec[r["winner"]]["wins"] += 1
            if r["loser"] in rec:
                rec[r["loser"]]["losses"] += 1

    # NRR components: runs scored / faced and runs conceded / bowled (main innings only).
    for _, r in tot.iterrows():
        bt, bw = r["batting_team"], r["bowling_team"]
        if bt in rec:
            rec[bt]["runs_for"] += r["runs"]
            rec[bt]["balls_for"] += r["balls"]
        if bw in rec:
            rec[bw]["runs_against"] += r["runs"]
            rec[bw]["balls_against"] += r["balls"]

    rows = []
    for t, d in rec.items():
        overs_for = d["balls_for"] / 6 if d["balls_for"] else 0
        overs_against = d["balls_against"] / 6 if d["balls_against"] else 0
        rr_for = d["runs_for"] / overs_for if overs_for else 0
        rr_against = d["runs_against"] / overs_against if overs_against else 0
        rows.append(dict(
            team=t, played=d["played"], wins=d["wins"], losses=d["losses"],
            no_result=d["no_result"], points=d["wins"] * 2 + d["no_result"],
            nrr=round(rr_for - rr_against, 3),
        ))
    out = pd.DataFrame(rows)
    return out.sort_values(["points", "nrr"], ascending=False).reset_index(drop=True)


def venues_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-venue: matches, batting-first wins, chasing wins, highest innings total."""
    res = match_results(df)
    tot = innings_totals(df)
    high = tot.groupby("venue")["runs"].max()

    rows = []
    for venue, g in res.groupby("venue"):
        bat_first_wins = int((g["result"] == "runs").sum())
        chasing_wins = int((g["result"] == "wickets").sum())
        rows.append(dict(
            venue=venue,
            short=_short_venue(venue),
            matches=len(g),
            bat_first_wins=bat_first_wins,
            chasing_wins=chasing_wins,
            highest_score=int(high.get(venue, 0)),
        ))
    out = pd.DataFrame(rows)
    return out.sort_values("highest_score", ascending=False).reset_index(drop=True)


def _short_venue(venue: str) -> str:
    """A compact label: city if we can find it, else the leading stadium name."""
    if "," in venue:
        return venue.split(",")[-1].strip()
    return venue
