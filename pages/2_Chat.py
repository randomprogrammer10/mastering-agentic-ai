"""IPL 2026 — Chat: ask Claude anything about the season.

Wires the Anthropic SDK into a streaming, multi-turn chat. The season's full stats
digest is built once (cached) and sent as the system prompt with a `cache_control`
breakpoint, so every turn after the first reads that large context from cache (~0.1x cost)
instead of re-billing it. Model: claude-opus-4-8.
"""

from __future__ import annotations

import os

import anthropic
import streamlit as st

from ipl_stats import loader

loader.page_config("Chat", "💬")

MODEL = "claude-opus-4-8"

PERSONA = (
    "You are the IPL 2026 Season Analyst, embedded in a cricket-stats dashboard. "
    "Answer using ONLY the season data provided below — it is the single source of truth. "
    "If a question can't be answered from this data, say so plainly rather than guessing. "
    "Be concise and conversational: lead with the number or the name, then a short bit of "
    "context. Use markdown tables for comparisons and **bold** for key figures. Do not invent "
    "players, matches, or stats that aren't in the data. Respond with your final answer only — "
    "no meta-commentary about your process."
)


@st.cache_data(show_spinner=False)
def stats_digest() -> str:
    """A large, stable text snapshot of the season — the cached system context."""
    bat = loader.batsmen()
    bowl = loader.bowlers()
    teams = loader.teams()
    venues = loader.venues()
    season = loader.current_season()

    lines: list[str] = [
        f"# IPL {season} — Full Season Data\n",
        "## Metric definitions",
        "- Batting strike rate (SR) = runs / balls faced × 100. Average = runs / dismissals.",
        "- Bowling economy = runs conceded / overs. A dot ball is a legal ball with no run.",
        "- Team points = 2 per win (ties/no-results share 1 each). NRR = run-rate for minus against.",
        "- Venue 'bat-first wins' = team batting first defended; 'chasing wins' = chase succeeded.\n",
        "## League standings (by points, then NRR)",
        "| # | Team | P | W | L | Pts | NRR |",
        "|---|------|---|---|---|-----|-----|",
    ]
    for i, r in teams.reset_index(drop=True).iterrows():
        lines.append(f"| {i+1} | {r.team} | {int(r.played)} | {int(r.wins)} | {int(r.losses)} "
                     f"| {int(r.points)} | {r.nrr:+.3f} |")

    lines += [f"\n## All batters ({len(bat)}), ranked by runs",
              "| # | Batter | Team | Runs | Balls | Avg | SR | 4s | 6s | Inns |",
              "|---|--------|------|------|-------|-----|----|----|----|------|"]
    for i, r in bat.reset_index(drop=True).iterrows():
        avg = f"{r.average:.1f}" if r.average == r.average else "-"
        lines.append(f"| {i+1} | {r.player} | {r.team} | {int(r.runs)} | {int(r.balls)} | {avg} "
                     f"| {r.strike_rate:.1f} | {int(r.fours)} | {int(r.sixes)} | {int(r.innings)} |")

    lines += [f"\n## All bowlers ({len(bowl)}), ranked by wickets",
              "| # | Bowler | Team | Wkts | Runs | Econ | Dots | Inns |",
              "|---|--------|------|------|------|------|------|------|"]
    for i, r in bowl.reset_index(drop=True).iterrows():
        econ = f"{r.economy:.2f}" if r.economy == r.economy else "-"
        lines.append(f"| {i+1} | {r.player} | {r.team} | {int(r.wickets)} | {int(r.runs_conceded)} "
                     f"| {econ} | {int(r.dot_balls)} | {int(r.innings)} |")

    lines += ["\n## Venues",
              "| Venue | Matches | Bat-1st wins | Chasing wins | Highest score |",
              "|-------|---------|--------------|--------------|---------------|"]
    for _, r in venues.iterrows():
        lines.append(f"| {r.venue} | {int(r.matches)} | {int(r.bat_first_wins)} "
                     f"| {int(r.chasing_wins)} | {int(r.highest_score)} |")

    return "\n".join(lines)


def _secret_key() -> str | None:
    """Read ANTHROPIC_API_KEY from .streamlit/secrets.toml if present (no error if absent)."""
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def resolved_key() -> str | None:
    """Key from env, then secrets.toml, then the sidebar box."""
    return os.environ.get("ANTHROPIC_API_KEY") or _secret_key() or st.session_state.get("api_key")


def get_client() -> anthropic.Anthropic | None:
    """Build an Anthropic client from any configured key source; None if unavailable."""
    key = resolved_key()
    return anthropic.Anthropic(api_key=key) if key else None


# ----------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.subheader("💬 Chat settings")
    if not (os.environ.get("ANTHROPIC_API_KEY") or _secret_key()):
        st.session_state["api_key"] = st.text_input(
            "Anthropic API key", type="password",
            value=st.session_state.get("api_key", ""),
            help="Used only in this session to call the Claude API. Or set ANTHROPIC_API_KEY.",
        )
    st.caption(f"Model: `{MODEL}`")
    if st.button("🗑️ Clear conversation"):
        st.session_state.chat = []
        st.rerun()

# ------------------------------------------------------------------------------- header

st.title("💬 Ask the Season")
st.caption("Chat with Claude about IPL 2026 — grounded in the full season stats below.")

with st.expander("📦 Stats digest sent to Claude (cached context)"):
    st.markdown(stats_digest())

# Build the system prompt once: stable persona + the cached digest block.
system = [
    {"type": "text", "text": PERSONA},
    {"type": "text", "text": stats_digest(), "cache_control": {"type": "ephemeral"}},
]

if "chat" not in st.session_state:
    st.session_state.chat = []

# Suggested prompts when the conversation is empty.
if not st.session_state.chat:
    st.markdown("**Try asking:**")
    cols = st.columns(3)
    suggestions = [
        "Who's the best death-overs bowler this season?",
        "Compare the top 3 run-scorers.",
        "Which venue favours chasing teams?",
    ]
    for col, s in zip(cols, suggestions):
        if col.button(s, width="stretch"):
            st.session_state.pending = s
            st.rerun()

# ---------------------------------------------------------------------------- chat loop

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask about players, teams, venues…") or st.session_state.pop("pending", None)

if prompt:
    client = get_client()
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if client is None:
        with st.chat_message("assistant"):
            st.warning("Add your Anthropic API key in the sidebar (or set `ANTHROPIC_API_KEY`) to chat.")
        st.session_state.chat.pop()  # don't keep an unanswered turn
        st.stop()

    with st.chat_message("assistant"):
        usage_box = {}

        def stream_reply():
            try:
                with client.messages.stream(
                    model=MODEL,
                    max_tokens=4096,
                    system=system,
                    messages=st.session_state.chat,
                ) as stream:
                    for text in stream.text_stream:
                        yield text
                    usage_box["usage"] = stream.get_final_message().usage
            except anthropic.AuthenticationError:
                yield "⚠️ That API key was rejected — check it in the sidebar."
            except anthropic.APIStatusError as e:
                yield f"⚠️ API error ({e.status_code}): {e.message}"

        reply = st.write_stream(stream_reply())

    st.session_state.chat.append({"role": "assistant", "content": reply})

    u = usage_box.get("usage")
    if u is not None:
        cached = getattr(u, "cache_read_input_tokens", 0) or 0
        written = getattr(u, "cache_creation_input_tokens", 0) or 0
        st.caption(
            f"🧾 in {u.input_tokens} · cache read {cached} · cache write {written} · out {u.output_tokens}"
            + ("  ·  ⚡ served the season context from cache" if cached else "")
        )
