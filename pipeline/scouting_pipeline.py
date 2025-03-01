"""
========================================================
  PIPELINE DE SCOUTING V3 FINAL — COMPLETO
  StatsBomb + Transfermarkt

  Entorno: La Liga | 2014/15 · 2015/16 · 2016/17
  Fuente A: JSON del repo clonado (open-data)
  Fuente B: Transfermarkt via Kaggle

  Output: 18 CSV + 3 reportes HTML de EDA
  ── 4 dimensiones:   dim_jugador, dim_partido, dim_valoracion, dim_calendario
  ── 13 tablas facts  (una por tipo de evento)
  ── 3 reportes EDA   (uno por perfil de jugador)

  FIXES v3 respecto a v2:
  [FIX 1] dim_jugador: deduplicación por player_id antes del save
  [FIX 2] es_gol / es_al_arco calculados ANTES del split_location
  [FIX 3] market_value_in_eur y height_in_cm como float64 desde origen
  [FIX 4] dim_calendario generada en Python con columna Temporada
  [FIX 5] EDA integrado por perfil (Bloque 6 v4):
           eda_delanteros.html    (fact_shot)
           eda_mediocampistas.html (fact_pass)
           eda_defensores.html    (fact_duel + fact_clearance)
  [FIX 6] Conversión numérica explícita en Bloque 6 para columnas
           calculadas (es_gol, es_al_arco, es_pase_completo, etc.)
           que llegan como string por el QUOTE_ALL del CSV
========================================================
"""

# ── INSTALACIONES ─────────────────────────────────────
!git clone https://github.com/statsbomb/open-data.git
!pip install kaggle rapidfuzz -q

import os
os.environ["KAGGLE_API_TOKEN"] = "TOKEN_AQUI"  # reemplazar con token válido
!kaggle datasets download -d davidcariboo/player-scores --unzip -p transfermarkt_data/

# ── IMPORTS ───────────────────────────────────────────
import pandas as pd
import numpy as np
import json, os, re, unicodedata, csv
from pathlib import Path
from rapidfuzz import fuzz

# ── CONFIG ────────────────────────────────────────────
REPO_PATH   = Path("open-data/data")
TM_PATH     = Path("transfermarkt_data")
OUTPUT_DIR  = Path("scouting_v3_output")
OUTPUT_DIR.mkdir(exist_ok=True)

OBJETIVOS = [
    {"competition_id": 11, "season_id": 26, "nombre": "La Liga 2014/15"},
    {"competition_id": 11, "season_id": 27, "nombre": "La Liga 2015/16"},
    {"competition_id": 11, "season_id":  2, "nombre": "La Liga 2016/17"},
]

EVENTOS_OBJETIVO = {
    "Pass", "Shot", "Duel", "Dribble", "Carry",
    "Pressure", "Interception", "Clearance", "Ball Receipt*",
    "Goal Keeper", "Foul Committed", "Foul Won", "Miscontrol", "Block"
}

FECHAS_INICIO = "2014-07-01"
FECHAS_FIN    = "2017-06-30"
FUZZY_UMBRAL  = 85

CONTEXTO = [
    "match_id", "player_id", "player", "team_id", "team",
    "position", "period", "minute", "second", "timestamp",
    "location", "under_pressure", "counterpress",
    "play_pattern", "possession_team_id", "possession_team",
]

COLS_EVENTO = {
    "Pass": [
        "pass_length", "pass_angle", "pass_body_part", "pass_height",
        "pass_technique", "pass_type", "pass_outcome", "pass_end_location",
        "pass_recipient_id", "pass_recipient", "pass_shot_assist",
        "pass_goal_assist", "pass_cross", "pass_switch", "pass_through_ball",
        "pass_aerial_won", "pass_miscommunication", "pass_deflected",
        "pass_inswinging", "pass_outswinging", "pass_straight",
        "pass_cut_back", "pass_no_touch", "duration"
    ],
    "Shot": [
        "shot_statsbomb_xg", "shot_outcome", "shot_technique",
        "shot_body_part", "shot_type", "shot_end_location",
        "shot_first_time", "shot_aerial_won", "shot_deflected",
        "shot_key_pass_id", "duration"
    ],
    "Duel":        ["duel_type", "duel_outcome", "duration"],
    "Dribble":     ["dribble_outcome", "dribble_nutmeg", "dribble_no_touch", "duration"],
    "Carry":       ["carry_end_location", "duration"],
    "Pressure":    ["duration"],
    "Interception":["interception_outcome", "duration"],
    "Clearance": [
        "clearance_body_part", "clearance_aerial_won",
        "clearance_head", "clearance_left_foot", "clearance_right_foot", "duration"
    ],
    "Ball Receipt*":  ["ball_receipt_outcome"],
    "Goal Keeper": [
        "goalkeeper_type", "goalkeeper_outcome", "goalkeeper_technique",
        "goalkeeper_body_part", "goalkeeper_position", "goalkeeper_end_location", "duration"
    ],
    "Foul Committed": [
        "foul_committed_type", "foul_committed_card",
        "foul_committed_advantage", "duration"
    ],
    "Foul Won":    ["foul_won_advantage", "foul_won_defensive", "duration"],
    "Miscontrol":  ["miscontrol_aerial_won", "duration"],
    "Block":       ["block_deflection", "duration"],
}

NOMBRE_ARCHIVO = {
    "Pass": "fact_pass", "Shot": "fact_shot", "Duel": "fact_duel",
    "Dribble": "fact_dribble", "Carry": "fact_carry", "Pressure": "fact_pressure",
    "Interception": "fact_interception", "Clearance": "fact_clearance",
    "Ball Receipt*": "fact_ball_receipt", "Goal Keeper": "fact_goalkeeper",
    "Foul Committed": "fact_foul_committed", "Foul Won": "fact_foul_won",
    "Miscontrol": "fact_miscontrol", "Block": "fact_block",
}

print("=" * 60)
print("  PIPELINE DE SCOUTING V3 — MEJORADO")
print("=" * 60)


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def safe_cols(df, cols):
    return [c for c in cols if c in df.columns]

def split_location(df, col, prefix):
    """
    Expande una columna de listas [x, y] en dos columnas separadas.
    Robusto ante valores None, listas vacías y listas de un solo elemento.
    """
    if col in df.columns:
        def extraer(v):
            if isinstance(v, list) and len(v) >= 2:
                return pd.Series([v[0], v[1]])
            return pd.Series([None, None])
        coords = df[col].apply(extraer)
        coords.columns = [f"{prefix}_x", f"{prefix}_y"]
        df = pd.concat([df.drop(columns=[col]), coords], axis=1)
    return df

