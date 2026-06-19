# ⚽ Football Scouting System
### Identifying high-performance, low-cost players for a Cruyffist-philosophy club

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-yellow?logo=powerbi)](https://powerbi.microsoft.com/)
[![StatsBomb](https://img.shields.io/badge/Data-StatsBomb%20Open%20Data-red)](https://github.com/statsbomb/open-data)
[![Transfermarkt](https://img.shields.io/badge/Data-Transfermarkt%20via%20Kaggle-green)](https://www.kaggle.com/datasets/davidcariboo/player-scores)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

---

## 🎯 Business Problem

A newly promoted Spanish First Division club needs to strengthen its squad with **high-performance, low-market-value players**, while staying true to a **Cruyffist playing philosophy**: possession, high press, and build-from-the-back.

The system answers three concrete questions:
- **What is analyzed?** Real on-pitch individual actions (passes, shots, duels, pressures, carries) crossed with historical market value.
- **For whom?** Sporting directors and coaching staff — decision-makers who need a fast discovery tool, not a static report.
- **What decisions does it enable?** Prioritize candidates by position, filter out profiles that don't fit the style, and detect market opportunities.

---

## 🗃️ Data Sources

| Source | Description | Access |
|---|---|---|
| **StatsBomb Open Data** | Match-by-match events in JSON — each action with coordinates, timestamp and type-specific attributes | `statsbombpy` / cloned repo |
| **Transfermarkt via Kaggle** | Position, height, dominant foot and **dated market valuation history** per player | Kaggle API (`davidcariboo/player-scores`) |

> Joining both sources via **composite-score matching** (fuzzy name similarity + country blocking + position similarity) is the core technical challenge of the pipeline.

---

## 🏗️ Pipeline Architecture

The ETL pipeline follows a **star schema** with 4 dimensions and up to 14 fact tables:

```
StatsBomb JSON  ──┐
                  ├──► Python ETL ──► Star Schema CSV ──► Power BI Dashboard
Transfermarkt  ───┘
```

**Dimensions:**
- `dim_jugador` — player profile, habitual position, team
- `dim_partido` — league, season, date
- `dim_valoracion` — full market valuation history within the analyzed period (one row per Transfermarkt snapshot)
- `dim_calendario` — time hierarchy

**Main Facts:**
`fact_pass` · `fact_shot` · `fact_duel` · `fact_dribble` · `fact_carry` · `fact_pressure` · `fact_interception` · `fact_clearance` · `fact_foul` · `fact_block` · `fact_ball_receipt` · `fact_miscontrol` · `fact_minutes`

---

## 📊 Data Coverage

| League | Seasons | Approx. Matches |
|---|---|---|
| La Liga (Spain) | 2014/15 · 2015/16 · 2016/17 · 2017/18 · 2018/19 · 2019/20 | 555 |

> The 2020/21 season is excluded due to COVID distortion. Other European leagues were dropped due to insufficient StatsBomb coverage (only one season available).

---

## 🧠 KPIs and Evaluation Philosophy

Each position has a Cruyffist profile with **weighted DAX scores** (69 measures total). Players with fewer than 450 minutes are automatically excluded:

| Profile | Metrics (weight) | DAX Score |
|---|---|---|
| **Forward** | Through-balls p90 (30%) · High-press actions p90 (30%) · npxG p90 (20%) · Receptions in final third p90 (20%) | `Score Delantero` |
| **Midfielder** | Progressive passes p90 (25%) · Prog. pass ratio (25%) · Progressive carries p90 (20%) · Passes under pressure p90 (20%) · Miscontrol p90 (10%, inverted) | `Score Mediocampista` |
| **Centre-back** | Interceptions in opp. half p90 (30%) · Progressive passes from own half p90 (30%) · Duels won in high zone p90 (20%) · Progressive carries in midfield p90 (20%) | `Score Defensor` |
| **Full-back** | Defensive duels won p90 (30%) · Inside carries p90 (30%) · Inward passes p90 (30%) · Wing presses p90 (10%) | `Score Lateral` |

Each metric is also exposed as a **percentile** (`Pct *`) within its positional cohort for radar-chart visualization.

---

## 📈 Power BI Dashboard

26 tables · 69 DAX measures · 26 relationships · 2 Python visuals · 3 pages:

1. **Jugadores** — master table with unified score and score-per-million, filterable by position (`dim_posicion`), market value and age slicers
2. **Detalle** — individual player card with Python radar chart (percentiles by position) + Python heatmap (8 action types via `fact_heatmap_jugador`), club, country, height, age, minutes played, and 5 dynamic metric cards
3. **Evolución Valor** — market value timeline and minutes played per season powered by `dim_valoracion` (full Transfermarkt history), with club breakdown table

`fact_heatmap_jugador` is a **DAX calculated table** (`UNION` of `SELECTCOLUMNS` over 8 fact tables) — not a CSV from the pipeline. Metric slicers use two auxiliary DAX tables (`dim_metricas_1`, `dim_metricas_2`) that feed `SWITCH`-based dynamic measures per position.

---

## 🗂️ Project Evolution

This repository documents the full evolution of the system — each commit is a working version:

| Version | Main milestone |
|---|---|
| v1 | Monolithic StatsBomb extraction — 4 seasons, 5 event types, master CSV |
| v2 | First star schema — 6 CSVs (2 dims + 4 facts) + per-player summary table |
| v3 | Full ETL — 18 CSVs, 4 dims, 13 facts, 3 EDA reports by Cruyffist profile |
| v4 | Cruyffist philosophical EDA — 4 profiles + cross-validation StatsBomb↔TM jersey number |
| v4.3 | Two-criteria deduplication — exact match first, fuzzy tiebreak with jersey bonus |
| v5 | Colab-free executable pipeline — argparse, preserved x/y coordinates, robust booleans |
| v7 | Interactive JS scatter + EDA oriented to P50/P75/P90 thresholds for DAX criteria |
| v9 | New `fact_minutes` table, reordered pedagogical EDA, canonical 0/1 flags per fact |
| v10 | Canonical rectangular schema per fact — no more misaligned CSV columns |
| v11 | Historical Transfermarkt valuations — peak market value within 2014-2017 period |
| v12 | **6 La Liga seasons 2014-2020, reduced Power BI schema, single conformity report, full valuation timeline** |

---

## 🚀 How to Run

### Requirements
```bash
pip install statsbombpy rapidfuzz pandas numpy
```

### Transfermarkt Data
```bash
pip install kaggle
export KAGGLE_API_TOKEN="your_token_here"
kaggle datasets download -d davidcariboo/player-scores --unzip -p transfermarkt_data/
```

### Run the Pipeline
```bash
# Run with explicit paths pointing to your local data folders
python pipeline/scouting_pipeline_v12.py \
  --repo-path "/path/to/statsbomb/open-data/data" \
  --tm-path "/path/to/transfermarkt" \
  --output-dir "output/scouting_v12_output"

# Or let the pipeline download everything automatically
python pipeline/scouting_pipeline_v12.py --download-data
```

Output CSVs and `reporte_conformidad.html` are saved to `--output-dir`, ready to connect with Power BI.

---

## 📁 Repository Structure

```
scouting-futbol/
├── pipeline/
│   ├── scouting_pipeline_v12.py  ← active pipeline
│   ├── scouting_pipeline_v1.py   ← project history
│   └── ...
├── pbix/                          ← Power BI dashboard + radiography
├── output/                        ← generated CSVs (ignored by .gitignore)
├── .gitignore
└── README.md
```

---

## 👤 Author

**Andrés Coria**
Final Integration Project — Data Analytics Course · ICARO / FCEFyN UNC · 2025

---

*StatsBomb data used under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license. Transfermarkt data via Kaggle under the original dataset terms.*
