"""IPL 2026 — Home: four leaderboards with metric filters.

Run with:  uv run streamlit run Home.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ipl_stats import data, loader

loader.page_config("Home", "🏏")


# --------------------------------------------------------------------------- chart helper


def _bar(df: pd.DataFrame, *, label: str, value: str, value_fmt: str, ascending: bool) -> go.Figure:
    """Horizontal bar chart of the top 5, coloured by team, best on top."""
    d = df.head(5).iloc[::-1]  # reverse so rank 1 sits at the top
    colors = [loader.team_color(t) for t in d["team"]] if "team" in d else [loader.ACCENT] * len(d)
    text = [format(v, value_fmt) for v in d[value]]
    fig = go.Figure(
        go.Bar(
            x=d[value], y=d[label], orientation="h",
            marker=dict(color=colors), text=text, textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x}<extra></extra>",
        )
    )
    fig.update_layout(
        height=260, margin=dict(l=8, r=40, t=8, b=8),
        xaxis=dict(visible=False), yaxis=dict(tickfont=dict(size=13)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def leaderboard(
    title: str, icon: str, df: pd.DataFrame, *, label: str,
    options: dict, default: str, table_cols: dict, key: str,
):
    """Render one leaderboard card: a metric filter, top-5 bar chart and a detail table.

    ``options`` maps a UI label -> (column, ascending, qualifier_column_or_None, min_balls, fmt).
    """
    st.markdown(f"### {icon}  {title}")
    choice = st.segmented_control(
        "Rank by", list(options), default=default, key=key, label_visibility="collapsed",
    ) or default

    col, ascending, qual_col, min_balls, fmt = options[choice]
    ranked = df.copy()
    if qual_col is not None:
        ranked = ranked[ranked[qual_col] >= min_balls]
    ranked = ranked.dropna(subset=[col]).sort_values(col, ascending=ascending).reset_index(drop=True)

    if ranked.empty:
        st.info("No players meet the qualification threshold for this metric.")
        return

    st.plotly_chart(
        _bar(ranked, label=label, value=col, value_fmt=fmt, ascending=ascending),
        width="stretch", key=f"{key}_chart",
    )

    top = ranked.head(5).copy()
    top.insert(0, "#", range(1, len(top) + 1))
    show = top[["#"] + list(table_cols)].rename(columns=table_cols)
    st.dataframe(show, hide_index=True, width="stretch")
    if qual_col is not None:
        st.caption(f"Qualification: min {min_balls} balls.")


# --------------------------------------------------------------------------------- header

season = loader.current_season()
results = loader.results()
n_matches = results["match_id"].nunique()

st.title("🏏 IPL 2026 — Season Dashboard")
st.markdown(
    f"<span class='stat-pill'>Season {season}</span>&nbsp;"
    f"<span class='stat-pill'>{n_matches} matches</span>&nbsp;"
    f"<span class='stat-pill'>10 teams · 13 venues</span>",
    unsafe_allow_html=True,
)
st.caption("Live leaderboards derived ball-by-ball. Use the toggles to re-rank each board.")
st.divider()

bat, bowl, team_tbl, venue_tbl = loader.batsmen(), loader.bowlers(), loader.teams(), loader.venues()

# --------------------------------------------------------------- batsmen + bowlers (row 1)

left, right = st.columns(2, gap="large")

with left:
    leaderboard(
        "Top Batsmen", "🏏", bat, label="player", key="bat",
        options={
            "Runs": ("runs", False, None, 0, ",d"),
            "Average": ("average", False, "balls", data.MIN_BALLS_BATTING, ".2f"),
            "Strike Rate": ("strike_rate", False, "balls", data.MIN_BALLS_BATTING, ".1f"),
        },
        default="Runs",
        table_cols={"player": "Batter", "team": "Team", "runs": "Runs",
                    "average": "Avg", "strike_rate": "SR", "sixes": "6s"},
    )

with right:
    leaderboard(
        "Top Bowlers", "🔴", bowl, label="player", key="bowl",
        options={
            "Wickets": ("wickets", False, None, 0, "d"),
            "Economy": ("economy", True, "balls", data.MIN_BALLS_BOWLING, ".2f"),
            "Dot Balls": ("dot_balls", False, None, 0, "d"),
        },
        default="Wickets",
        table_cols={"player": "Bowler", "team": "Team", "wickets": "Wkts",
                    "economy": "Econ", "dot_balls": "Dots"},
    )

st.divider()

# ------------------------------------------------------------------ teams + venues (row 2)

left2, right2 = st.columns(2, gap="large")

with left2:
    # Bars are coloured via the "team" column; "name" is the y-axis label.
    tdf = team_tbl.copy()
    tdf["name"] = tdf["team"]
    leaderboard(
        "Top Teams", "🏆", tdf, label="name", key="team",
        options={
            "Points": ("points", False, None, 0, "d"),
            "Wins": ("wins", False, None, 0, "d"),
            "Losses": ("losses", False, None, 0, "d"),
            "NRR": ("nrr", False, None, 0, "+.3f"),
        },
        default="Points",
        table_cols={"team": "Team", "played": "P", "wins": "W", "losses": "L",
                    "points": "Pts", "nrr": "NRR"},
    )

with right2:
    vdf = venue_tbl.copy()
    vdf["name"] = vdf["short"]
    vdf["team"] = None  # neutral colour for venues
    leaderboard(
        "Top Venues", "🏟️", vdf, label="name", key="venue",
        options={
            "Highest Score": ("highest_score", False, None, 0, "d"),
            "Bat-First Wins": ("bat_first_wins", False, None, 0, "d"),
            "Chasing Wins": ("chasing_wins", False, None, 0, "d"),
        },
        default="Highest Score",
        table_cols={"short": "Venue", "matches": "M", "bat_first_wins": "Bat-1st W",
                    "chasing_wins": "Chase W", "highest_score": "High"},
    )

st.divider()
st.caption("📊 Explore narrative **Insights** and **What-Ifs** or open the **Chat** to ask Claude anything — see the sidebar.")