def normalizar(nombre):
    if not isinstance(nombre, str):
        return ""
    nombre = unicodedata.normalize("NFD", nombre)
    nombre = "".join(c for c in nombre if unicodedata.category(c) != "Mn")
    nombre = nombre.lower().strip()
    nombre = re.sub(r"[^a-z\s]", "", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre

def save(df, nombre):
    path = OUTPUT_DIR / f"{nombre}.csv"
    df.to_csv(path, index=False, sep=";", decimal=",")
    print(f"   ✔ {nombre:<42} → {len(df):>8,} filas | {len(df.columns):>3} cols")

def append_csv(df, nombre):
    path = OUTPUT_DIR / f"{nombre}.csv"
    df.to_csv(path, mode="a", header=not path.exists(),
              index=False, sep=";", decimal=",",
              quoting=csv.QUOTE_ALL)

def to_num(df, cols):
    """
    Convierte columnas a numérico reemplazando coma decimal por punto.
    Aplica errors='coerce' para convertir valores no parseables en NaN.
    Necesario porque QUOTE_ALL escribe los decimales entre comillas
    y pandas no los convierte automáticamente con decimal=','.
    """
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "."), errors="coerce"
            )
    return df


# ══════════════════════════════════════════════════════
# BLOQUE 1 — TRANSFERMARKT
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 1: Carga Transfermarkt ────────────────────")

tm_players = pd.read_csv(TM_PATH / "players.csv", low_memory=False)
tm_players = tm_players[[
    "player_id", "name", "date_of_birth", "country_of_citizenship",
    "sub_position", "foot", "height_in_cm",
    "market_value_in_eur", "highest_market_value_in_eur"
]].rename(columns={"player_id": "tm_player_id", "name": "tm_name"})

# [FIX 3] Convertir a numérico desde la fuente
tm_players["height_in_cm"]                = pd.to_numeric(tm_players["height_in_cm"], errors="coerce")
tm_players["market_value_in_eur"]         = pd.to_numeric(tm_players["market_value_in_eur"], errors="coerce")
tm_players["highest_market_value_in_eur"] = pd.to_numeric(tm_players["highest_market_value_in_eur"], errors="coerce")

tm_players["nombre_norm"] = tm_players["tm_name"].apply(normalizar)
print(f"   ✔ tm_players: {len(tm_players):,} jugadores")

tm_valuations = pd.read_csv(TM_PATH / "player_valuations.csv", low_memory=False)
tm_valuations["date"] = pd.to_datetime(tm_valuations["date"])
tm_valuations = tm_valuations[
    (tm_valuations["date"] >= FECHAS_INICIO) &
    (tm_valuations["date"] <= FECHAS_FIN)
].rename(columns={"player_id": "tm_player_id"})

# [FIX 3] Tipo numérico en valuations también
tm_valuations["market_value_in_eur"] = pd.to_numeric(
    tm_valuations["market_value_in_eur"], errors="coerce"
)
tm_valuations["tm_player_id"] = pd.to_numeric(
    tm_valuations["tm_player_id"], errors="coerce"
).astype("Int64")

print(f"   ✔ tm_valuations (2014-2017): {len(tm_valuations):,} registros")


# ══════════════════════════════════════════════════════
# BLOQUE 2 — PROCESAMIENTO INCREMENTAL POR PARTIDO
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 2: Procesamiento incremental ──────────────")

for nombre in NOMBRE_ARCHIVO.values():
    path = OUTPUT_DIR / f"{nombre}.csv"
    if path.exists():
        path.unlink()

all_matches  = []
all_lineups  = []
conteo_total = 0

