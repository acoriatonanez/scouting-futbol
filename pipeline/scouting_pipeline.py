"""
========================================================
  PIPELINE DE SCOUTING V4.3 — COMPLETO
  StatsBomb + Transfermarkt
 
  Entorno: La Liga | 2014/15 · 2015/16 · 2016/17
  Fuente A: JSON del repo clonado (open-data)
  Fuente B: Transfermarkt via Kaggle
 
  Output: 18 CSV + 4 reportes HTML de EDA
  ── 4 dimensiones:   dim_jugador, dim_partido, dim_valoracion, dim_calendario
  ── 13 tablas facts  (una por tipo de evento)
  ── 4 reportes EDA   (uno por perfil filosófico)
 
  FIXES v4 respecto a v3:
  [FIX 1] dim_jugador: deduplicación por player_id
  [FIX 2] es_gol / es_al_arco calculados ANTES del split_location
  [FIX 3] market_value_in_eur y height_in_cm como float64 desde origen
  [FIX 4] dim_calendario generada en Python con columna Temporada
  [FIX 5] Bloque 6 v5: EDA filosófico por perfil cruyffista
           eda_v4_delanteros.html     (9 falso: presión, movilidad, xG)
           eda_v4_mediocampistas.html (entre líneas: progresión, presión)
           eda_v4_defensores.html     (líbero moderno: zonas altas, salida)
           eda_v4_laterales.html      (lateral invertido: versatilidad)
  [FIX 6] Conversión numérica explícita (to_num) para columnas calculadas
  [FIX 7] Sección de valoraciones: scatter rendimiento vs valor de mercado
  [FIX 8] Validación cruzada de número de camiseta StatsBomb ↔ Transfermarkt
           Fuente TM: game_lineups.csv (shirt_number por partido, no estático)
           Fuente SB: all_lineups (jersey_number por partido)
           Resultado: columna match_confidence = fuzzy_score + 10 si coincide
  [FIX 9] Deduplicación con dos criterios separados en Bloque 4:
           1° es_exacto (match por nombre exacto siempre gana)
           2° match_confidence (desempate por score + bonus camiseta)
========================================================
"""
 
# ── INSTALACIONES ─────────────────────────────────────
!git clone https://github.com/statsbomb/open-data.git
!pip install kaggle rapidfuzz -q
 
import os
os.environ["KAGGLE_API_TOKEN"] = "KGAT_094108e46ec956df71ce0a41311f9652"  # reemplazar con token válido
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
OUTPUT_DIR  = Path("scouting_v4_output")
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
print("  PIPELINE DE SCOUTING V4")
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
    Necesario porque QUOTE_ALL escribe los decimales entre comillas.
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
tm_valuations["market_value_in_eur"] = pd.to_numeric(
    tm_valuations["market_value_in_eur"], errors="coerce"
)
tm_valuations["tm_player_id"] = pd.to_numeric(
    tm_valuations["tm_player_id"], errors="coerce"
).astype("Int64")
print(f"   ✔ tm_valuations (2014-2017): {len(tm_valuations):,} registros")
tm_lineups_raw = pd.read_csv(TM_PATH / "game_lineups.csv", low_memory=False)
tm_lineups_raw["date"] = pd.to_datetime(tm_lineups_raw["date"], errors="coerce")
tm_lineups_raw = tm_lineups_raw[
    (tm_lineups_raw["date"] >= FECHAS_INICIO) &
    (tm_lineups_raw["date"] <= FECHAS_FIN)
]
tm_lineups_raw["player_id"] = pd.to_numeric(
    tm_lineups_raw["player_id"], errors="coerce"
).astype("Int64")

tm_jersey = (
    tm_lineups_raw.groupby("player_id")["number"]
    .agg(lambda x: x.value_counts().idxmax() if x.notna().any() else None)
    .reset_index()
    .rename(columns={"player_id": "tm_player_id_int",
                     "number": "jersey_tm"})
)
tm_jersey["tm_player_id_int"] = tm_jersey["tm_player_id_int"].astype("Int64")
print(f"   ✔ tm_jersey: {len(tm_jersey):,} jugadores con número de camiseta TM")
 
 
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
 
            if tipo == "Pass":
                if "pass_outcome" in subset.columns:
                    subset["es_pase_completo"]   = (subset["pass_outcome"] == "Complete").astype(int)
                if "pass_goal_assist" in subset.columns:
                    subset["es_asistencia_gol"]  = subset["pass_goal_assist"].fillna(False).astype(int)
                if "pass_shot_assist" in subset.columns:
                    subset["es_asistencia_tiro"] = subset["pass_shot_assist"].fillna(False).astype(int)
                subset = split_location(subset, "location", "location")
                subset = split_location(subset, "pass_end_location", "pass_end")
 
            elif tipo == "Shot":
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
 
# [FIX 8] Número de camiseta más frecuente por jugador en StatsBomb (moda)
sb_jersey = (
    pd.DataFrame(all_lineups)
    .groupby("player_id")["jersey_number"]
    .agg(lambda x: x.value_counts().idxmax() if x.notna().any() else None)
    .reset_index()
    .rename(columns={"jersey_number": "jersey_sb"})
)
print(f"   ✔ sb_jersey: {len(sb_jersey):,} jugadores con número de camiseta StatsBomb")
 
 
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
 
# [FIX 8] Validación cruzada de número de camiseta
# ── Merge jersey StatsBomb (por player_id) ─────────
merge_final = merge_final.merge(sb_jersey, on="player_id", how="left")
 
# ── Merge jersey Transfermarkt (por tm_player_id) ──
# Convertir tm_player_id a Int64 para que el join no falle por tipo
merge_final["tm_player_id_int"] = pd.to_numeric(
    merge_final["tm_player_id"], errors="coerce"
).astype("Int64")
merge_final = merge_final.merge(
    tm_jersey,  # ya tiene tm_player_id_int como Int64
    on="tm_player_id_int", how="left"
).drop(columns=["tm_player_id_int"])
 
# ── Score de confianza mejorado ─────────────────────
# Exactos tienen fuzzy_score = None → los ponemos en 100
merge_final["fuzzy_score"]       = merge_final["fuzzy_score"].fillna(100)
merge_final["camiseta_coincide"] = (
    merge_final["jersey_sb"].notna() &
    merge_final["jersey_tm"].notna() &
    (merge_final["jersey_sb"] == merge_final["jersey_tm"])
)
merge_final["match_confidence"] = (
    merge_final["fuzzy_score"] +
    merge_final["camiseta_coincide"].fillna(False).astype(int) * 10
)
 
n_validados = merge_final["camiseta_coincide"].sum()
n_conflicto = (
    merge_final["tm_player_id"].notna() &
    merge_final["jersey_sb"].notna() &
    merge_final["jersey_tm"].notna() &
    ~merge_final["camiseta_coincide"]
).sum()
print(f"   ✔ Camiseta coincide:  {n_validados:>3} jugadores (match_confidence +10)")
print(f"   ⚠ Camiseta conflicto: {n_conflicto:>3} jugadores (revisar manualmente)")
 
 
# ══════════════════════════════════════════════════════
# BLOQUE 4 — DIMENSIONES
# ══════════════════════════════════════════════════════
 
print("\n── BLOQUE 4: Dimensiones ────────────────────────────")
 
dim_partido = pd.DataFrame(all_matches).drop_duplicates("match_id")
dim_partido["match_date"] = pd.to_datetime(dim_partido["match_date"])
save(dim_partido, "dim_partido")
 
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
 
