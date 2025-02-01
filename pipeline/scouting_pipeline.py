"""
========================================================
  PIPELINE DE SCOUTING v2- STATSBOMB
  Genera estructura optimizada desde el CSV master
  Output: 6 archivos CSV listos para Power BI
========================================================
"""

import pandas as pd
import numpy as np
import os

# ── CONFIG ────────────────────────────────────────────
INPUT_FILE = "statsbomb_master_scouting_europa.csv"
OUTPUT_DIR = "scouting_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 55)
print("  PIPELINE DE SCOUTING STATSBOMB")
print("=" * 55)

# ── CARGA ─────────────────────────────────────────────
print("\n📂 Cargando CSV master...")
df = pd.read_csv(INPUT_FILE)
print(f"   ✔ {len(df):,} eventos | {df['player'].nunique()} jugadores | {df['team'].nunique()} equipos")


# ══════════════════════════════════════════════════════
# BLOQUE 1 — DIMENSIONES (tablas de referencia)
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 1: Dimensiones ─────────────────────────")

# --- dim_jugador ---
# Posición habitual = la que más aparece en sus eventos
pos_habitual = (
    df.groupby("player")["position"]
    .agg(lambda x: x.value_counts().idxmax() if x.notna().any() else "Desconocida")
    .reset_index()
    .rename(columns={"position": "posicion_habitual"})
)
equipo_habitual = (
    df.groupby("player")["team"]
    .agg(lambda x: x.value_counts().idxmax() if x.notna().any() else "Desconocido")
    .reset_index()
    .rename(columns={"team": "equipo_habitual"})
)
dim_jugador = (
    pos_habitual
    .merge(equipo_habitual, on="player")
    .reset_index(drop=True)
)
dim_jugador.insert(0, "player_id", dim_jugador.index + 1)
dim_jugador.to_csv(f"{OUTPUT_DIR}/dim_jugador.csv", index=False, sep=";", decimal=",")
print(f"   ✔ dim_jugador         → {len(dim_jugador):,} filas")

# Mapa nombre → id para unir a los facts
player_id_map = dict(zip(dim_jugador["player"], dim_jugador["player_id"]))

# --- dim_partido ---
dim_partido = (
    df[["match_id", "liga_origen"]]
    .drop_duplicates("match_id")
    .sort_values("match_id")
    .reset_index(drop=True)
)
# Extraer temporada desde el nombre de la liga
dim_partido["temporada"] = dim_partido["liga_origen"].str.extract(r"(\d{2}/\d{2})")
dim_partido["competicion"] = dim_partido["liga_origen"].str.extract(r"^(.*?)\s\d")
dim_partido.to_csv(f"{OUTPUT_DIR}/dim_partido.csv", index=False, sep=";", decimal=",")
print(f"   ✔ dim_partido         → {len(dim_partido):,} filas")


# ══════════════════════════════════════════════════════
# BLOQUE 2 — TABLAS DE HECHOS (modelo estrella)
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 2: Tablas de hechos ────────────────────")

# Columnas de contexto compartido por todos los facts
CONTEXTO = ["match_id", "period", "minute", "timestamp", "team", "player",
            "position", "under_pressure", "counterpress", "liga_origen"]

def add_player_id(frame):
    frame = frame.copy()
    frame.insert(0, "player_id", frame["player"].map(player_id_map))
    return frame

# --- fact_pases ---
pases = df[df["type"] == "Pass"][
    CONTEXTO + ["pass_outcome", "pass_length", "pass_recipient",
                "pass_shot_assist", "pass_assisted_shot_id"]
].copy()
pases["es_pase_completo"] = (pases["pass_outcome"] == "Complete").astype(int)
pases["es_asistencia_tiro"] = pases["pass_shot_assist"].notna().astype(int)
pases = add_player_id(pases)
pases.to_csv(f"{OUTPUT_DIR}/fact_pases.csv", index=False, sep=";", decimal=",")
print(f"   ✔ fact_pases          → {len(pases):,} filas")