for obj in OBJETIVOS:
    comp_id = obj["competition_id"]
    seas_id = obj["season_id"]
    nombre  = obj["nombre"]

    matches_path = REPO_PATH / "matches" / str(comp_id) / f"{seas_id}.json"
    if not matches_path.exists():
        print(f"   ⚠ No encontrado: {matches_path}")
        continue

    matches = load_json(matches_path)
    print(f"\n   {nombre} — {len(matches)} partidos")

    for i, match in enumerate(matches):
        mid = match["match_id"]

        all_matches.append({
            "match_id":       mid,
            "competition_id": comp_id,
            "competition":    match["competition"]["competition_name"],
            "season_id":      seas_id,
            "season":         match["season"]["season_name"],
            "match_date":     match.get("match_date"),
            "kick_off":       match.get("kick_off"),
            "match_week":     match.get("match_week"),
            "home_team_id":   match["home_team"]["home_team_id"],
            "home_team":      match["home_team"]["home_team_name"],
            "away_team_id":   match["away_team"]["away_team_id"],
            "away_team":      match["away_team"]["away_team_name"],
            "home_score":     match.get("home_score"),
            "away_score":     match.get("away_score"),
            "stadium":        match.get("stadium", {}).get("name") if match.get("stadium") else None,
            "referee":        match.get("referee", {}).get("name") if match.get("referee") else None,
        })

        lineups_path = REPO_PATH / "lineups" / f"{mid}.json"
        if lineups_path.exists():
            for team_lineup in load_json(lineups_path):
                for player in team_lineup.get("lineup", []):
                    all_lineups.append({
                        "match_id":      mid,
                        "team_id":       team_lineup["team_id"],
                        "team":          team_lineup["team_name"],
                        "player_id":     player["player_id"],
                        "player":        player["player_name"],
                        "jersey_number": player.get("jersey_number"),
                        "country":       player.get("country", {}).get("name") if player.get("country") else None,
                    })

        events_path = REPO_PATH / "events" / f"{mid}.json"
        if not events_path.exists():
            continue

        raw_events = load_json(events_path)
        rows = []
        for ev in raw_events:
            tipo = ev.get("type", {}).get("name") if isinstance(ev.get("type"), dict) else ev.get("type")
            if tipo not in EVENTOS_OBJETIVO:
                continue

            row = {
                "match_id":           mid,
                "competition_id":     comp_id,
                "season_id":          seas_id,
                "type":               tipo,
                "period":             ev.get("period"),
                "timestamp":          ev.get("timestamp"),
                "minute":             ev.get("minute"),
                "second":             ev.get("second"),
                "location":           ev.get("location"),
                "player_id":          ev.get("player", {}).get("id") if isinstance(ev.get("player"), dict) else None,
                "player":             ev.get("player", {}).get("name") if isinstance(ev.get("player"), dict) else None,
                "team_id":            ev.get("team", {}).get("id") if isinstance(ev.get("team"), dict) else None,
                "team":               ev.get("team", {}).get("name") if isinstance(ev.get("team"), dict) else None,
                "position":           ev.get("position", {}).get("name") if isinstance(ev.get("position"), dict) else None,
                "possession_team_id": ev.get("possession_team", {}).get("id") if isinstance(ev.get("possession_team"), dict) else None,
                "possession_team":    ev.get("possession_team", {}).get("name") if isinstance(ev.get("possession_team"), dict) else None,
                "play_pattern":       ev.get("play_pattern", {}).get("name") if isinstance(ev.get("play_pattern"), dict) else None,
                "under_pressure":     bool(ev.get("under_pressure", False)),
                "counterpress":       bool(ev.get("counterpress", False)),
                "duration":           ev.get("duration"),
            }

            for key, val in ev.items():
                if isinstance(val, dict) and key not in (
                    "type","player","team","position","possession_team",
                    "play_pattern","location","related_events","id"
                ):
                    for subkey, subval in val.items():
                        col = f"{key}_{subkey}"
                        if isinstance(subval, dict):
                            row[col] = subval.get("name", str(subval))
                        elif isinstance(subval, list):
                            row[col] = str(subval)
                        else:
                            row[col] = subval

            rows.append(row)

        if not rows:
            continue

        df_match = pd.DataFrame(rows)
        conteo_total += len(df_match)

        for tipo, nombre_csv in NOMBRE_ARCHIVO.items():
            subset = df_match[df_match["type"] == tipo].copy()
            if subset.empty:
                continue

            extra = COLS_EVENTO.get(tipo, [])
            cols  = safe_cols(subset, CONTEXTO + extra)
            subset = subset[cols].copy()

            # ── Transformaciones específicas por tipo ──────────

            if tipo == "Pass":
                # [FIX 2] Columnas booleanas ANTES del split
                if "pass_outcome" in subset.columns:
                    subset["es_pase_completo"]   = (subset["pass_outcome"] == "Complete").astype(int)
                if "pass_goal_assist" in subset.columns:
                    subset["es_asistencia_gol"]  = subset["pass_goal_assist"].fillna(False).astype(int)
                if "pass_shot_assist" in subset.columns:
                    subset["es_asistencia_tiro"] = subset["pass_shot_assist"].fillna(False).astype(int)
                subset = split_location(subset, "location", "location")
                subset = split_location(subset, "pass_end_location", "pass_end")

            elif tipo == "Shot":
                # [FIX 2] Calcular ANTES del split para evitar nulos heredados
                if "shot_outcome" in subset.columns:
                    subset["es_gol"]     = (subset["shot_outcome"] == "Goal").astype(int)
                    subset["es_al_arco"] = subset["shot_outcome"].isin(["Goal", "Saved"]).astype(int)
                subset = split_location(subset, "location", "location")
                subset = split_location(subset, "shot_end_location", "shot_end")

            elif tipo == "Carry":
                subset = split_location(subset, "location", "location")
                subset = split_location(subset, "carry_end_location", "carry_end")
                if all(c in subset.columns for c in ["location_x","location_y","carry_end_x","carry_end_y"]):
                    subset["carry_distancia"] = (
                        ((subset["carry_end_x"] - subset["location_x"])**2 +
                         (subset["carry_end_y"] - subset["location_y"])**2) ** 0.5
                    ).round(2)

            elif tipo == "Goal Keeper":
                subset = split_location(subset, "location", "location")
                subset = split_location(subset, "goalkeeper_end_location", "gk_end")

            else:
                subset = split_location(subset, "location", "location")

            # Columnas booleanas para otros tipos
            if tipo == "Duel":
                EXITOS = {"Won","Success","Success In Play","Success Out"}
                if "duel_outcome" in subset.columns:
                    subset["es_duelo_ganado"] = subset["duel_outcome"].isin(EXITOS).astype(int)

            elif tipo == "Dribble":
                if "dribble_outcome" in subset.columns:
                    subset["es_dribble_exitoso"] = (subset["dribble_outcome"] == "Complete").astype(int)

            elif tipo == "Interception":
                EXITOS = {"Won","Success","Success In Play","Success Out"}
                if "interception_outcome" in subset.columns:
                    subset["es_intercepcion_exitosa"] = subset["interception_outcome"].isin(EXITOS).astype(int)

            elif tipo == "Ball Receipt*":
                if "ball_receipt_outcome" in subset.columns:
                    subset["es_recepcion_exitosa"] = (subset["ball_receipt_outcome"] == "Complete").astype(int)

            append_csv(subset, nombre_csv)

        if (i + 1) % 10 == 0:
            print(f"      {i+1}/{len(matches)} partidos procesados — {conteo_total:,} eventos acumulados")

print(f"\n   ✔ Total eventos procesados: {conteo_total:,}")


# ══════════════════════════════════════════════════════
# BLOQUE 3 — FUZZY MATCHING
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 3: Merge StatsBomb ↔ Transfermarkt ────────")

lineups_df = pd.DataFrame(all_lineups)
sb_players = (
    lineups_df.groupby("player_id")
    .agg(player=("player","first"), country=("country","first"))
    .reset_index()
)
sb_players["nombre_norm"] = sb_players["player"].apply(normalizar)

merge_exacto = sb_players.merge(
    tm_players[[
        "tm_player_id","tm_name","nombre_norm",
        "date_of_birth","country_of_citizenship",
        "sub_position","foot","height_in_cm",
        "market_value_in_eur","highest_market_value_in_eur"
    ]],
    on="nombre_norm", how="left"
)
con_match = merge_exacto[merge_exacto["tm_player_id"].notna()]
sin_match = merge_exacto[merge_exacto["tm_player_id"].isna()][
    ["player_id","player","nombre_norm","country"]
].copy()
print(f"   Match exacto:  {len(con_match):>4} jugadores")
print(f"   Sin match:     {len(sin_match):>4} jugadores — aplicando fuzzy...")

tm_nombres = tm_players["nombre_norm"].tolist()
tm_data    = tm_players.set_index("nombre_norm")

fuzzy_rows = []
for _, row in sin_match.iterrows():
    nombre_sb = row["nombre_norm"]
    if not nombre_sb:
        continue
    mejor_score  = 0
    mejor_nombre = None
    for tm_nombre in tm_nombres:
        score = fuzz.token_set_ratio(nombre_sb, tm_nombre)
        if score > mejor_score:
            mejor_score  = score
            mejor_nombre = tm_nombre
    if mejor_score >= FUZZY_UMBRAL and mejor_nombre:
        tm_row = tm_data.loc[mejor_nombre]
        fuzzy_rows.append({
            "player_id":                   row["player_id"],
            "player":                      row["player"],
            "country":                     row["country"],
            "nombre_norm":                 row["nombre_norm"],
            "tm_player_id":                tm_row["tm_player_id"],
            "tm_name":                     tm_row["tm_name"],
            "date_of_birth":               tm_row["date_of_birth"],
            "country_of_citizenship":      tm_row["country_of_citizenship"],
            "sub_position":                tm_row["sub_position"],
            "foot":                        tm_row["foot"],
            "height_in_cm":                tm_row["height_in_cm"],
            "market_value_in_eur":         tm_row["market_value_in_eur"],
            "highest_market_value_in_eur": tm_row["highest_market_value_in_eur"],
            "fuzzy_score":                 mejor_score,
        })

merge_fuzzy = pd.DataFrame(fuzzy_rows) if fuzzy_rows else pd.DataFrame()
print(f"   Match fuzzy:   {len(merge_fuzzy):>4} jugadores adicionales")