dim_jugador["height_in_cm"]                = pd.to_numeric(dim_jugador["height_in_cm"], errors="coerce")
dim_jugador["market_value_in_eur"]         = pd.to_numeric(dim_jugador["market_value_in_eur"], errors="coerce")
dim_jugador["highest_market_value_in_eur"] = pd.to_numeric(dim_jugador["highest_market_value_in_eur"], errors="coerce")
 
# [FIX 9] Deduplicación con dos criterios separados:
# 1° es_exacto: un match exacto por nombre SIEMPRE gana sobre uno fuzzy,
#    incluso si el fuzzy tiene bonus de camiseta (confidence 109 > exacto 100).
# 2° match_confidence: desempate entre matches del mismo tipo.
# Esto evita que fuzzy+camiseta desplace a exacto sin camiseta disponible.
dim_jugador = (
    dim_jugador
    .assign(es_exacto=(dim_jugador["fuzzy_score"] == 100).astype(int))
    .sort_values(
        ["es_exacto", "match_confidence"],
        ascending=[False, False],
        na_position="last"
    )
    .drop_duplicates(subset="player_id", keep="first")
    .drop(columns=["es_exacto"])
    .reset_index(drop=True)
)
print(f"   ℹ dim_jugador tras deduplicación: {len(dim_jugador):,} jugadores únicos")
save(dim_jugador, "dim_jugador")
 
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
# BLOQUE 6 — EDA FILOSÓFICO POR PERFIL (v5)
# ══════════════════════════════════════════════════════
# Genera 4 reportes HTML orientados al modelo cruyffista:
#   ⚽ eda_v4_delanteros.html      → 9 falso: presión, movilidad, xG sin penal
#   🎯 eda_v4_mediocampistas.html  → entre líneas: progresión, presión, bajo error
#   🛡️ eda_v4_defensores.html      → líbero moderno: zonas altas, salida limpia
#   🔁 eda_v4_laterales.html       → lateral invertido: duelos + conducción al centro
#
# Cada reporte incluye:
#   · Sección 1 — Universo del perfil (jugadores únicos, distribución)
#   · Sección 2 — Distribuciones de métricas filosóficas (histogramas + KDE)
#   · Sección 3 — Detección de outliers IQR sobre métricas del relato
#   · Sección 4 — Boxplots con Q1/Med/Q3 anotados
#   · Sección 5 — Valoraciones: scatter rendimiento vs valor de mercado
#   · Sección 6 — Hallazgos e implicaciones para DAX
# ══════════════════════════════════════════════════════
 
print("\n── BLOQUE 6: EDA Filosófico por Perfil ──────────────")
 
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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
    "lateral":       {"primario": "#7B2D8B", "secundario": "#CE93D8",
                      "fondo": "#F9F0FF",    "acento":     "#4A148C"},
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
    if len(datos) < 5:
        return ""
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
               linewidth=1.5, alpha=0.8, label=f"Media: {datos.mean():.2f}")
    ax.axvline(datos.median(), color="#888888", linestyle=":",
               linewidth=1.5, alpha=0.8, label=f"Mediana: {datos.median():.2f}")
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
    cols_ok = [c for c in cols if c in df.columns and df[c].dropna().shape[0] > 5]
    if not cols_ok:
        return ""
    titulos_ok = [titulos[cols.index(c)] for c in cols_ok]
    n = len(cols_ok)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 5))
    fig.patch.set_facecolor(fondo)
    if n == 1:
        axes = [axes]
    for ax, col, titulo in zip(axes, cols_ok, titulos_ok):
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
                f"{lbl}\n{val:.2f}", xy=(1, val), xytext=(1.28, val),
                fontsize=8, color="#333333",
                arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.8),
            )
    fig.suptitle("Boxplots — Dispersión y outliers",
                 fontsize=13, fontweight="bold", color="#222222", y=1.02)
    plt.tight_layout()
    return fig_to_b64(fig)
 
def grafico_scatter_valoracion(df_analitico, metrica, label_metrica,
                                color, fondo, titulo):
    """
    Scatter: valor de mercado promedio del período vs métrica principal.
    Cuadrante interesante: bajo costo, alto rendimiento.
    """
    df_plot = df_analitico[
        df_analitico[metrica].notna() &
        df_analitico["valor_mercado_promedio"].notna() &
        (df_analitico["valor_mercado_promedio"] > 0)
    ].copy()
    if len(df_plot) < 10:
        return ""
 
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
 
    # Scatter base
    ax.scatter(df_plot[metrica], df_plot["valor_mercado_promedio"] / 1e6,
               color=color, alpha=0.45, s=35, edgecolors="white", linewidth=0.4)
 
    # Líneas de mediana para definir cuadrantes
    med_x = df_plot[metrica].median()
    med_y = (df_plot["valor_mercado_promedio"] / 1e6).median()
    ax.axvline(med_x, color="#aaaaaa", linestyle="--", linewidth=1, alpha=0.7)
    ax.axhline(med_y, color="#aaaaaa", linestyle="--", linewidth=1, alpha=0.7)
 
    # Etiqueta cuadrante de interés (alto rendimiento, bajo costo)
    ax.text(df_plot[metrica].max() * 0.02,
            (df_plot["valor_mercado_promedio"] / 1e6).max() * 0.95,
            "Alto rendimiento\nAlto costo", fontsize=8,
            color="#888888", alpha=0.7)
    ax.text(df_plot[metrica].max() * 0.02,
            (df_plot["valor_mercado_promedio"] / 1e6).max() * 0.05,
            "⭐ Alto rendimiento\nBajo costo", fontsize=9,
            color=color, fontweight="bold", alpha=0.9)
 
    # Línea de tendencia
    try:
        z = np.polyfit(df_plot[metrica], df_plot["valor_mercado_promedio"] / 1e6, 1)
        p = np.poly1d(z)
        x_line = np.linspace(df_plot[metrica].min(), df_plot[metrica].max(), 100)
        ax.plot(x_line, p(x_line), color=color, linewidth=1.5,
                alpha=0.5, linestyle="-")
    except Exception:
        pass
 
    ax.set_xlabel(label_metrica, fontsize=10, color="#444444")
    ax.set_ylabel("Valor de mercado promedio (M€)", fontsize=10, color="#444444")
    ax.set_title(titulo, fontsize=12, fontweight="bold", pad=10, color="#222222")
    ax.tick_params(colors="#555555")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig_to_b64(fig)
 
def grafico_boxplot_cuartiles(df_analitico, metrica, color, fondo, label_metrica):
    """
    Boxplot de valor de mercado segmentado por cuartil de rendimiento.
    Muestra si las métricas del relato están 'preciadas' en el mercado.
    """
    df_plot = df_analitico[
        df_analitico[metrica].notna() &
        df_analitico["valor_mercado_promedio"].notna() &
        (df_analitico["valor_mercado_promedio"] > 0)
    ].copy()
    if len(df_plot) < 20:
        return ""
 
    df_plot["cuartil"] = pd.qcut(df_plot[metrica], q=4,
                                  labels=["Q1\n(bajo)", "Q2", "Q3", "Q4\n(alto)"])
    grupos = [df_plot[df_plot["cuartil"] == q]["valor_mercado_promedio"].values / 1e6
              for q in ["Q1\n(bajo)", "Q2", "Q3", "Q4\n(alto)"]]
    grupos = [g for g in grupos if len(g) > 0]
 
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
 
    colors_grad = [color + "55", color + "88", color + "BB", color]
    for j, (grupo, col_hex) in enumerate(zip(grupos, colors_grad)):
        bp = ax.boxplot(grupo, positions=[j + 1], patch_artist=True,
                        widths=0.5,
                        medianprops=dict(color="#333333", linewidth=2),
                        whiskerprops=dict(color="#666666", linewidth=1.2),
                        capprops=dict(color="#666666", linewidth=1.2),
                        flierprops=dict(marker="o", markerfacecolor=col_hex,
                                        markersize=3, alpha=0.5, linestyle="none"))
        bp["boxes"][0].set_facecolor(col_hex)
        bp["boxes"][0].set_alpha(0.8)
 
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(["Q1\n(bajo)", "Q2", "Q3", "Q4\n(alto)"],
                       fontsize=9, color="#555555")
    ax.set_xlabel(f"Cuartil de rendimiento — {label_metrica}", fontsize=10, color="#444444")
    ax.set_ylabel("Valor de mercado (M€)", fontsize=10, color="#444444")
    ax.set_title("¿El mercado precia esta métrica?", fontsize=12,
                 fontweight="bold", pad=10, color="#222222")
    ax.tick_params(colors="#555555")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig_to_b64(fig)
 
