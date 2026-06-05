# Data Schema

The app derives every leaderboard, fun fact and what-if from a **single ball-by-ball CSV**
placed in `data/` (Cricsheet-style IPL deliveries). The current file is
`data/ipl_2026_deliveries.csv` — any file matching `data/*deliveries*.csv` is picked up.

There is **no separate matches file and no precomputed winner**: match results, team standings
and NRR are all derived from the ball-by-ball rows.

## `data/*deliveries*.csv`

One row per legal/illegal delivery bowled.

| column             | type  | notes                                                                    |
|--------------------|-------|--------------------------------------------------------------------------|
| `match_id`         | int   | unique match id                                                          |
| `season`           | int   | e.g. `2026` (dataset currently holds one season)                         |
| `phase`            | str   | `Group Stage`, `Qualifier 1`, `Eliminator`, `Qualifier 2`, `Final`       |
| `match_no`         | int   | sequential match number in the season                                    |
| `date`             | str   | e.g. `Mar 28, 2026`                                                       |
| `venue`            | str   | full stadium name incl. city                                             |
| `batting_team`     | str   | short code, e.g. `RCB`, `MI`, `CSK`                                       |
| `bowling_team`     | str   | short code                                                               |
| `innings`          | int   | `1`/`2` for the match; `3`/`4` are super-over innings (tie-breaker)       |
| `over`             | float | over.ball notation, e.g. `0.1` = 1st ball of over 0, max `19.6`          |
| `striker`          | str   | batter on strike                                                         |
| `bowler`           | str   |                                                                          |
| `runs_of_bat`      | int   | runs off the bat (0–6)                                                    |
| `extras`           | int   | **actual extra runs** on the delivery                                    |
| `wide`             | int   | **flag** 0/1 — was this a wide                                            |
| `legbyes`          | int   | **flag** 0/1 — were leg-byes scored                                      |
| `byes`             | int   | **flag** 0/1 — were byes scored                                          |
| `noballs`          | int   | **flag** 0/1 — was this a no-ball                                         |
| `wicket_type`      | str   | dismissal kind or empty: `caught`, `bowled`, `lbw`, `runout`, `stumped`, `hit wicket`/`hitwicket`, `retired hurt`, `obstructing the field` |
| `player_dismissed` | str   | batter who was out (empty if no wicket)                                   |
| `fielder`          | str   | fielder involved (if any)                                                |

### Important quirks (handled in the data layer)

- `wide`/`legbyes`/`byes`/`noballs` are **0/1 indicators, not run counts**. The run value lives
  in `extras`. A delivery is a **legal ball** when `wide == 0 and noballs == 0`.
- **Total runs** on a delivery = `runs_of_bat + extras`.
- **`wicket_type`** spelling is inconsistent (`hit wicket` vs `hitwicket`) — normalised before use.
- **Bowler-credited wickets** exclude `runout`, `retired hurt`, `obstructing the field`.
- One match (`202612`) has **only innings 1** → treated as a no-result.
- One match is decided by a **super over** (innings 3 & 4) after a tied main innings.

## Derived metrics

- **Batsmen** — runs, innings, balls faced (legal balls only), dismissals → average, strike-rate.
- **Bowlers** — wickets (bowler-credited only), runs conceded (runs off bat + wides + no-balls),
  legal balls → economy, dot balls (legal ball with 0 total runs).
- **Teams** — wins, losses, points (2/win), Net Run Rate (NRR) across the season.
- **Venues** — batting-first wins (defended), chasing wins, highest innings total.