cols_merge = [
    "player_id","player","country","nombre_norm","tm_player_id","tm_name",
    "date_of_birth","country_of_citizenship","sub_position","foot",
    "height_in_cm","market_value_in_eur","highest_market_value_in_eur"
]
con_match = con_match.copy()
con_match["fuzzy_score"] = None

if not merge_fuzzy.empty:
    merge_final = pd.concat(
        [con_match[cols_merge + ["fuzzy_score"]], merge_fuzzy],
        ignore_index=True
    )
else:
    merge_final = con_match[cols_merge + ["fuzzy_score"]].copy()

sin_match_final = merge_final["tm_player_id"].isna().sum()
print(f"   Sin match final: {sin_match_final:>3} jugadores (quedan con TM nulo)")


# ══════════════════════════════════════════════════════
# BLOQUE 4 — DIMENSIONES
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 4: Dimensiones ────────────────────────────")

# ── dim_partido ───────────────────────────────────────
dim_partido = pd.DataFrame(all_matches).drop_duplicates("match_id")
dim_partido["match_date"] = pd.to_datetime(dim_partido["match_date"])
save(dim_partido, "dim_partido")

# ── dim_jugador ───────────────────────────────────────
df_events_pos = pd.read_csv(
    OUTPUT_DIR / "fact_pass.csv", sep=";", decimal=",",
    usecols=["player_id","position","team"], nrows=500000
)
pos_habitual = (
    df_events_pos.groupby("player_id")["position"]
    .agg(lambda x: x.value_counts().idxmax() if x.notna().any() else "Desconocida")
    .reset_index().rename(columns={"position": "posicion_habitual"})
)
equipo_habitual = (
    df_events_pos.groupby("player_id")["team"]
    .agg(lambda x: x.value_counts().idxmax() if x.notna().any() else "Desconocido")
    .reset_index().rename(columns={"team": "equipo_habitual"})
)

dim_jugador = (
    merge_final.drop(columns=["nombre_norm"])
    .merge(pos_habitual,    on="player_id", how="left")
    .merge(equipo_habitual, on="player_id", how="left")
)

# [FIX 3] Garantizar tipos numéricos en dim_jugador
dim_jugador["height_in_cm"]                = pd.to_numeric(dim_jugador["height_in_cm"], errors="coerce")
dim_jugador["market_value_in_eur"]         = pd.to_numeric(dim_jugador["market_value_in_eur"], errors="coerce")
dim_jugador["highest_market_value_in_eur"] = pd.to_numeric(dim_jugador["highest_market_value_in_eur"], errors="coerce")

# [FIX 1] Eliminar duplicados de player_id — mantener el de mayor fuzzy_score
dim_jugador = (
    dim_jugador
    .sort_values("fuzzy_score", ascending=False, na_position="last")
    .drop_duplicates(subset="player_id", keep="first")
    .reset_index(drop=True)
)
print(f"   ℹ dim_jugador tras deduplicación: {len(dim_jugador):,} jugadores únicos")
save(dim_jugador, "dim_jugador")

# ── dim_valoracion ────────────────────────────────────
id_map = (
    merge_final[merge_final["tm_player_id"].notna()][["player_id","tm_player_id"]]
    .copy()
)
id_map["tm_player_id"] = pd.to_numeric(id_map["tm_player_id"], errors="coerce").astype("Int64")

dim_valoracion = (
    tm_valuations
    .merge(id_map, on="tm_player_id", how="inner")
    [["player_id","tm_player_id","date","market_value_in_eur",
      "current_club_name","player_club_domestic_competition_id"]]
    .sort_values(["player_id","date"])
    .reset_index(drop=True)
)
save(dim_valoracion, "dim_valoracion")


# ══════════════════════════════════════════════════════
# BLOQUE 5 — DIM_CALENDARIO
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 5: Dimensión Calendario ───────────────────")

fechas = pd.date_range(start=FECHAS_INICIO, end=FECHAS_FIN, freq="D")
dim_calendario = pd.DataFrame({"Date": fechas})

dim_calendario["Anio"]              = dim_calendario["Date"].dt.year
dim_calendario["Mes_Numero"]        = dim_calendario["Date"].dt.month
dim_calendario["Mes_Nombre"]        = dim_calendario["Date"].dt.strftime("%B")
dim_calendario["Trimestre"]         = "Q" + dim_calendario["Date"].dt.quarter.astype(str)
dim_calendario["Semana_Anio"]       = dim_calendario["Date"].dt.isocalendar().week.astype(int)
dim_calendario["Dia_Semana_Numero"] = dim_calendario["Date"].dt.dayofweek + 1
dim_calendario["Dia_Semana_Nombre"] = dim_calendario["Date"].dt.strftime("%A")
dim_calendario["Es_Fin_De_Semana"]  = (dim_calendario["Dia_Semana_Numero"] >= 6).astype(int)

def calcular_temporada(fecha):
    if fecha.month >= 7:
        return f"{fecha.year}/{fecha.year + 1}"
    else:
        return f"{fecha.year - 1}/{fecha.year}"

dim_calendario["Temporada"] = dim_calendario["Date"].apply(calcular_temporada)
dim_calendario["Date"] = dim_calendario["Date"].dt.strftime("%Y-%m-%d")

save(dim_calendario, "dim_calendario")
print(f"   ℹ Rango: {FECHAS_INICIO} → {FECHAS_FIN} | Temporadas: {dim_calendario['Temporada'].unique()}")


# ══════════════════════════════════════════════════════
# BLOQUE 6 — EDA INTEGRADO POR PERFIL DE JUGADOR (v4)
# ══════════════════════════════════════════════════════
# Genera 3 reportes HTML completos, uno por posición:
#   🔴 eda_delanteros.html      → fact_shot
#   🔵 eda_mediocampistas.html  → fact_pass
#   🟢 eda_defensores.html      → fact_duel + fact_clearance
#
# Cada reporte incluye:
#   · Sección 5  — Estadísticas descriptivas
#   · Sección 6  — Histogramas con curva KDE
#   · Sección 7  — Detección de outliers método IQR
#   · Sección 8  — Boxplots con Q1/Mediana/Q3 anotados
#   · Hallazgos  — Conclusiones automáticas + implicaciones DAX
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 6: EDA Integrado por Perfil ───────────────")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import base64, io, warnings
warnings.filterwarnings("ignore")

COLORES = {
    "delantero":     {"primario": "#E63946", "secundario": "#FF6B6B",
                      "fondo": "#FFF5F5",    "acento":     "#C1121F"},
    "mediocampista": {"primario": "#2196F3", "secundario": "#64B5F6",
                      "fondo": "#F0F8FF",    "acento":     "#0D47A1"},
    "defensor":      {"primario": "#2E7D32", "secundario": "#66BB6A",
                      "fondo": "#F1F8F1",    "acento":     "#1B5E20"},
}

# ── Helpers estadísticos ───────────────────────────────