# --- fact_tiros ---
tiros = df[df["type"] == "Shot"][
    CONTEXTO + ["shot_statsbomb_xg", "shot_outcome", "shot_technique",
                "shot_key_pass_id", "es_gol"]
].copy()
tiros["es_al_arco"] = tiros["shot_outcome"].isin(["Saved", "Goal"]).astype(int)
tiros = add_player_id(tiros)
tiros.to_csv(f"{OUTPUT_DIR}/fact_tiros.csv", index=False, sep=";", decimal=",")
print(f"   ✔ fact_tiros          → {len(tiros):,} filas")

# --- fact_duelos ---
EXITOS_DUELO = {"Won", "Success", "Success In Play", "Success Out"}
duelos = df[df["type"] == "Duel"][
    CONTEXTO + ["duel_type", "duel_outcome"]
].copy()
duelos["es_duelo_ganado"] = duelos["duel_outcome"].isin(EXITOS_DUELO).astype(int)
duelos = add_player_id(duelos)
duelos.to_csv(f"{OUTPUT_DIR}/fact_duelos.csv", index=False, sep=";", decimal=",")
print(f"   ✔ fact_duelos         → {len(duelos):,} filas")

# --- fact_intercepciones ---
EXITOS_INT = {"Won", "Success", "Success In Play", "Success Out"}
intercepciones = df[df["type"] == "Interception"][
    CONTEXTO + ["interception_outcome"]
].copy()
intercepciones["es_intercepcion_exitosa"] = intercepciones["interception_outcome"].isin(EXITOS_INT).astype(int)
intercepciones = add_player_id(intercepciones)
intercepciones.to_csv(f"{OUTPUT_DIR}/fact_intercepciones.csv", index=False, sep=";", decimal=",")
print(f"   ✔ fact_intercepciones → {len(intercepciones):,} filas")

# --- fact_despejes ---
despejes = df[df["type"] == "Clearance"][CONTEXTO].copy()
despejes = add_player_id(despejes)
despejes.to_csv(f"{OUTPUT_DIR}/fact_despejes.csv", index=False, sep=";", decimal=",")
print(f"   ✔ fact_despejes       → {len(despejes):,} filas")


# ══════════════════════════════════════════════════════
# BLOQUE 3 — RESUMEN DE SCOUTING (una fila por jugador)
# ══════════════════════════════════════════════════════

print("\n── BLOQUE 3: Tabla resumen de scouting ───────────")

# Métricas de pases
met_pases = pases.groupby("player").agg(
    partidos_jugados=("match_id", "nunique"),
    total_pases=("pass_outcome", "count"),
    pases_completos=("es_pase_completo", "sum"),
    long_pase_promedio=("pass_length", "mean"),
    asistencias_tiro=("es_asistencia_tiro", "sum"),
).rename(columns={"partidos_jugados": "partidos_jugados_pases"})
met_pases["pct_pases_completos"] = (
    met_pases["pases_completos"] / met_pases["total_pases"] * 100
).round(1)
met_pases["long_pase_promedio"] = met_pases["long_pase_promedio"].round(2)

# Métricas de pases bajo presión
pases_presion = pases[pases["under_pressure"] == True].groupby("player").agg(
    pases_bajo_presion=("pass_outcome", "count"),
    pases_completos_presion=("es_pase_completo", "sum"),
)
pases_presion["pct_pases_presion"] = (
    pases_presion["pases_completos_presion"] / pases_presion["pases_bajo_presion"] * 100
).round(1)

# Métricas de tiros
met_tiros = tiros.groupby("player").agg(
    total_tiros=("shot_outcome", "count"),
    goles=("es_gol", "sum"),
    tiros_al_arco=("es_al_arco", "sum"),
    xg_total=("shot_statsbomb_xg", "sum"),
    xg_promedio=("shot_statsbomb_xg", "mean"),
)
met_tiros["pct_tiros_al_arco"] = (
    met_tiros["tiros_al_arco"] / met_tiros["total_tiros"] * 100
).round(1)
met_tiros["xg_total"] = met_tiros["xg_total"].round(3)
met_tiros["xg_promedio"] = met_tiros["xg_promedio"].round(3)
met_tiros["goles_sobre_xg"] = (met_tiros["goles"] - met_tiros["xg_total"]).round(3)

# Métricas de duelos
met_duelos = duelos.groupby("player").agg(
    total_duelos=("duel_outcome", "count"),
    duelos_ganados=("es_duelo_ganado", "sum"),
)
met_duelos["pct_duelos_ganados"] = (
    met_duelos["duelos_ganados"] / met_duelos["total_duelos"] * 100
).round(1)