def grafico_hist_valoracion(serie_valores, color, fondo):
    """Distribución de valor de mercado del universo del perfil."""
    datos = serie_valores.dropna()
    datos = datos[datos > 0] / 1e6
    if len(datos) < 5:
        return ""
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    ax.hist(datos, bins=30, color=color, alpha=0.7,
            edgecolor="white", linewidth=0.5)
    ax.axvline(datos.mean(),   color="#333333", linestyle="--",
               linewidth=1.5, alpha=0.8, label=f"Media: {datos.mean():.1f}M€")
    ax.axvline(datos.median(), color="#888888", linestyle=":",
               linewidth=1.5, alpha=0.8, label=f"Mediana: {datos.median():.1f}M€")
    ax.set_xlabel("Valor de mercado promedio (M€)", fontsize=10, color="#444444")
    ax.set_ylabel("N° jugadores", fontsize=10, color="#444444")
    ax.set_title("Distribución de valor de mercado del perfil",
                 fontsize=12, fontweight="bold", pad=10, color="#222222")
    ax.tick_params(colors="#555555")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9, framealpha=0.7)
    plt.tight_layout()
    return fig_to_b64(fig)
 
# ── Helpers de tablas HTML ────────────────────────────
 
def tabla_stats_html(df, cols, titulos, color):
    filas = ""
    for col, titulo in zip(cols, titulos):
        if col not in df.columns:
            continue
        d    = df[col].dropna()
        if len(d) < 2:
            continue
        skew = d.skew()
        kurt = d.kurtosis()
        lbl  = ("Simétrica" if abs(skew) < 0.5
                else ("Asim. +" if skew > 0 else "Asim. −"))
        filas += f"""
        <tr>
          <td><code>{titulo}</code></td>
          <td>{len(d):,}</td>
          <td>{d.mean():.2f}</td><td>{d.median():.2f}</td>
          <td>{d.std():.2f}</td>
          <td>{d.min():.2f}</td><td>{d.max():.2f}</td>
          <td>{skew:.2f} <em>({lbl})</em></td>
          <td>{kurt:.2f}</td>
        </tr>"""
    return f"""<table class="tbl">
      <thead><tr style="background:{color};color:white">
        <th>Variable</th><th>N</th><th>Media</th><th>Mediana</th>
        <th>Desv.Est.</th><th>Mín.</th><th>Máx.</th>
        <th>Asimetría</th><th>Curtosis</th>
      </tr></thead><tbody>{filas}</tbody></table>"""
 
def tabla_iqr_html(df, cols, titulos, color):
    filas = ""
    for col, titulo in zip(cols, titulos):
        if col not in df.columns:
            continue
        r   = calcular_iqr(df[col])
        sem = ("🔴" if r["pct_outliers"] > 10
               else ("🟡" if r["pct_outliers"] > 5 else "🟢"))
        filas += f"""
        <tr>
          <td><code>{titulo}</code></td>
          <td>{r['Q1']:.2f}</td><td>{r['Q3']:.2f}</td>
          <td>{r['IQR']:.2f}</td>
          <td>{r['lower']:.2f}</td><td>{r['upper']:.2f}</td>
          <td><strong>{r['n_outliers']:,}</strong></td>
          <td>{r['pct_outliers']}% {sem}</td>
        </tr>"""
    return f"""<table class="tbl">
      <thead><tr style="background:{color};color:white">
        <th>Variable</th><th>Q1</th><th>Q3</th><th>IQR</th>
        <th>Límite inf.</th><th>Límite sup.</th>
        <th>N° Outliers</th><th>% Outliers</th>
      </tr></thead><tbody>{filas}</tbody></table>"""
 