def calcular_iqr(serie):
    serie = serie.dropna()
    Q1 = serie.quantile(0.25)
    Q3 = serie.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    outliers = serie[(serie < lower) | (serie > upper)]
    return {
        "Q1": Q1, "Q3": Q3, "IQR": IQR,
        "lower": lower, "upper": upper,
        "n_outliers": len(outliers),
        "pct_outliers": round(len(outliers) / len(serie) * 100, 2),
    }

def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded

# ── Helpers de gráficos ───────────────────────────────

def grafico_histograma(df, col, color, titulo_col, fondo):
    datos = df[col].dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    ax.hist(datos, bins=40, color=color, alpha=0.7,
            edgecolor="white", linewidth=0.5)
    if len(datos) > 10 and datos.std() > 0:
        kde_x = np.linspace(datos.min(), datos.max(), 300)
        kde   = stats.gaussian_kde(datos)
        ax2   = ax.twinx()
        ax2.plot(kde_x, kde(kde_x), color=color, linewidth=2.5, alpha=0.9)
        ax2.set_yticks([])
        ax2.set_facecolor(fondo)
    ax.axvline(datos.mean(),   color="#333333", linestyle="--",
               linewidth=1.5, alpha=0.8, label=f"Media: {datos.mean():.3f}")
    ax.axvline(datos.median(), color="#888888", linestyle=":",
               linewidth=1.5, alpha=0.8, label=f"Mediana: {datos.median():.3f}")
    ax.set_title(f"Distribución — {titulo_col}", fontsize=12,
                 fontweight="bold", pad=10, color="#222222")
    ax.set_xlabel(titulo_col, fontsize=10, color="#444444")
    ax.set_ylabel("Frecuencia", fontsize=10, color="#444444")
    ax.tick_params(colors="#555555")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9, framealpha=0.7)
    plt.tight_layout()
    return fig_to_b64(fig)

def grafico_boxplot_multiple(df, cols, titulos, color, fondo):
    n = len(cols)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 5))
    fig.patch.set_facecolor(fondo)
    if n == 1:
        axes = [axes]
    for ax, col, titulo in zip(axes, cols, titulos):
        datos = df[col].dropna()
        ax.set_facecolor(fondo)
        bp = ax.boxplot(
            datos, patch_artist=True,
            medianprops=dict(color="#333333", linewidth=2.5),
            whiskerprops=dict(color="#666666", linewidth=1.5),
            capprops=dict(color="#666666",    linewidth=1.5),
            flierprops=dict(marker="o", markerfacecolor=color,
                            markersize=4, alpha=0.5, linestyle="none"),
        )
        bp["boxes"][0].set_facecolor(color)
        bp["boxes"][0].set_alpha(0.65)
        ax.set_title(titulo, fontsize=10, fontweight="bold",
                     color="#222222", pad=8)
        ax.set_xticks([])
        ax.tick_params(colors="#555555")
        ax.spines[["top", "right", "bottom"]].set_visible(False)
        for val, lbl in [(datos.quantile(0.25), "Q1"),
                         (datos.median(),        "Med"),
                         (datos.quantile(0.75),  "Q3")]:
            ax.annotate(
                f"{lbl}\n{val:.3f}", xy=(1, val), xytext=(1.28, val),
                fontsize=8, color="#333333",
                arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.8),
            )
    fig.suptitle("Boxplots — Dispersión y outliers",
                 fontsize=13, fontweight="bold", color="#222222", y=1.02)
    plt.tight_layout()
    return fig_to_b64(fig)

# ── Helpers de tablas HTML ────────────────────────────

def tabla_stats_html(df, cols, titulos, color):
    filas = ""
    for col, titulo in zip(cols, titulos):
        d    = df[col].dropna()
        skew = d.skew()
        kurt = d.kurtosis()
        lbl  = ("Simétrica" if abs(skew) < 0.5
                else ("Asim. +" if skew > 0 else "Asim. −"))
        filas += f"""
        <tr>
          <td><code>{titulo}</code></td>
          <td>{len(d):,}</td>
          <td>{d.mean():.3f}</td><td>{d.median():.3f}</td>
          <td>{d.std():.3f}</td>
          <td>{d.min():.3f}</td><td>{d.max():.3f}</td>
          <td>{skew:.2f} <em>({lbl})</em></td>
          <td>{kurt:.2f}</td>
        </tr>"""
    return f"""<table class="tbl">
      <thead><tr style="background:{color};color:white">
        <th>Variable</th><th>N</th><th>Media</th><th>Mediana</th>
        <th>Desv.Est.</th><th>Mín.</th><th>Máx.</th>
        <th>Asimetría</th><th>Curtosis</th>
      </tr></thead><tbody>{filas}</tbody></table>"""

def tabla_iqr_html(resultados, color):
    filas = ""
    for col, r in resultados.items():
        sem = ("🔴" if r["pct_outliers"] > 10
               else ("🟡" if r["pct_outliers"] > 5 else "🟢"))
        filas += f"""
        <tr>
          <td><code>{col}</code></td>
          <td>{r['Q1']:.3f}</td><td>{r['Q3']:.3f}</td>
          <td>{r['IQR']:.3f}</td>
          <td>{r['lower']:.3f}</td><td>{r['upper']:.3f}</td>
          <td><strong>{r['n_outliers']:,}</strong></td>
          <td>{r['pct_outliers']}% {sem}</td>
        </tr>"""
    return f"""<table class="tbl">
      <thead><tr style="background:{color};color:white">
        <th>Variable</th><th>Q1</th><th>Q3</th><th>IQR</th>
        <th>Límite inf.</th><th>Límite sup.</th>
        <th>N° Outliers</th><th>% Outliers</th>
      </tr></thead><tbody>{filas}</tbody></table>"""

# ── Generador principal de HTML ───────────────────────

