"""IPL 2026 — Insights: animated fun-facts + interactive what-ifs.

Design note (answering the brief): fun-facts and what-ifs live **together on this page,
separate from the Home leaderboards**. The Home board is the scannable "what's true"
surface; this page is the narrative "what happened / what could've happened" surface.
Keeping the two editorial, animation-led modules side by side gives them a consistent
rhythm and a single place users go to be entertained rather than to look something up.
"""

from __future__ import annotations

import time

import plotly.graph_objects as go
import streamlit as st

from ipl_stats import facts, loader

loader.page_config("Insights", "✨")

df = loader.deliveries()

# --------------------------------------------------------------- card animation styling

st.markdown(
    """
    <style>
      @keyframes fadeUp {from {opacity:0; transform:translateY(18px);} to {opacity:1; transform:translateY(0);}}
      .fact-card {
        border-radius:16px; padding:20px 22px; height:100%;
        background:linear-gradient(140deg, var(--accent)22, rgba(255,255,255,0.02));
        border:1px solid var(--accent)55; border-left:5px solid var(--accent);
        animation:fadeUp .6s ease both;
      }
      .fact-icon {font-size:1.9rem;}
      .fact-value {font-size:2.6rem; font-weight:800; line-height:1.1; color:var(--accent);}
      .fact-vlabel {font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; opacity:.7; margin-bottom:.5rem;}
      .fact-headline {font-size:1.15rem; font-weight:700; margin-bottom:.4rem;}
      .fact-detail {font-size:.92rem; opacity:.85; line-height:1.45;}
    </style>
    """,
    unsafe_allow_html=True,
)


def fact_card(f: dict, delay: float) -> str:
    color = loader.team_color(f["team"]) if f["team"] else loader.ACCENT
    return f"""
    <div class="fact-card" style="--accent:{color}; animation-delay:{delay}s">
      <div class="fact-icon">{f['icon']}</div>
      <div class="fact-value">{f['value']:,}</div>
      <div class="fact-vlabel">{f['value_label']}</div>
      <div class="fact-headline">{f['headline']}</div>
      <div class="fact-detail">{f['detail']}</div>
    </div>
    """


# ----------------------------------------------------------------------------- fun facts

st.title("✨ Season Fun Facts")
st.caption("Four headline moments from IPL 2026 — one batter, one bowler, one team, one venue.")

fun = facts.all_fun_facts(df)
row1 = st.columns(2, gap="large")
row2 = st.columns(2, gap="large")
for col, f, i in zip([*row1, *row2], fun, range(4)):
    col.markdown(fact_card(f, delay=i * 0.15), unsafe_allow_html=True)

# Celebrate once per session.
if not st.session_state.get("celebrated"):
    st.session_state["celebrated"] = True
    st.balloons()

st.divider()

# ------------------------------------------------------------------------------ what-ifs

st.title("🔮 What If…")
st.caption("Counterfactual seasons — interactive, and recomputed live from the ball-by-ball data.")

wi1, wi2, wi3 = st.tabs([
    "🎲 Nail-biter flips", "⚡ Powerplay decided it", "🚫 No boundaries",
])