def tabla_universo_html(df_analitico, color):
    n_jug  = len(df_analitico)
    n_convm = df_analitico["valor_mercado_promedio"].notna().sum()
    med_val = df_analitico["valor_mercado_promedio"].median()
    equipos = df_analitico["equipo_habitual"].value_counts().head(5)
    rows_eq = "".join(f"<tr><td>{eq}</td><td>{cnt}</td></tr>"
                      for eq, cnt in equipos.items())
    return f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <table class="tbl">
        <thead><tr style="background:{color};color:white">
          <th>Métrica</th><th>Valor</th>
        </tr></thead>
        <tbody>
          <tr><td>Jugadores únicos</td><td><strong>{n_jug:,}</strong></td></tr>
          <tr><td>Con valor de mercado</td><td>{n_convm:,} ({n_convm/n_jug*100:.0f}%)</td></tr>
          <tr><td>Valor mediano del período</td><td>{med_val/1e6:.1f} M€</td></tr>
        </tbody>
      </table>
      <table class="tbl">
        <thead><tr style="background:{color};color:white">
          <th>Equipo</th><th>Jugadores</th>
        </tr></thead>
        <tbody>{rows_eq}</tbody>
      </table>
    </div>"""
 
# ── Generador principal de HTML ───────────────────────
 
def generar_html_perfil(perfil, emoji, subtitulo, filosofia,
                        df_analitico, cols_metricas, titulos_metricas,
                        imgs_hist, img_box, img_hist_val,
                        img_scatter, img_cuartiles,
                        t_stats, t_iqr, t_universo,
                        colores, hallazgos):
    c = colores
    grids = "".join(f"""
      <div class="chart-card">
        <h3 class="chart-title">{tit}</h3>
        <img src="data:image/png;base64,{img}" class="chart-img"/>
      </div>""" for tit, img in zip(titulos_metricas, imgs_hist) if img)
 
    hallazgos_li = "".join(f"<li>{h}</li>" for h in hallazgos)
 
    scatter_block = f"""
      <div class="chart-card" style="grid-column:span 2">
        <h3 class="chart-title">Rendimiento vs Valor de Mercado</h3>
        <img src="data:image/png;base64,{img_scatter}" class="chart-img"/>
      </div>""" if img_scatter else ""
 
    cuartiles_block = f"""
      <div class="chart-card">
        <h3 class="chart-title">¿El mercado precia esta métrica?</h3>
        <img src="data:image/png;base64,{img_cuartiles}" class="chart-img"/>
      </div>""" if img_cuartiles else ""
 
    hist_val_block = f"""
      <div class="chart-card">
        <h3 class="chart-title">Distribución de valor de mercado</h3>
        <img src="data:image/png;base64,{img_hist_val}" class="chart-img"/>
      </div>""" if img_hist_val else ""
 
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>EDA v4 — {perfil.title()}</title>
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
  .header p.sub{{font-size:1.05rem;opacity:.88;margin-top:6px}}
  .filosofia{{background:rgba(255,255,255,.15);border-left:3px solid rgba(255,255,255,.6);
    padding:12px 16px;margin-top:16px;border-radius:0 8px 8px 0;
    font-size:.9rem;font-style:italic;opacity:.92;line-height:1.6}}
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
  <h1>EDA v4 — {perfil.title()}</h1>
  <p class="sub">{subtitulo}</p>
  <div class="filosofia">{filosofia}</div>
  <div class="badges">
    <span class="badge">📊 {len(df_analitico):,} jugadores analizados</span>
    <span class="badge">📐 {len(cols_metricas)} métricas filosóficas</span>
    <span class="badge">⚽ La Liga 2014–2017</span>
    <span class="badge">💶 Valoraciones Transfermarkt</span>
  </div>
</div>
<div class="container">
 
  <div class="section">
    <div class="sec-header"><div class="sec-num">1</div>
      <div><div class="sec-title">Universo del Perfil</div>
        <div class="sec-sub">Jugadores únicos, cobertura de valoraciones y distribución por equipo</div></div></div>
    <div class="card">{t_universo}</div>
  </div>
 
  <div class="section">
    <div class="sec-header"><div class="sec-num">2</div>
      <div><div class="sec-title">Distribuciones — Métricas Filosóficas</div>
        <div class="sec-sub">Variables directamente alineadas con el modelo de juego cruyffista</div></div></div>
    <div class="charts-grid">{grids}</div>
  </div>
 
  <div class="section">
    <div class="sec-header"><div class="sec-num">3</div>
      <div><div class="sec-title">Detección de Outliers — Método IQR</div>
        <div class="sec-sub">Los outliers de rendimiento son los candidatos de élite del universo</div></div></div>
    <div class="card" style="overflow-x:auto">{t_iqr}
      <div class="leyenda">
        <span>🟢 &lt; 5% outliers → métrica bien distribuida</span>
        <span>🟡 5–10% → algunos jugadores muy por encima del promedio</span>
        <span>🔴 &gt; 10% → métrica muy concentrada en pocos jugadores</span>
      </div></div>
  </div>
 
  <div class="section">
    <div class="sec-header"><div class="sec-num">4</div>
      <div><div class="sec-title">Boxplots — Dispersión por Métrica</div>
        <div class="sec-sub">Caja = IQR · Bigotes = 1.5×IQR · Puntos = jugadores outliers</div></div></div>
    <div class="card">
      <img src="data:image/png;base64,{img_box}" style="width:100%;border-radius:6px"/></div>
  </div>
 
  <div class="section">
    <div class="sec-header"><div class="sec-num">5</div>
      <div><div class="sec-title">Análisis de Valoraciones</div>
        <div class="sec-sub">¿El mercado precia lo que necesitamos? Oportunidades de valor oculto</div></div></div>
    <div class="charts-grid">
      {hist_val_block}
      {cuartiles_block}
      {scatter_block}
    </div>
  </div>
 
  <div class="section">
    <div class="sec-header"><div class="sec-num">6</div>
      <div><div class="sec-title">Hallazgos e Implicaciones para DAX</div>
        <div class="sec-sub">Umbrales sugeridos y recomendaciones para Power BI</div></div></div>
    <div class="hallazgos"><h3>Principales observaciones:</h3>
      <ul>{hallazgos_li}</ul></div>
  </div>
 
</div>
<div class="footer">EDA Filosófico v4 · Scouting La Liga 2014–2017 · ICARO Data Analytics · 2026</div>
</body></html>"""
 
 
# ── Función auxiliar: valor de mercado promedio por jugador ──
def valor_mercado_promedio(player_ids):
    """
    Calcula el valor de mercado promedio durante el período
    para cada player_id usando dim_valoracion.
    Más representativo que el último valor registrado.
    """
    return (
        dim_valoracion[dim_valoracion["player_id"].isin(player_ids)]
        .groupby("player_id")["market_value_in_eur"]
        .mean()
        .reset_index()
        .rename(columns={"market_value_in_eur": "valor_mercado_promedio"})
    )
 
# ── Carga base de dimensiones slim ────────────────────
dim_jugador_slim = dim_jugador[["player_id", "posicion_habitual",
                                 "equipo_habitual", "market_value_in_eur"]].copy()
 
 
# ══════════════════════════════════════════════════════
# PERFIL 1: DELANTERO — "9 FALSO CRUYFFISTA"
# ══════════════════════════════════════════════════════
# Métricas: xG sin penal, presiones en último tercio (x>70),
#           duelos ganados en campo rival, recepciones en campo rival
 
print("\n   ⚽ Generando eda_v4_delanteros.html ...")
 
POSICIONES_DEL = {
    "Center Forward", "Left Wing", "Right Wing",
    "Left Center Forward", "Right Center Forward",
    "Secondary Striker"
}
 
# Cargar y convertir facts necesarios
df_shot_d = pd.read_csv(OUTPUT_DIR / "fact_shot.csv", sep=";", decimal=",",
                         low_memory=False, on_bad_lines="skip")
df_shot_d = to_num(df_shot_d, ["shot_statsbomb_xg", "location_x", "es_gol",
                                 "es_al_arco"])
 
df_pres_d = pd.read_csv(OUTPUT_DIR / "fact_pressure.csv", sep=";", decimal=",",
                          low_memory=False, on_bad_lines="skip")
df_pres_d = to_num(df_pres_d, ["location_x"])
 
df_duel_d = pd.read_csv(OUTPUT_DIR / "fact_duel.csv", sep=";", decimal=",",
                          low_memory=False, on_bad_lines="skip")
df_duel_d = to_num(df_duel_d, ["location_x", "es_duelo_ganado"])
 
df_recv_d = pd.read_csv(OUTPUT_DIR / "fact_ball_receipt.csv", sep=";", decimal=",",
                          low_memory=False, on_bad_lines="skip")
df_recv_d = to_num(df_recv_d, ["location_x", "es_recepcion_exitosa"])
 
# Filtrar por posición de delantero
players_del = dim_jugador_slim[
    dim_jugador_slim["posicion_habitual"].isin(POSICIONES_DEL)
]["player_id"].unique()
 
# Construir df analítico por jugador
xg_sp = (df_shot_d[
    df_shot_d["player_id"].isin(players_del) &
    (df_shot_d.get("shot_type", pd.Series(dtype=str)) != "Penalty")
].groupby("player_id")["shot_statsbomb_xg"].sum()
.reset_index().rename(columns={"shot_statsbomb_xg": "xg_sin_penal"}))
 
presiones = (df_pres_d[
    df_pres_d["player_id"].isin(players_del) &
    (df_pres_d["location_x"] > 70)          # umbral acordado
].groupby("player_id").size()
.reset_index().rename(columns={0: "presiones_ultimo_tercio"}))
 
duelos_cr = (df_duel_d[
    df_duel_d["player_id"].isin(players_del) &
    (df_duel_d["location_x"] > 60) &
    (df_duel_d["es_duelo_ganado"] == 1)
].groupby("player_id").size()
.reset_index().rename(columns={0: "duelos_campo_rival"}))
 
recepciones = (df_recv_d[
    df_recv_d["player_id"].isin(players_del) &
    (df_recv_d["location_x"] > 60)
].groupby("player_id").size()
.reset_index().rename(columns={0: "recepciones_campo_rival"}))
 
df_del = (dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_del)]
          .merge(xg_sp,       on="player_id", how="left")
          .merge(presiones,   on="player_id", how="left")
          .merge(duelos_cr,   on="player_id", how="left")
          .merge(recepciones, on="player_id", how="left")
          .merge(valor_mercado_promedio(players_del), on="player_id", how="left")
          .fillna(0))
 
COLS_DEL  = ["xg_sin_penal", "presiones_ultimo_tercio",
             "duelos_campo_rival", "recepciones_campo_rival"]
TITS_DEL  = ["xG sin penal", "Presiones último tercio (x>70)",
             "Duelos ganados campo rival", "Recepciones campo rival"]