# Métricas de intercepciones
met_int = intercepciones.groupby("player").agg(
    total_intercepciones=("interception_outcome", "count"),
    intercepciones_exitosas=("es_intercepcion_exitosa", "sum"),
)
met_int["pct_intercepciones_exitosas"] = (
    met_int["intercepciones_exitosas"] / met_int["total_intercepciones"] * 100
).round(1)

# Despejes
met_desp = despejes.groupby("player").agg(total_despejes=("match_id", "count"))

# Partidos únicos totales (unión de todos los eventos)
partidos_totales = df.groupby("player")["match_id"].nunique().rename("partidos_totales")

# Unir todo
resumen = (
    dim_jugador[["player_id", "player", "posicion_habitual", "equipo_habitual"]]
    .set_index("player")
    .join(partidos_totales)
    .join(met_pases.drop(columns="partidos_jugados_pases"))
    .join(pases_presion[["pases_bajo_presion", "pct_pases_presion"]])
    .join(met_tiros)
    .join(met_duelos)
    .join(met_int)
    .join(met_desp)
    .reset_index()
    .fillna(0)
)

# Métricas por partido (normalización clave para comparar jugadores con distinta carga)
resumen["pases_por_partido"] = (resumen["total_pases"] / resumen["partidos_totales"]).round(2)
resumen["tiros_por_partido"]  = (resumen["total_tiros"] / resumen["partidos_totales"]).round(2)
resumen["xg_por_partido"]     = (resumen["xg_total"] / resumen["partidos_totales"]).round(3)
resumen["duelos_por_partido"] = (resumen["total_duelos"] / resumen["partidos_totales"]).round(2)
resumen["intercepciones_por_partido"] = (resumen["total_intercepciones"] / resumen["partidos_totales"]).round(2)

# Ordenar columnas de forma lógica
orden = [
    "player_id", "player", "posicion_habitual", "equipo_habitual", "partidos_totales",
    # Pases
    "total_pases", "pases_completos", "pct_pases_completos", "long_pase_promedio",
    "pases_bajo_presion", "pct_pases_presion", "asistencias_tiro", "pases_por_partido",
    # Tiros
    "total_tiros", "tiros_al_arco", "pct_tiros_al_arco",
    "goles", "xg_total", "xg_promedio", "goles_sobre_xg",
    "tiros_por_partido", "xg_por_partido",
    # Duelos
    "total_duelos", "duelos_ganados", "pct_duelos_ganados", "duelos_por_partido",
    # Defensa
    "total_intercepciones", "intercepciones_exitosas", "pct_intercepciones_exitosas",
    "intercepciones_por_partido", "total_despejes",
]
resumen = resumen[orden]
resumen.to_csv(f"{OUTPUT_DIR}/resumen_scouting_jugadores.csv", index=False, sep=";", decimal=",")
print(f"   ✔ resumen_scouting    → {len(resumen):,} jugadores | {len(resumen.columns)} métricas")


# ══════════════════════════════════════════════════════
# RESUMEN FINAL
# ══════════════════════════════════════════════════════

print("\n" + "=" * 55)
print("  ✅ PIPELINE COMPLETADO")
print("=" * 55)
print(f"\n  Archivos generados en: ./{OUTPUT_DIR}/\n")
archivos = [
    ("dim_jugador.csv",                 "Dimensión jugadores con posición habitual"),
    ("dim_partido.csv",                 "Dimensión partidos con liga y temporada"),
    ("fact_pases.csv",                  "Eventos de pases (nivel granular)"),
    ("fact_tiros.csv",                  "Eventos de tiros con xG (nivel granular)"),
    ("fact_duelos.csv",                 "Eventos de duelos (nivel granular)"),
    ("fact_intercepciones.csv",         "Eventos de intercepciones (nivel granular)"),
    ("fact_despejes.csv",               "Eventos de despejes (nivel granular)"),
    ("resumen_scouting_jugadores.csv",  "⭐ Tabla resumen — una fila por jugador"),
]
for nombre, desc in archivos:
    print(f"  📄 {nombre:<38} {desc}")
print()