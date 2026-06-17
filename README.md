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

> Joining both sources via **fuzzy matching** (token_set_ratio + jersey number bonus) is the core technical challenge of the pipeline.

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
- `dim_valoracion` — peak market value within the analyzed period
- `dim_calendario` — time hierarchy

**Main Facts:**
`fact_pass` · `fact_shot` · `fact_duel` · `fact_dribble` · `fact_carry` · `fact_pressure` · `fact_interception` · `fact_clearance` · `fact_foul` · `fact_block` · `fact_ball_receipt` · `fact_miscontrol` · `fact_goalkeeper` · `fact_minutes`

---

## 📊 Data Coverage

| League | Seasons | Approx. Matches |
|---|---|---|
| La Liga (Spain) | 2014/15 · 2015/16 · 2016/17 · 2017/18 · 2018/19 · 2019/20 | ~2,280 |

> The 2020/21 season is excluded due to COVID distortion. Other European leagues were dropped due to insufficient StatsBomb coverage (only one season available).

---

## 🧠 KPIs and Evaluation Philosophy

Each position has a Cruyffist profile with weighted metrics:

| Position | Main Focus |
|---|---|
| **False 9 / Forward** | xG, high press, movement between lines |
| **Midfielder** | Progressive passes, carries, actions under pressure |
| **Centre-back** | Interceptions in the opponent's half, build-up from the back |
| **Full-back** | 1v1 duels, inside carries, passes into the box |

**P50 / P75 / P90** percentiles by position are the threshold for dashboard filtering.

---

## 📈 Power BI Dashboard

The dashboard has 3 pages:

1. **Position Selector** — unified filter by Cruyffist profile
2. **Player Profile** — metrics radar + interactive heatmap with action-type slicer
3. **Opportunity Ranking** — players sorted by composite performance/value score

The heatmap (`fact_heatmap_jugador`) is built as a calculated table in **DAX** using the 8 event types that retain `location_x` / `location_y` coordinates.

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
| v12 | **6 La Liga seasons 2014-2020, reduced Power BI schema, single conformity report** |

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
# Clone StatsBomb data
git clone https://github.com/statsbomb/open-data.git

# Run full pipeline
python pipeline/scouting_pipeline.py

# Or with data download included
python pipeline/scouting_pipeline.py --download-data
```

Output CSVs are saved to `output/`, ready to connect with Power BI.

---

## 📁 Repository Structure

```
scouting-futbol/
├── pipeline/
│   ├── scouting_pipeline.py      ← active pipeline (v12)
│   ├── scouting_pipeline_v1.py   ← project history
│   ├── ...
│   └── scouting_pipeline_v12.py
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