c = COLORES["delantero"]
 
imgs_hist_del = [grafico_histograma(df_del, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_DEL, TITS_DEL)]
img_box_del   = grafico_boxplot_multiple(df_del, COLS_DEL, TITS_DEL,
                                          c["primario"], c["fondo"])
img_hist_val_del  = grafico_hist_valoracion(df_del["valor_mercado_promedio"],
                                             c["primario"], c["fondo"])
img_scatter_del   = grafico_scatter_valoracion(df_del, "xg_sin_penal",
                                                "xG sin penal (total período)",
                                                c["primario"], c["fondo"],
                                                "xG sin penal vs Valor de mercado")
img_cuartiles_del = grafico_boxplot_cuartiles(df_del, "xg_sin_penal",
                                               c["primario"], c["fondo"],
                                               "xG sin penal")
 
# Hallazgos
xg_med   = df_del["xg_sin_penal"].median()
xg_p75   = df_del["xg_sin_penal"].quantile(0.75)
pres_med = df_del["presiones_ultimo_tercio"].median()
recv_med = df_del["recepciones_campo_rival"].median()
n_val    = df_del["valor_mercado_promedio"].gt(0).sum()
val_med  = df_del[df_del["valor_mercado_promedio"] > 0]["valor_mercado_promedio"].median()
 
hallazgos_del = [
    f"El universo de delanteros cruyffistas tiene {len(df_del)} jugadores únicos en el período. La mediana de xG sin penal es {xg_med:.1f} — el umbral de corte sugerido para candidatos es >{xg_p75:.1f} (percentil 75).",
    f"Las presiones en el último tercio (location_x > 70) tienen mediana {pres_med:.0f} por jugador. Un delantero con >P75 en esta métrica es un candidato ideal para el modelo de presión alta.",
    f"Las recepciones en campo rival (mediana {recv_med:.0f}) miden el 'movimiento sin balón' del delantero. Alta correlación con la participación asociativa en campo rival que busca el relato.",
    f"Solo {n_val} de {len(df_del)} delanteros tienen valoración Transfermarkt disponible. La mediana de valor es {val_med/1e6:.1f}M€ — el club puede buscar jugadores con xG alto por debajo de este umbral.",
    f"Para DAX: crear medida 'Score Delantero' = xG_sin_penal * 0.4 + presiones_ultimo_tercio * 0.3 + recepciones_campo_rival * 0.3, normalizado por percentil del universo.",
    f"El scatter rendimiento vs valor de mercado identifica el cuadrante de 'valor oculto': jugadores con xG sin penal superior a la mediana pero valor de mercado inferior a la mediana del perfil.",
]
 
html_del = generar_html_perfil(
    "Delanteros", "⚽",
    "9 falso cruyffista · fact_shot + fact_pressure + fact_duel + fact_ball_receipt",
    "Movilidad, presión alta e inteligencia sin balón. No buscamos un 9 estático: buscamos un atacante que inicie la presión, se asocie de espaldas y genere peligro sin depender del área.",
    df_del, COLS_DEL, TITS_DEL,
    imgs_hist_del, img_box_del, img_hist_val_del,
    img_scatter_del, img_cuartiles_del,
    tabla_stats_html(df_del, COLS_DEL, TITS_DEL, c["primario"]),
    tabla_iqr_html(df_del, COLS_DEL, TITS_DEL, c["primario"]),
    tabla_universo_html(df_del, c["primario"]),
    c, hallazgos_del
)
(OUTPUT_DIR / "eda_v4_delanteros.html").write_text(html_del, encoding="utf-8")
print(f"   ✔ eda_v4_delanteros.html — {len(df_del):,} jugadores")
 
 
# ══════════════════════════════════════════════════════
# PERFIL 2: MEDIOCAMPISTA — "ENTRE LÍNEAS"
# ══════════════════════════════════════════════════════
# Métricas: pases progresivos (pass_end_x > location_x + 8),
#           conducciones progresivas, acciones bajo presión exitosas,
#           tasa de pérdida de balón
 
print("\n   🎯 Generando eda_v4_mediocampistas.html ...")
 
POSICIONES_MID = {
    "Center Defensive Midfield", "Center Midfield",
    "Left Center Midfield", "Right Center Midfield",
    "Left Midfield", "Right Midfield",
    "Left Defensive Midfield", "Right Defensive Midfield",
    "Center Attacking Midfield",
}
 
players_mid = dim_jugador_slim[
    dim_jugador_slim["posicion_habitual"].isin(POSICIONES_MID)
]["player_id"].unique()
 
df_pass_m = pd.read_csv(OUTPUT_DIR / "fact_pass.csv", sep=";", decimal=",",
                          low_memory=False, on_bad_lines="skip")
df_pass_m = to_num(df_pass_m, ["location_x", "pass_end_x", "es_pase_completo",
                                 "es_asistencia_gol", "es_asistencia_tiro",
                                 "under_pressure"])
 
df_carry_m = pd.read_csv(OUTPUT_DIR / "fact_carry.csv", sep=";", decimal=",",
                           low_memory=False, on_bad_lines="skip")
df_carry_m = to_num(df_carry_m, ["location_x", "carry_end_x", "carry_distancia"])
 
df_misc_m = pd.read_csv(OUTPUT_DIR / "fact_miscontrol.csv", sep=";", decimal=",",
                          low_memory=False, on_bad_lines="skip")
 
# Pases progresivos: pass_end_x > location_x + 8
pases_prog = (df_pass_m[
    df_pass_m["player_id"].isin(players_mid) &
    (df_pass_m["pass_end_x"] > df_pass_m["location_x"] + 8)
].groupby("player_id").size()
.reset_index().rename(columns={0: "pases_progresivos"}))
 
# Total pases para calcular ratio
total_pases = (df_pass_m[df_pass_m["player_id"].isin(players_mid)]
               .groupby("player_id").size()
               .reset_index().rename(columns={0: "total_pases"}))
 
# Conducciones progresivas: carry_end_x > location_x + 5
cond_prog = (df_carry_m[
    df_carry_m["player_id"].isin(players_mid) &
    (df_carry_m["carry_end_x"] > df_carry_m["location_x"] + 5)
].groupby("player_id").size()
.reset_index().rename(columns={0: "conducciones_progresivas"}))
 
# Acciones bajo presión exitosas
acc_presion = (df_pass_m[
    df_pass_m["player_id"].isin(players_mid) &
    (df_pass_m["under_pressure"] == 1) &
    (df_pass_m["es_pase_completo"] == 1)
].groupby("player_id").size()
.reset_index().rename(columns={0: "pases_exitosos_bajo_presion"}))
 
# Pérdidas de balón
perdidas = (df_misc_m[df_misc_m["player_id"].isin(players_mid)]
            .groupby("player_id").size()
            .reset_index().rename(columns={0: "perdidas_balon"}))
 
df_mid = (dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_mid)]
          .merge(pases_prog,   on="player_id", how="left")
          .merge(total_pases,  on="player_id", how="left")
          .merge(cond_prog,    on="player_id", how="left")
          .merge(acc_presion,  on="player_id", how="left")
          .merge(perdidas,     on="player_id", how="left")
          .merge(valor_mercado_promedio(players_mid), on="player_id", how="left")
          .fillna(0))
 
# Ratio pases progresivos
df_mid["ratio_pases_prog"] = np.where(
    df_mid["total_pases"] > 0,
    df_mid["pases_progresivos"] / df_mid["total_pases"],
    0
)
 
COLS_MID  = ["pases_progresivos", "ratio_pases_prog",
             "conducciones_progresivas", "pases_exitosos_bajo_presion",
             "perdidas_balon"]
