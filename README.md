# ⚽ Sistema de Scouting de Fútbol
### Identificación de jugadores de alto rendimiento y bajo costo para un club de filosofía cruyffista

## 🎯 Problema de negocio

Un club recién ascendido a la Primera División española necesita reforzar su plantilla con jugadores de **alto rendimiento y bajo costo de mercado**, respetando una filosofía de juego **cruyffista**: posesión, presión alta y construcción desde atrás.

El sistema responde tres preguntas concretas:
- **¿Qué se analiza?** Acciones individuales reales en cancha (pases, tiros, duelos, presiones, conducciones) cruzadas con valor de mercado histórico.
- **¿Para quién?** La dirección deportiva y el cuerpo técnico — un decisor que necesita una herramienta de descubrimiento rápido, no un reporte estático.
- **¿Qué decisiones habilita?** Priorizar candidatos por posición, descartar perfiles que no encajan en el estilo, y detectar oportunidades de mercado.

---

## 🗃️ Fuentes de datos

| Fuente | Descripción | Acceso |
|---|---|---|
| **StatsBomb Open Data** | Eventos partido a partido en JSON — cada acción con coordenadas, timestamp y atributos por tipo | `statsbombpy` / repo clonado |
| **Transfermarkt via Kaggle** | Posición, altura, pie dominante e **historial de valoraciones fechadas** por jugador | API Kaggle (`davidcariboo/player-scores`) |

> El cruce de ambas fuentes mediante **fuzzy matching** (token_set_ratio + bonus de número de camiseta) es el núcleo técnico del pipeline.

---

## 🏗️ Arquitectura del pipeline

El pipeline ETL sigue un modelo **estrella** con 4 dimensiones y hasta 14 tablas de hechos:

```
StatsBomb JSON  ──┐
                  ├──► ETL Python ──► Star Schema CSV ──► Power BI Dashboard
Transfermarkt  ───┘
```

**Dimensiones:**
- `dim_jugador` — perfil, posición habitual, equipo
- `dim_partido` — liga, temporada, fecha
- `dim_valoracion` — pico de valor de mercado en el período analizado
- `dim_calendario` — jerarquía temporal

**Facts principales:**
`fact_pass` · `fact_shot` · `fact_duel` · `fact_dribble` · `fact_carry` · `fact_pressure` · `fact_interception` · `fact_clearance` · `fact_foul` · `fact_block` · `fact_ball_receipt` · `fact_miscontrol` · `fact_goalkeeper` · `fact_minutes`

---

## 📊 Cobertura de datos

| Liga | Temporadas | Partidos aprox. |
|---|---|---|
| La Liga (España) | 2014/15 · 2015/16 · 2016/17 · 2017/18 · 2018/19 · 2019/20 | ~2.280 |

> Se excluye la temporada 2020/21 por distorsión COVID. Otras ligas europeas se descartaron por cobertura insuficiente en StatsBomb (una sola temporada disponible).

---

## 🧠 KPIs y filosofía de evaluación

Cada posición tiene un perfil cruyffista con métricas ponderadas:

| Posición | Foco principal |
|---|---|
| **9 falso / Delantero** | xG, presión alta, movilidad entre líneas |
| **Mediocampista** | Pases progresivos, conducciones, acciones bajo presión |
| **Defensor central** | Intercepciones en campo rival, progresión desde el fondo |
| **Lateral** | Duelos 1v1, conducciones hacia el centro, pases al interior |

Los percentiles **P50 / P75 / P90** por posición son el umbral de corte para el dashboard.

---

## 📈 Dashboard Power BI

El tablero tiene 3 páginas:

1. **Selector de posición** — filtro unificado por perfil cruyffista
2. **Perfil de jugador** — radar de métricas + heatmap interactivo con slicer de tipo de acción
3. **Ranking de oportunidades** — jugadores ordenados por score compuesto rendimiento/valor

El heatmap (`fact_heatmap_jugador`) se construye como tabla calculada en **DAX** usando los 8 tipos de eventos que retienen coordenadas `location_x` / `location_y`.

---

## 🗂️ Evolución del proyecto

Este repositorio documenta la evolución completa del sistema — cada commit es una versión funcional:

| Versión | Hito principal |
|---|---|
| v1 | Extracción monolítica StatsBomb — 4 temporadas, 5 tipos de evento, CSV master |
| v2 | Primer star schema — 6 CSVs (2 dims + 4 facts) + tabla resumen por jugador |
| v3 | ETL completo — 18 CSV, 4 dims, 13 facts, 3 reportes EDA por perfil cruyffista |
| v4 | EDA filosófico cruyffista — 4 perfiles + validación cruzada camiseta StatsBomb↔TM |
| v4.3 | Deduplicación en dos criterios — exacto primero, fuzzy de desempate con bonus camiseta |
| v5 | Pipeline ejecutable sin Colab — argparse, coordenadas x/y preservadas, booleanos robustos |
| v7 | Scatter interactivo JS + EDA orientado a umbrales P50/P75/P90 para criterios DAX |
| v9 | `fact_minutes` nuevo, EDA pedagógico reordenado, flags 0/1 canónicos por fact |
| v10 | Schema rectangular canónico por fact — CSV sin columnas desalineadas |
| v11 | Valoraciones históricas Transfermarkt — pico de mercado en período analizado 2014-2017 |
| v12 | **6 temporadas La Liga 2014-2020, esquema reducido Power BI, reporte de conformidad único** |

---

## 🚀 Cómo ejecutar

### Requisitos
```bash
pip install statsbombpy rapidfuzz pandas numpy
```

### Datos de Transfermarkt
```bash
pip install kaggle
export KAGGLE_API_TOKEN="tu_token_aqui"
kaggle datasets download -d davidcariboo/player-scores --unzip -p transfermarkt_data/
```

### Ejecutar el pipeline
```bash
# Clonar datos StatsBomb
git clone https://github.com/statsbomb/open-data.git

# Ejecutar pipeline completo
python pipeline/scouting_pipeline.py

# O con descarga incluida
python pipeline/scouting_pipeline.py --download-data
```

Los CSV de salida quedan en `output/` listos para conectar con Power BI.

---

## 📁 Estructura del repositorio

```
scouting-futbol/
├── pipeline/
│   ├── scouting_pipeline.py      ← pipeline activo (v12)
│   ├── scouting_pipeline_v1.py   ← historia del proyecto
│   ├── ...
│   └── scouting_pipeline_v12.py
├── output/                        ← CSVs generados (ignorados por .gitignore)
├── .gitignore
└── README.md
```

---

## 👤 Autor

**Andrés Jano Coriatonanez**
Trabajo Final Integrador — Curso de Data Analytics · ICARO / FCEFyN UNC · 2025

---

*Datos de StatsBomb utilizados bajo licencia [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Datos de Transfermarkt vía Kaggle bajo términos del dataset original.*
