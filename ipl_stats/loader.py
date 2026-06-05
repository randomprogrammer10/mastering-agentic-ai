"""Streamlit-cached accessors and shared UI helpers.

Keeps ``ipl_stats.data`` free of any Streamlit import (so it stays unit-testable) while
giving every page a single cached source of truth for the heavy DataFrame work.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ipl_stats import data

# IPL franchise brand colours (used across charts for instant recognition).
TEAM_COLORS = {
    "CSK": "#F9CD05",
    "MI": "#006CB7",
    "RCB": "#D81B26",
    "KKR": "#5C2A8E",
    "DC": "#17449B",
    "SRH": "#F26522",
    "RR": "#EA1A85",
    "PBKS": "#D71920",
    "GT": "#1C9CD8",
    "LSG": "#00A2B6",
}
ACCENT = "#1C9CD8"


def team_color(team: str) -> str:
    return TEAM_COLORS.get(team, ACCENT)


@st.cache_data(show_spinner="Loading ball-by-ball data…")
def deliveries() -> pd.DataFrame:
    return data.load_deliveries()


@st.cache_data
def batsmen() -> pd.DataFrame:
    return data.batsmen_table(deliveries())


@st.cache_data
def bowlers() -> pd.DataFrame:
    return data.bowlers_table(deliveries())


@st.cache_data
def teams() -> pd.DataFrame:
    return data.teams_table(deliveries())


@st.cache_data
def venues() -> pd.DataFrame:
    return data.venues_table(deliveries())


@st.cache_data
def results() -> pd.DataFrame:
    return data.match_results(deliveries())


@st.cache_data
def innings() -> pd.DataFrame:
    return data.innings_totals(deliveries())


@st.cache_data
def current_season() -> int:
    return data.season(deliveries())


def page_config(title: str, icon: str) -> None:
    """Shared ``set_page_config`` + a little global CSS for a polished look."""
    st.set_page_config(page_title=f"{title} · IPL 2026", page_icon=icon, layout="wide")
    st.markdown(
        """
        <style>
          .block-container {padding-top: 2.2rem;}
          [data-testid="stMetricValue"] {font-size: 1.8rem;}
          h1, h2, h3 {letter-spacing: -0.01em;}
          .stat-pill {display:inline-block; padding:2px 10px; border-radius:999px;
                      background:#1C9CD822; color:#1C9CD8; font-size:0.8rem; font-weight:600;}
        </style>
        """,
        unsafe_allow_html=True,
    )