TITS_MID  = ["Pases progresivos (end_x > x+8)", "Ratio pases progresivos",
             "Conducciones progresivas (end_x > x+5)",
             "Pases exitosos bajo presión", "Pérdidas de balón"]
c = COLORES["mediocampista"]
 
imgs_hist_mid = [grafico_histograma(df_mid, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_MID, TITS_MID)]
img_box_mid   = grafico_boxplot_multiple(df_mid, COLS_MID, TITS_MID,
                                          c["primario"], c["fondo"])
img_hist_val_mid  = grafico_hist_valoracion(df_mid["valor_mercado_promedio"],
                                             c["primario"], c["fondo"])
img_scatter_mid   = grafico_scatter_valoracion(df_mid, "pases_progresivos",
                                                "Pases progresivos (total período)",
                                                c["primario"], c["fondo"],
                                                "Pases progresivos vs Valor de mercado")
img_cuartiles_mid = grafico_boxplot_cuartiles(df_mid, "pases_progresivos",
                                               c["primario"], c["fondo"],
                                               "Pases progresivos")
 
pp_med   = df_mid["pases_progresivos"].median()
pp_p75   = df_mid["pases_progresivos"].quantile(0.75)
rat_med  = df_mid["ratio_pases_prog"].median()
pres_med = df_mid["pases_exitosos_bajo_presion"].median()
val_med  = df_mid[df_mid["valor_mercado_promedio"] > 0]["valor_mercado_promedio"].median() if df_mid["valor_mercado_promedio"].gt(0).any() else 0
 
hallazgos_mid = [
    f"El universo de mediocampistas tiene {len(df_mid)} jugadores. La mediana de pases progresivos es {pp_med:.0f} — el umbral sugerido para candidatos es >{pp_p75:.0f} (percentil 75).",
    f"El ratio de pases progresivos (mediana {rat_med:.2f}) mide la 'intención' de juego hacia adelante: un jugador con ratio > 0.35 prioriza la progresión sobre la circulación lateral.",
    f"Las conducciones progresivas complementan los pases: distinguen mediocampistas que progresan con el balón además de pasarlo, clave para el modelo entre líneas.",
    f"Los pases exitosos bajo presión (mediana {pres_med:.0f}) es la métrica más selectiva del perfil: mide exactamente la resistencia técnica bajo presión que pide el relato.",
    f"La mediana de valor de mercado del perfil es {val_med/1e6:.1f}M€. Un mediocampista con pases_progresivos en el P75 y valor de mercado por debajo de la mediana es la definición de 'ventaja competitiva'.",
    f"Para DAX: ratio_pases_prog como métrica principal de scouting. Filtrar jugadores con >300 pases totales para evitar muestras pequeñas que inflen el ratio.",
]
 
html_mid = generar_html_perfil(
    "Mediocampistas", "🎯",
    "Entre líneas · fact_pass + fact_carry + fact_miscontrol",
    "Resistencia técnica, visión de juego y valentía para recibir entre líneas. No queremos corredores: queremos pensadores que aceleren el juego hacia adelante bajo cualquier circunstancia.",
    df_mid, COLS_MID, TITS_MID,
    imgs_hist_mid, img_box_mid, img_hist_val_mid,
    img_scatter_mid, img_cuartiles_mid,
    tabla_stats_html(df_mid, COLS_MID, TITS_MID, c["primario"]),
    tabla_iqr_html(df_mid, COLS_MID, TITS_MID, c["primario"]),
    tabla_universo_html(df_mid, c["primario"]),
    c, hallazgos_mid
)
(OUTPUT_DIR / "eda_v4_mediocampistas.html").write_text(html_mid, encoding="utf-8")
print(f"   ✔ eda_v4_mediocampistas.html — {len(df_mid):,} jugadores")
 
 
# ══════════════════════════════════════════════════════
# PERFIL 3: DEFENSOR CENTRAL — "LÍBERO MODERNO"
# ══════════════════════════════════════════════════════
# Métricas: duelos ganados en zonas altas (x>40),
#           intercepciones en campo rival (x>60),
#           pases progresivos desde atrás (x<40, end_x > x+15),
#           despejes aéreos
 
print("\n   🛡️ Generando eda_v4_defensores.html ...")
 
POSICIONES_DEF = {
    "Center Back", "Left Center Back", "Right Center Back"
}
 
players_def = dim_jugador_slim[
    dim_jugador_slim["posicion_habitual"].isin(POSICIONES_DEF)
]["player_id"].unique()
 
df_duel_def = pd.read_csv(OUTPUT_DIR / "fact_duel.csv", sep=";", decimal=",",
                            low_memory=False, on_bad_lines="skip")
df_duel_def = to_num(df_duel_def, ["location_x", "es_duelo_ganado"])
 
df_int_def = pd.read_csv(OUTPUT_DIR / "fact_interception.csv", sep=";", decimal=",",
                           low_memory=False, on_bad_lines="skip")
df_int_def = to_num(df_int_def, ["location_x", "es_intercepcion_exitosa"])
 
df_pass_def = pd.read_csv(OUTPUT_DIR / "fact_pass.csv", sep=";", decimal=",",
                            low_memory=False, on_bad_lines="skip",
                            usecols=["player_id","location_x","pass_end_x",
                                     "es_pase_completo"])
df_pass_def = to_num(df_pass_def, ["location_x", "pass_end_x", "es_pase_completo"])
 
df_clear_def = pd.read_csv(OUTPUT_DIR / "fact_clearance.csv", sep=";", decimal=",",
                             low_memory=False, on_bad_lines="skip")
df_clear_def = to_num(df_clear_def, ["clearance_aerial_won"])
 
duelos_zona = (df_duel_def[
    df_duel_def["player_id"].isin(players_def) &
    (df_duel_def["location_x"] > 40) &
    (df_duel_def["es_duelo_ganado"] == 1)
].groupby("player_id").size()
.reset_index().rename(columns={0: "duelos_zona_alta"}))
 
intercep_cr = (df_int_def[
    df_int_def["player_id"].isin(players_def) &
    (df_int_def["location_x"] > 60)
].groupby("player_id").size()
.reset_index().rename(columns={0: "intercepciones_campo_rival"}))
 
pases_prog_def = (df_pass_def[
    df_pass_def["player_id"].isin(players_def) &
    (df_pass_def["location_x"] < 40) &
    (df_pass_def["pass_end_x"] > df_pass_def["location_x"] + 15)
].groupby("player_id").size()
.reset_index().rename(columns={0: "pases_prog_desde_atras"}))
 
despejes_aereos = (df_clear_def[
    df_clear_def["player_id"].isin(players_def) &
    (df_clear_def["clearance_aerial_won"] == 1)
].groupby("player_id").size()
.reset_index().rename(columns={0: "despejes_aereos"}))
 
df_def = (dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_def)]
          .merge(duelos_zona,     on="player_id", how="left")
          .merge(intercep_cr,     on="player_id", how="left")
          .merge(pases_prog_def,  on="player_id", how="left")
          .merge(despejes_aereos, on="player_id", how="left")
          .merge(valor_mercado_promedio(players_def), on="player_id", how="left")
          .fillna(0))
 
COLS_DEF  = ["duelos_zona_alta", "intercepciones_campo_rival",
             "pases_prog_desde_atras", "despejes_aereos"]
TITS_DEF  = ["Duelos ganados zona alta (x>40)",
             "Intercepciones campo rival (x>60)",
             "Pases progresivos desde atrás (x<40)",
             "Despejes aéreos"]
c = COLORES["defensor"]
 