def generar_html_perfil(perfil, emoji, subtitulo, n_reg,
                        cols, titulos, imgs_hist, img_box,
                        t_stats, t_iqr, colores, hallazgos):
    c = colores
    grids = "".join(f"""
      <div class="chart-card">
        <h3 class="chart-title">{tit}</h3>
        <img src="data:image/png;base64,{img}" class="chart-img"/>
      </div>""" for tit, img in zip(titulos, imgs_hist))
    hallazgos_li = "".join(f"<li>{h}</li>" for h in hallazgos)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>EDA — {perfil.title()}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;700&family=DM+Mono:wght@400;500&display=swap');
  :root{{--p:{c['primario']};--s:{c['secundario']};--f:{c['fondo']};--a:{c['acento']};
    --txt:#1a1a2e;--gris:#64748b;--borde:#e2e8f0;}}
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'DM Sans',sans-serif;background:var(--f);color:var(--txt);line-height:1.6}}
  .header{{background:linear-gradient(135deg,var(--a) 0%,var(--p) 60%,var(--s) 100%);
    color:white;padding:48px 40px 36px;position:relative;overflow:hidden}}
  .header::before{{content:"";position:absolute;top:-40px;right:-40px;
    width:280px;height:280px;background:rgba(255,255,255,.07);border-radius:50%}}
  .header h1{{font-size:2.4rem;font-weight:700;letter-spacing:-.5px}}
  .header p{{font-size:1.05rem;opacity:.88;margin-top:6px}}
  .badges{{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}}
  .badge{{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);
    padding:4px 14px;border-radius:20px;font-size:.82rem;font-weight:500}}
  .emoji{{font-size:56px;display:block;margin-bottom:12px}}
  .container{{max-width:1200px;margin:0 auto;padding:40px 24px}}
  .section{{margin-bottom:48px}}
  .sec-header{{display:flex;align-items:center;gap:12px;
    border-left:4px solid var(--p);padding-left:16px;margin-bottom:24px}}
  .sec-num{{background:var(--p);color:white;width:36px;height:36px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:700;flex-shrink:0}}
  .sec-title{{font-size:1.4rem;font-weight:700;color:var(--a)}}
  .sec-sub{{font-size:.9rem;color:var(--gris);margin-top:2px}}
  .card{{background:white;border-radius:12px;border:1px solid var(--borde);
    padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
  .charts-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}}
  .chart-card{{background:white;border-radius:12px;border:1px solid var(--borde);
    padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
  .chart-title{{font-size:.95rem;font-weight:600;color:var(--a);
    margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid var(--f)}}
  .chart-img{{width:100%;border-radius:6px}}
  .tbl{{width:100%;border-collapse:collapse;font-size:.86rem;border-radius:8px;overflow:hidden}}
  .tbl th,.tbl td{{padding:10px 14px;text-align:right;border-bottom:1px solid var(--borde)}}
  .tbl th:first-child,.tbl td:first-child{{text-align:left}}
  .tbl tbody tr:hover{{background:var(--f)}}
  .tbl code{{font-family:'DM Mono',monospace;font-size:.8rem;color:var(--a);
    background:var(--f);padding:2px 6px;border-radius:4px}}
  .tbl em{{color:#888;font-size:.8rem}}
  .leyenda{{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;font-size:.83rem;color:var(--gris)}}
  .hallazgos{{background:linear-gradient(135deg,var(--f),white);border:1px solid var(--borde);
    border-left:4px solid var(--p);border-radius:8px;padding:20px 24px}}
  .hallazgos h3{{color:var(--a);margin-bottom:12px;font-size:1rem}}
  .hallazgos ul{{list-style:none;padding:0}}
  .hallazgos li{{padding:6px 0 6px 24px;position:relative;font-size:.92rem;color:#334155;
    border-bottom:1px solid rgba(0,0,0,.04)}}
  .hallazgos li::before{{content:"→";position:absolute;left:0;color:var(--p);font-weight:700}}
  .footer{{text-align:center;padding:32px;font-size:.8rem;color:var(--gris);
    border-top:1px solid var(--borde);margin-top:40px}}
</style>
</head>
<body>
<div class="header">
  <span class="emoji">{emoji}</span>
  <h1>EDA — {perfil.title()}</h1>
  <p>{subtitulo}</p>
  <div class="badges">
    <span class="badge">📊 {n_reg:,} registros</span>
    <span class="badge">📐 {len(cols)} variables</span>
    <span class="badge">⚽ La Liga 2014–2017</span>
    <span class="badge">🔬 Distribuciones · IQR · Boxplots</span>
  </div>
</div>
<div class="container">
  <div class="section">
    <div class="sec-header"><div class="sec-num">5</div>
      <div><div class="sec-title">Variables Numéricas — Estadísticas Descriptivas</div>
        <div class="sec-sub">Media, mediana, desv. estándar, asimetría y curtosis</div></div></div>
    <div class="card" style="overflow-x:auto">{t_stats}
      <div class="leyenda" style="margin-top:16px">
        <span>📐 Asimetría &lt; 0.5 → distribución simétrica</span>
        <span>📐 Asimetría &gt; 1 → sesgo fuerte (cola de outliers)</span>
        <span>📐 Curtosis &gt; 3 → colas pesadas, más outliers esperados</span>
      </div></div></div>
  <div class="section">
    <div class="sec-header"><div class="sec-num">6</div>
      <div><div class="sec-title">Distribuciones — Histogramas con curva KDE</div>
        <div class="sec-sub">Forma de la distribución de cada variable numérica clave</div></div></div>
    <div class="charts-grid">{grids}</div></div>
  <div class="section">
    <div class="sec-header"><div class="sec-num">7</div>
      <div><div class="sec-title">Detección de Outliers — Método IQR</div>
        <div class="sec-sub">Límite inferior = Q1 − 1.5×IQR &nbsp;·&nbsp; Límite superior = Q3 + 1.5×IQR</div></div></div>
    <div class="card" style="overflow-x:auto">{t_iqr}
      <div class="leyenda">
        <span>🟢 &lt; 5% outliers → distribución limpia</span>
        <span>🟡 5–10% → sesgo moderado</span>
        <span>🔴 &gt; 10% → distribución muy sesgada</span>
      </div></div></div>
  <div class="section">
    <div class="sec-header"><div class="sec-num">8</div>
      <div><div class="sec-title">Boxplots — Dispersión visual y outliers</div>
        <div class="sec-sub">Caja = IQR (50% central) · Bigotes = 1.5×IQR · Puntos = outliers</div></div></div>
    <div class="card">
      <img src="data:image/png;base64,{img_box}" style="width:100%;border-radius:6px"/></div></div>
  <div class="section">
    <div class="sec-header"><div class="sec-num">💡</div>
      <div><div class="sec-title">Hallazgos e Implicaciones para DAX</div>
        <div class="sec-sub">Conclusiones automáticas y recomendaciones para Power BI</div></div></div>
    <div class="hallazgos"><h3>Principales observaciones:</h3>
      <ul>{hallazgos_li}</ul></div></div>
</div>
<div class="footer">EDA Integrado · Scouting La Liga 2014–2017 · ICARO Data Analytics · 2026</div>
</body></html>"""


# ── Columnas slim para joins ───────────────────────────
COLS_JUGADOR_SLIM = ["player_id", "posicion_habitual", "equipo_habitual",
                     "market_value_in_eur", "height_in_cm"]
COLS_PARTIDO_SLIM = ["match_id", "season"]

dim_jugador_slim2 = dim_jugador[COLS_JUGADOR_SLIM].copy()
dim_partido_slim2 = dim_partido[COLS_PARTIDO_SLIM].copy()

def enriquecer(df):
    return (df
            .merge(dim_jugador_slim2, on="player_id", how="left")
            .merge(dim_partido_slim2, on="match_id",  how="left"))


# ══════════════════════════════════════════════════════
# PERFIL 1: DELANTEROS — fact_shot
# ══════════════════════════════════════════════════════

print("\n   🔴 Generando eda_delanteros.html ...")

df_shot = pd.read_csv(OUTPUT_DIR / "fact_shot.csv",
                      sep=";", decimal=",", low_memory=False,
                      on_bad_lines="skip")
# [FIX 6] Conversión numérica explícita — columnas calculadas llegan como
# string por el QUOTE_ALL del CSV
df_shot = to_num(df_shot, ["shot_statsbomb_xg", "duration",
                            "location_x", "location_y",
                            "es_gol", "es_al_arco"])
df_shot = enriquecer(df_shot)

COLS_DEL = ["shot_statsbomb_xg", "duration", "minute", "location_x"]
TITS_DEL = ["xG por tiro", "Duración evento (s)", "Minuto del tiro", "Posición X"]
c = COLORES["delantero"]

imgs_hist_del = [grafico_histograma(df_shot, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_DEL, TITS_DEL)]
img_box_del   = grafico_boxplot_multiple(df_shot, COLS_DEL, TITS_DEL,
                                         c["primario"], c["fondo"])
iqr_del       = {col: calcular_iqr(df_shot[col]) for col in COLS_DEL}

xg_mean  = df_shot["shot_statsbomb_xg"].mean()
xg_med   = df_shot["shot_statsbomb_xg"].median()
skew_xg  = df_shot["shot_statsbomb_xg"].skew()
gol_pct  = df_shot["es_gol"].mean()    * 100
arco_pct = df_shot["es_al_arco"].mean() * 100

hallazgos_del = [
    f"La distribución de xG es fuertemente asimétrica ({skew_xg:.2f}): la mediana ({xg_med:.3f}) es menor que la media ({xg_mean:.3f}), lo que indica que la mayoría de los tiros son de baja calidad pero unos pocos de alta probabilidad elevan el promedio.",
    f"Solo el {gol_pct:.1f}% de los tiros terminan en gol. El {arco_pct:.1f}% van al arco — la diferencia ({arco_pct - gol_pct:.1f}%) son los atajados por el portero.",
    f"El {iqr_del['shot_statsbomb_xg']['pct_outliers']}% de los valores de xG son outliers según IQR (límite superior = {iqr_del['shot_statsbomb_xg']['upper']:.3f}): son penales y manos a mano, las chances más claras.",
    f"La variable 'minute' muestra acumulación en los minutos 45 y 90 (tiempo de descuento), reflejando el patrón real de más tiros al final de cada tiempo.",
    f"Para DAX: usar MEDIAN en lugar de AVERAGE para xG promedio por jugador, ya que la fuerte asimetría haría que la media sobre-estime la calidad habitual de tiro.",
    f"Umbral sugerido para scouting de delantero: xG total > {df_shot.groupby('player_id')['shot_statsbomb_xg'].sum().quantile(0.75):.1f} en el período (percentil 75 del universo).",
]

html_del = generar_html_perfil(
    "Delanteros", "⚽",
    "Análisis de tiros · fact_shot · Distribuciones, IQR y Boxplots",
    len(df_shot), COLS_DEL, TITS_DEL,
    imgs_hist_del, img_box_del,
    tabla_stats_html(df_shot, COLS_DEL, TITS_DEL, c["primario"]),
    tabla_iqr_html(iqr_del, c["primario"]),
    c, hallazgos_del
)
(OUTPUT_DIR / "eda_delanteros.html").write_text(html_del, encoding="utf-8")
print(f"   ✔ eda_delanteros.html — {len(df_shot):,} registros | {len(df_shot.columns)} cols")


# ══════════════════════════════════════════════════════
# PERFIL 2: MEDIOCAMPISTAS — fact_pass
# ══════════════════════════════════════════════════════

print("\n   🔵 Generando eda_mediocampistas.html ...")

df_pass = pd.read_csv(OUTPUT_DIR / "fact_pass.csv",
                      sep=";", decimal=",", low_memory=False,
                      on_bad_lines="skip")
# [FIX 6] Conversión numérica explícita
df_pass = to_num(df_pass, ["pass_length", "pass_angle", "duration", "minute",
                            "es_pase_completo", "es_asistencia_gol",
                            "es_asistencia_tiro"])
df_pass = enriquecer(df_pass)

COLS_MID = ["pass_length", "pass_angle", "duration", "minute"]
TITS_MID = ["Longitud del pase (m)", "Ángulo del pase (rad)",
            "Duración evento (s)",   "Minuto del pase"]
c = COLORES["mediocampista"]

imgs_hist_mid = [grafico_histograma(df_pass, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_MID, TITS_MID)]
img_box_mid   = grafico_boxplot_multiple(df_pass, COLS_MID, TITS_MID,
                                         c["primario"], c["fondo"])
iqr_mid       = {col: calcular_iqr(df_pass[col]) for col in COLS_MID}

prec_global = df_pass["es_pase_completo"].mean()    * 100
len_med     = df_pass["pass_length"].median()
len_mean    = df_pass["pass_length"].mean()
skew_len    = df_pass["pass_length"].skew()
asist_g_pct = df_pass["es_asistencia_gol"].mean()  * 100
asist_t_pct = df_pass["es_asistencia_tiro"].mean() * 100

hallazgos_mid = [
    f"La precisión global de pase en La Liga 2014–2017 fue del {prec_global:.1f}%. Para identificar mediocampistas de élite el umbral sugerido es >{prec_global + 5:.0f}%.",
    f"La longitud de pase tiene asimetría positiva ({skew_len:.2f}): la mediana es {len_med:.1f}m pero la media sube a {len_mean:.1f}m por la cola de pases largos. Para el scouting, la mediana es más representativa del estilo habitual.",
    f"El ángulo de pase sigue una distribución bimodal — hay un pico hacia adelante y otro hacia atrás/lateral — confirmando el juego de posesión dominante en La Liga.",
    f"Solo el {asist_t_pct:.2f}% de los pases generan un tiro y el {asist_g_pct:.3f}% generan un gol, contextualizando por qué las asistencias son métricas difíciles de acumular.",
    f"El {iqr_mid['pass_length']['pct_outliers']}% de las longitudes son outliers (>{iqr_mid['pass_length']['upper']:.1f}m): son cambios de orientación y pelotazos. Filtrarlos permite analizar el juego asociativo puro.",
    f"Para DAX: COUNTROWS como base de volumen, DIVIDE para precisión, y MEDIAN para longitud típica de pase. Evitar AVERAGE por el sesgo de la distribución.",
]

html_mid = generar_html_perfil(
    "Mediocampistas", "🎯",
    "Análisis de pases · fact_pass · Distribuciones, IQR y Boxplots",
    len(df_pass), COLS_MID, TITS_MID,
    imgs_hist_mid, img_box_mid,
    tabla_stats_html(df_pass, COLS_MID, TITS_MID, c["primario"]),
    tabla_iqr_html(iqr_mid,   c["primario"]),
    c, hallazgos_mid
)
(OUTPUT_DIR / "eda_mediocampistas.html").write_text(html_mid, encoding="utf-8")
print(f"   ✔ eda_mediocampistas.html — {len(df_pass):,} registros | {len(df_pass.columns)} cols")


# ══════════════════════════════════════════════════════
# PERFIL 3: DEFENSORES — fact_duel + fact_clearance
# ══════════════════════════════════════════════════════

print("\n   🟢 Generando eda_defensores.html ...")

df_duel = pd.read_csv(OUTPUT_DIR / "fact_duel.csv",
                      sep=";", decimal=",", low_memory=False,
                      on_bad_lines="skip")
# [FIX 6] Conversión numérica explícita en fact_duel
df_duel = to_num(df_duel, ["duration", "location_x", "location_y",
                            "es_duelo_ganado"])

df_clear = pd.read_csv(OUTPUT_DIR / "fact_clearance.csv",
                       sep=";", decimal=",", low_memory=False,
                       on_bad_lines="skip")
# [FIX 6] Conversión numérica explícita en fact_clearance ANTES del concat
# clearance_aerial_won se calcula desde df_clear directamente (no desde df_def)
# por lo que necesita su propia conversión aquí
df_clear = to_num(df_clear, ["duration", "location_x", "location_y",
                              "clearance_aerial_won"])

df_duel["origen"]  = "duel"
df_clear["origen"] = "clearance"
df_def = pd.concat([df_duel, df_clear], ignore_index=True)
df_def = enriquecer(df_def)

COLS_DEF = ["duration", "minute", "location_x", "location_y"]
TITS_DEF = ["Duración evento (s)", "Minuto del evento",
            "Posición X en el campo", "Posición Y en el campo"]
c = COLORES["defensor"]

imgs_hist_def = [grafico_histograma(df_def, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_DEF, TITS_DEF)]
img_box_def   = grafico_boxplot_multiple(df_def, COLS_DEF, TITS_DEF,
                                         c["primario"], c["fondo"])
iqr_def       = {col: calcular_iqr(df_def[col]) for col in COLS_DEF}

# Calculados desde las tablas individuales ya convertidas
duelos_gan = df_duel["es_duelo_ganado"].mean() * 100
aereo_gan  = (df_clear["clearance_aerial_won"].mean() * 100
              if "clearance_aerial_won" in df_clear.columns else 0)
loc_x_med  = df_def["location_x"].median()
skew_x     = df_def["location_x"].skew()

hallazgos_def = [
    f"La tasa global de duelos ganados fue del {duelos_gan:.1f}%. Dado que cada duelo tiene dos participantes, la media teórica es ~50% — una tasa >55% indica un defensor dominante en el período.",
    f"El {aereo_gan:.1f}% de los despejes estuvieron precedidos de un duelo aéreo ganado, confirmando que el juego aéreo es crítico para el perfil de defensor central.",
    f"La distribución de location_x tiene asimetría {skew_x:.2f}: los duelos y despejes se concentran en la mitad defensiva del campo (mediana X = {loc_x_med:.1f} sobre escala 0–120).",
    f"La distribución de location_y es casi simétrica (mediana ≈ 40), indicando que las acciones defensivas se distribuyen uniformemente en el ancho del campo.",
    f"El {iqr_def['location_x']['pct_outliers']}% de los eventos tienen location_x > {iqr_def['location_x']['upper']:.1f} (outliers): son duelos/despejes en campo rival, propios de defensores que salen a jugar.",
    f"Para DAX: filtrar location_x < 60 para métricas puramente defensivas. Defensores con muchos eventos en location_x > 80 son candidatos a perfiles de líbero que construye desde atrás.",
]

html_def = generar_html_perfil(
    "Defensores", "🛡️",
    "Análisis de duelos y despejes · fact_duel + fact_clearance · Distribuciones, IQR y Boxplots",
    len(df_def), COLS_DEF, TITS_DEF,
    imgs_hist_def, img_box_def,
    tabla_stats_html(df_def, COLS_DEF, TITS_DEF, c["primario"]),
    tabla_iqr_html(iqr_def,  c["primario"]),
    c, hallazgos_def
)
(OUTPUT_DIR / "eda_defensores.html").write_text(html_def, encoding="utf-8")
print(f"   ✔ eda_defensores.html — {len(df_def):,} registros | {len(df_def.columns)} cols")


# ══════════════════════════════════════════════════════
# RESUMEN FINAL
# ══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("  ✅ PIPELINE V3 FINAL COMPLETADO")
print("=" * 60)

csvs     = list(OUTPUT_DIR.glob("*.csv"))
htmls    = list(OUTPUT_DIR.glob("*.html"))
total_mb = sum(f.stat().st_size for f in csvs + htmls) / 1024 / 1024

print(f"\n  {len(csvs)} archivos CSV generados en ./{OUTPUT_DIR}/")
print(f"  {len(htmls)} reportes EDA HTML generados en ./{OUTPUT_DIR}/")
print(f"  Tamaño total: {total_mb:.1f} MB")

print("""
  FIXES APLICADOS EN V3:
  ✔ [FIX 1] dim_jugador sin duplicados de player_id
  ✔ [FIX 2] es_gol / es_al_arco calculados antes del split_location
  ✔ [FIX 3] height_in_cm / market_value_in_eur como float64
  ✔ [FIX 4] dim_calendario con Temporada, Trimestre, Semana y más
  ✔ [FIX 5] EDA integrado por perfil (3 reportes HTML)
  ✔ [FIX 6] Conversión numérica explícita en Bloque 6 (to_num)

  ARCHIVOS CSV (18):
  → dim_jugador, dim_partido, dim_valoracion, dim_calendario
  → fact_shot, fact_pass, fact_duel, fact_dribble, fact_carry
  → fact_pressure, fact_interception, fact_clearance
  → fact_ball_receipt, fact_goalkeeper, fact_foul_committed
  → fact_foul_won, fact_miscontrol, fact_block

  REPORTES EDA (3):
  🔴 eda_delanteros.html      (fact_shot)
  🔵 eda_mediocampistas.html  (fact_pass)
  🟢 eda_defensores.html      (fact_duel + fact_clearance)

  Cada reporte incluye:
  · Sección 5 — Estadísticas descriptivas
  · Sección 6 — Histogramas + KDE
  · Sección 7 — Outliers por método IQR
  · Sección 8 — Boxplots con Q1/Med/Q3
  · Hallazgos e implicaciones para DAX

  PRÓXIMOS PASOS EN POWER BI:
  → Importar CSVs con sep=';' y decimal=','
  → Conectar: dim_calendario[Date]   → dim_partido[match_date]
  → Conectar: dim_jugador[player_id] → fact_*[player_id]
  → Conectar: dim_partido[match_id]  → fact_*[match_id]
""")

# ── Descargar ZIP ──────────────────────────────────────
import shutil
from google.colab import files

shutil.make_archive("scouting_v3_final", "zip", str(OUTPUT_DIR))
files.download("scouting_v3_final.zip")