# ---- What-if 1: nail-biter flips -----------------------------------------------------
with wi1:
    st.subheader("What if the closest games had gone the other way?")
    st.caption("Flip every result decided within a margin and watch the table reshuffle. "
               "NRR is unchanged and only breaks ties.")
    s1, s2 = st.columns(2)
    run_thr = s1.slider("Defended by ≤ this many runs", 1, 30, 10, key="nb_runs")
    wkt_thr = s2.slider("Chased with ≤ this many wickets in hand", 1, 5, 2, key="nb_wkts")

    nb = facts.whatif_nailbiters(df, run_thr, wkt_thr)
    tbl = nb["table"]
    st.markdown(
        f"**:red[{nb['n_flips']}]** {'result' if nb['n_flips']==1 else 'results'} flip — "
        "the standings settle like this:"
    )

    # New standings, ordered best-on-top, with a ▲/▼ rank-change tag baked into the label.
    ordered = tbl.sort_values("new_rank", ascending=False)  # reversed so #1 is on top
    def _tag(d):
        return f"  ▲{d}" if d > 0 else (f"  ▼{abs(d)}" if d < 0 else "")
    labels = [f"{t}{_tag(int(d))}" for t, d in zip(ordered["team"], ordered["delta"])]
    bar_colors = [loader.team_color(t) for t in ordered["team"]]
    fig = go.Figure(go.Bar(
        x=ordered["points"], y=labels, orientation="h", marker_color=bar_colors,
        text=[f"{int(p)} pts" for p in ordered["points"]], textposition="outside",
        cliponaxis=False, hovertemplate="%{y}: %{x} pts<extra></extra>",
    ))
    fig.update_layout(
        height=430, margin=dict(l=8, r=50, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(tickfont=dict(size=13)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        transition_duration=700,  # bars glide to new positions when the sliders move
    )
    st.plotly_chart(fig, width="stretch")

    if nb["n_flips"]:
        climber = tbl.loc[tbl["delta"].idxmax()]
        faller = tbl.loc[tbl["delta"].idxmin()]
        c1, c2 = st.columns(2)
        c1.metric(f"Biggest climber · {climber['team']}", f"#{int(climber['new_rank'])}",
                  f"+{int(climber['delta'])} from #{int(climber['actual_rank'])}")
        c2.metric(f"Biggest faller · {faller['team']}", f"#{int(faller['new_rank'])}",
                  f"{int(faller['delta'])} from #{int(faller['actual_rank'])}", delta_color="inverse")
        with st.expander(f"See the {nb['n_flips']} flipped results"):
            for f in nb["flipped"]:
                how = f"by {f['margin']} runs" if f["result"] == "runs" else f"with {f['margin']} wkts in hand"
                st.write(f"• **{f['from']}** beat **{f['to']}** {how} at {f['venue']} → now **{f['to']}** win")
    else:
        st.info("No matches were that close — widen the margins above to start flipping results.")

# ---- What-if 2: powerplay decides ----------------------------------------------------
with wi2:
    st.subheader("What if only the powerplay (first 6 overs) counted?")
    pp = facts.whatif_powerplay(df)
    st.markdown(
        f"Re-deciding all **{pp['decided']}** completed matches on powerplay runs alone, "
        f"**:red[{pp['flips']} results]** would flip."
    )
    if st.button("▶ Reveal the powerplay table", key="pp_go"):
        ph = st.empty()
        tbl = pp["table"]
        # Animate the bars growing.
        for frac in [0.2, 0.45, 0.7, 1.0]:
            fig = go.Figure(go.Bar(
                x=tbl["pp_wins"] * frac, y=tbl["team"], orientation="h",
                marker_color=[loader.team_color(t) for t in tbl["team"]],
            ))
            fig.update_layout(
                height=380, margin=dict(l=8, r=20, t=8, b=8),
                xaxis=dict(range=[0, tbl["pp_wins"].max() + 1], title="Powerplay 'wins'"),
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            ph.plotly_chart(fig, width="stretch")
            time.sleep(0.18)
        top = tbl.iloc[0]
        st.success(f"🏆 **{top['team']}** would top a powerplay-only league with **{int(top['pp_wins'])} wins** "
                   "— the strongest fast starters of the season.")
    else:
        st.info("Hit the button to watch the alternate powerplay table build up.")

# ---- What-if 3: no boundaries --------------------------------------------------------
with wi3:
    st.subheader("What if a batter's boundaries never counted?")
    bat = loader.batsmen()
    top_names = bat.head(15)["player"].tolist()
    player = st.selectbox("Pick a top batter", top_names, index=0, key="nb_player")
    wb = facts.whatif_no_boundaries(df, player)

    st.markdown(f"**{wb['player']}** ({wb['team']}) scored **{wb['actual_runs']:,}** runs — "
                f"**{wb['fours']} fours** and **{wb['sixes']} sixes** alone were worth "
                f"**{wb['boundary_runs']:,}** of them.")

    if st.button("▶ Strip the boundaries", key="nb_go"):
        ph = st.empty()
        start, end = wb["actual_runs"], wb["adjusted_runs"]
        steps = 28
        for i in range(steps + 1):
            val = int(start + (end - start) * (i / steps))
            ph.markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:4rem;font-weight:800;color:{loader.team_color(wb['team'])}'>{val:,}</div>"
                f"<div style='opacity:.7'>runs without boundaries</div></div>",
                unsafe_allow_html=True,
            )
            time.sleep(0.03)
        c1, c2 = st.columns(2)
        c1.metric("Runs", f"{wb['adjusted_runs']:,}", f"-{wb['boundary_runs']:,}", delta_color="inverse")
        c2.metric("Season rank", f"#{wb['adjusted_rank']}", f"{wb['adjusted_rank']-wb['actual_rank']:+d} from #{wb['actual_rank']}", delta_color="inverse")
        st.warning(f"**{wb['pct_from_boundaries']:.0f}%** of {wb['player'].split()[0]}'s runs came from boundaries — "
                   f"take them away and they'd tumble from **#{wb['actual_rank']}** to **#{wb['adjusted_rank']}** on the run charts.")
    else:
        st.info("Hit the button to watch the run tally fall as the 4s and 6s vanish.")