imgs_hist_def = [grafico_histograma(df_def, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_DEF, TITS_DEF)]
img_box_def   = grafico_boxplot_multiple(df_def, COLS_DEF, TITS_DEF,
                                          c["primario"], c["fondo"])
img_hist_val_def  = grafico_hist_valoracion(df_def["valor_mercado_promedio"],
                                             c["primario"], c["fondo"])
img_scatter_def   = grafico_scatter_valoracion(df_def, "duelos_zona_alta",
                                                "Duelos ganados zona alta",
                                                c["primario"], c["fondo"],
                                                "Duelos zona alta vs Valor de mercado")
img_cuartiles_def = grafico_boxplot_cuartiles(df_def, "duelos_zona_alta",
                                               c["primario"], c["fondo"],
                                               "Duelos zona alta")
 
dz_med  = df_def["duelos_zona_alta"].median()
dz_p75  = df_def["duelos_zona_alta"].quantile(0.75)
ic_med  = df_def["intercepciones_campo_rival"].median()
pp_med  = df_def["pases_prog_desde_atras"].median()
val_med = df_def[df_def["valor_mercado_promedio"] > 0]["valor_mercado_promedio"].median() if df_def["valor_mercado_promedio"].gt(0).any() else 0
 
hallazgos_def = [
    f"El universo de defensores centrales tiene {len(df_def)} jugadores. Los duelos ganados en zona alta (mediana {dz_med:.0f}) son la métrica más discriminante: el umbral sugerido para candidatos es >{dz_p75:.0f}.",
    f"Las intercepciones en campo rival (mediana {ic_med:.0f}) identifican defensores que defienden lejos del arco, exactamente el perfil que necesita el sistema de presión alta del relato.",
    f"Los pases progresivos desde atrás (location_x < 40, mediana {pp_med:.0f}) miden la calidad de salida: son defensores que inician el juego limpio desde atrás, no solo que despejan.",
    f"Los despejes aéreos son complementarios: un defensor con alta progresión de balón pero también buena cobertura aérea es el perfil completo del líbero moderno.",
    f"La mediana de valor de mercado es {val_med/1e6:.1f}M€. El scatter puede revelar defensores con alto puntaje en duelos_zona_alta pero valor de mercado deprimido — oportunidades de mercado real.",
    f"Para DAX: Score Defensor = duelos_zona_alta * 0.35 + intercepciones_campo_rival * 0.30 + pases_prog_desde_atras * 0.35. Filtrar jugadores con >20 partidos para robustez estadística.",
]
 
html_def = generar_html_perfil(
    "Defensores", "🛡️",
    "Líbero moderno · fact_duel + fact_interception + fact_pass + fact_clearance",
    "Velocidad para corregir a campo abierto y calidad técnica para iniciar el juego limpio desde atrás. No hay lugar para zagueros que solo despejan: necesitamos defensores que construyen.",
    df_def, COLS_DEF, TITS_DEF,
    imgs_hist_def, img_box_def, img_hist_val_def,
    img_scatter_def, img_cuartiles_def,
    tabla_stats_html(df_def, COLS_DEF, TITS_DEF, c["primario"]),
    tabla_iqr_html(df_def, COLS_DEF, TITS_DEF, c["primario"]),
    tabla_universo_html(df_def, c["primario"]),
    c, hallazgos_def
)
(OUTPUT_DIR / "eda_v4_defensores.html").write_text(html_def, encoding="utf-8")
print(f"   ✔ eda_v4_defensores.html — {len(df_def):,} jugadores")
 
 
# ══════════════════════════════════════════════════════
# PERFIL 4: LATERAL INVERTIDO — "VERSATILIDAD MODERNA"
# ══════════════════════════════════════════════════════
# Posiciones: laterales + mediocampistas con perfil lateral
# Métricas: duelos defensivos ganados, conducciones hacia el centro,
#           pases hacia adentro, presiones en banda
 
print("\n   🔁 Generando eda_v4_laterales.html ...")
 
POSICIONES_LAT = {
    # Laterales puros
    "Left Back", "Right Back", "Left Wing Back", "Right Wing Back",
    # Mediocampistas con perfil lateral (incluidos por pedido)
    "Left Midfield", "Right Midfield",
    "Left Defensive Midfield", "Right Defensive Midfield",
}
 
players_lat = dim_jugador_slim[
    dim_jugador_slim["posicion_habitual"].isin(POSICIONES_LAT)
]["player_id"].unique()
 
df_duel_lat = pd.read_csv(OUTPUT_DIR / "fact_duel.csv", sep=";", decimal=",",
                            low_memory=False, on_bad_lines="skip")
df_duel_lat = to_num(df_duel_lat, ["location_x", "location_y", "es_duelo_ganado"])
 
df_carry_lat = pd.read_csv(OUTPUT_DIR / "fact_carry.csv", sep=";", decimal=",",
                             low_memory=False, on_bad_lines="skip")
df_carry_lat = to_num(df_carry_lat, ["location_x", "location_y",
                                      "carry_end_x", "carry_end_y"])
 
df_pass_lat = pd.read_csv(OUTPUT_DIR / "fact_pass.csv", sep=";", decimal=",",
                            low_memory=False, on_bad_lines="skip",
                            usecols=["player_id","location_x","location_y",
                                     "pass_end_x","pass_end_y","es_pase_completo"])
df_pass_lat = to_num(df_pass_lat, ["location_x", "location_y",
                                    "pass_end_x", "pass_end_y", "es_pase_completo"])
 
df_pres_lat = pd.read_csv(OUTPUT_DIR / "fact_pressure.csv", sep=";", decimal=",",
                            low_memory=False, on_bad_lines="skip")
df_pres_lat = to_num(df_pres_lat, ["location_x", "location_y"])
 
# Duelos defensivos ganados (todas las zonas)
duelos_def = (df_duel_lat[
    df_duel_lat["player_id"].isin(players_lat) &
    (df_duel_lat["es_duelo_ganado"] == 1)
].groupby("player_id").size()
.reset_index().rename(columns={0: "duelos_defensivos_ganados"}))
 
# Conducciones hacia el centro:
# lateral izquierdo: carry_end_y > location_y (se mueve a la derecha = al centro)
# lateral derecho:   carry_end_y < location_y (se mueve a la izquierda = al centro)
# Aproximación: location_y < 30 (banda izq) → end_y > location_y
#               location_y > 50 (banda der) → end_y < location_y
cond_centro = (df_carry_lat[
    df_carry_lat["player_id"].isin(players_lat) &
    (
        ((df_carry_lat["location_y"] < 30) & (df_carry_lat["carry_end_y"] > df_carry_lat["location_y"])) |
        ((df_carry_lat["location_y"] > 50) & (df_carry_lat["carry_end_y"] < df_carry_lat["location_y"]))
    )
].groupby("player_id").size()
.reset_index().rename(columns={0: "conducciones_hacia_centro"}))
 
# Pases hacia adentro desde banda
pases_adentro = (df_pass_lat[
    df_pass_lat["player_id"].isin(players_lat) &
    (
        ((df_pass_lat["location_y"] < 25) & (df_pass_lat["pass_end_y"] > df_pass_lat["location_y"] + 5)) |
        ((df_pass_lat["location_y"] > 55) & (df_pass_lat["pass_end_y"] < df_pass_lat["location_y"] - 5))
    )
].groupby("player_id").size()
.reset_index().rename(columns={0: "pases_hacia_adentro"}))
 
# Presiones en banda (franjas laterales)
presiones_banda = (df_pres_lat[
    df_pres_lat["player_id"].isin(players_lat) &
    ((df_pres_lat["location_y"] < 20) | (df_pres_lat["location_y"] > 60))
].groupby("player_id").size()
.reset_index().rename(columns={0: "presiones_en_banda"}))
 
df_lat = (dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_lat)]
          .merge(duelos_def,      on="player_id", how="left")
          .merge(cond_centro,     on="player_id", how="left")
          .merge(pases_adentro,   on="player_id", how="left")
          .merge(presiones_banda, on="player_id", how="left")
          .merge(valor_mercado_promedio(players_lat), on="player_id", how="left")
          .fillna(0))
 
COLS_LAT  = ["duelos_defensivos_ganados", "conducciones_hacia_centro",
             "pases_hacia_adentro", "presiones_en_banda"]
TITS_LAT  = ["Duelos defensivos ganados",
             "Conducciones hacia el centro",
             "Pases hacia adentro desde banda",
             "Presiones en banda"]
c = COLORES["lateral"]
 
imgs_hist_lat = [grafico_histograma(df_lat, col, c["primario"], tit, c["fondo"])
                 for col, tit in zip(COLS_LAT, TITS_LAT)]
img_box_lat   = grafico_boxplot_multiple(df_lat, COLS_LAT, TITS_LAT,
                                          c["primario"], c["fondo"])
img_hist_val_lat  = grafico_hist_valoracion(df_lat["valor_mercado_promedio"],
                                             c["primario"], c["fondo"])
img_scatter_lat   = grafico_scatter_valoracion(df_lat, "conducciones_hacia_centro",
                                                "Conducciones hacia el centro",
                                                c["primario"], c["fondo"],
                                                "Conducciones al centro vs Valor de mercado")
img_cuartiles_lat = grafico_boxplot_cuartiles(df_lat, "conducciones_hacia_centro",
                                               c["primario"], c["fondo"],
                                               "Conducciones al centro")
 
dd_med  = df_lat["duelos_defensivos_ganados"].median()
dd_p75  = df_lat["duelos_defensivos_ganados"].quantile(0.75)
cc_med  = df_lat["conducciones_hacia_centro"].median()
pa_med  = df_lat["pases_hacia_adentro"].median()
val_med = df_lat[df_lat["valor_mercado_promedio"] > 0]["valor_mercado_promedio"].median() if df_lat["valor_mercado_promedio"].gt(0).any() else 0
 
hallazgos_lat = [
    f"El universo de laterales/mediocampistas con perfil lateral tiene {len(df_lat)} jugadores. Mediana de duelos defensivos ganados: {dd_med:.0f} — umbral sugerido para candidatos: >{dd_p75:.0f}.",
    f"Las conducciones hacia el centro (mediana {cc_med:.0f}) son la métrica más diferencial del lateral invertido respecto al lateral clásico: miden cuánto abandona la banda para generar superioridades interiores.",
    f"Los pases hacia adentro desde banda (mediana {pa_med:.0f}) complementan las conducciones: algunos laterales invierten por pase en lugar de por conducción — ambos perfiles sirven al modelo.",
    f"Las presiones en banda miden el trabajo defensivo sin balón: un lateral con alta presión en banda + conducciones hacia el centro tiene exactamente el perfil dual que pide el relato.",
    f"La mediana de valor de mercado es {val_med/1e6:.1f}M€. Este perfil suele estar sub-valorado en el mercado porque las métricas de lateral invertido no aparecen en estadísticas tradicionales.",
    f"Para DAX: Score Lateral = duelos_defensivos_ganados * 0.30 + conducciones_hacia_centro * 0.35 + pases_hacia_adentro * 0.35. Filtrar por >15 partidos y verificar posicion_habitual en dim_jugador.",
]
 
html_lat = generar_html_perfil(
    "Laterales", "🔁",
    "Lateral invertido · fact_duel + fact_carry + fact_pass + fact_pressure",
    "Firme en el uno contra uno pero inteligente para cerrarse al medio. No queremos centradores: queremos jugadores con lectura táctica que generen superioridades desde la banda hacia adentro.",
    df_lat, COLS_LAT, TITS_LAT,
    imgs_hist_lat, img_box_lat, img_hist_val_lat,
    img_scatter_lat, img_cuartiles_lat,
    tabla_stats_html(df_lat, COLS_LAT, TITS_LAT, c["primario"]),
    tabla_iqr_html(df_lat, COLS_LAT, TITS_LAT, c["primario"]),
    tabla_universo_html(df_lat, c["primario"]),
    c, hallazgos_lat
)
(OUTPUT_DIR / "eda_v4_laterales.html").write_text(html_lat, encoding="utf-8")
print(f"   ✔ eda_v4_laterales.html — {len(df_lat):,} jugadores")
 
 
# ══════════════════════════════════════════════════════
# RESUMEN FINAL
# ══════════════════════════════════════════════════════
 
print("\n" + "=" * 60)
print("  ✅ PIPELINE V4 COMPLETADO")
print("=" * 60)
 
csvs     = list(OUTPUT_DIR.glob("*.csv"))
htmls    = list(OUTPUT_DIR.glob("*.html"))
total_mb = sum(f.stat().st_size for f in csvs + htmls) / 1024 / 1024
 
print(f"\n  {len(csvs)} archivos CSV en ./{OUTPUT_DIR}/")
print(f"  {len(htmls)} reportes EDA HTML en ./{OUTPUT_DIR}/")
print(f"  Tamaño total: {total_mb:.1f} MB")
 
print("""
  FIXES APLICADOS EN V4:
  ✔ [FIX 1] dim_jugador sin duplicados de player_id
  ✔ [FIX 2] es_gol / es_al_arco calculados antes del split_location
  ✔ [FIX 3] height_in_cm / market_value_in_eur como float64
  ✔ [FIX 4] dim_calendario con Temporada, Trimestre, Semana y más
  ✔ [FIX 5] EDA filosófico por perfil cruyffista (4 reportes HTML)
  ✔ [FIX 6] Conversión numérica explícita (to_num)
  ✔ [FIX 7] Sección de valoraciones con scatter y cuartiles de mercado
 
  ARCHIVOS CSV (18):
  → dim_jugador, dim_partido, dim_valoracion, dim_calendario
  → fact_shot, fact_pass, fact_duel, fact_dribble, fact_carry
  → fact_pressure, fact_interception, fact_clearance
  → fact_ball_receipt, fact_goalkeeper, fact_foul_committed
  → fact_foul_won, fact_miscontrol, fact_block
 
  FIXES APLICADOS EN V4.3:
  ✔ [FIX 8] Validación cruzada de camiseta SB ↔ TM (game_lineups.csv)
             match_confidence = fuzzy_score + 10 si jersey_sb == jersey_tm
  ✔ [FIX 9] Deduplicación con dos criterios: es_exacto primero, confidence segundo
 
  REPORTES EDA (4):
  ⚽ eda_v4_delanteros.html      (9 falso: xG sin penal, presiones, movilidad)
  🎯 eda_v4_mediocampistas.html  (entre líneas: progresión, presión, pérdidas)
  🛡️ eda_v4_defensores.html      (líbero moderno: zonas altas, salida limpia)
  🔁 eda_v4_laterales.html       (lateral invertido: duelos + conducción centro)
 
  PRÓXIMOS PASOS EN POWER BI:
  → Importar CSVs con sep=';' y decimal=','
  → Conectar: dim_calendario[Date]   → dim_partido[match_date]
  → Conectar: dim_jugador[player_id] → fact_*[player_id]
  → Conectar: dim_partido[match_id]  → fact_*[match_id]
  → Construir medidas DAX con los umbrales sugeridos en cada reporte
""")
 
import shutil
from google.colab import files
shutil.make_archive("scouting_v4_final", "zip", str(OUTPUT_DIR))
files.download("scouting_v4_final.zip")
 