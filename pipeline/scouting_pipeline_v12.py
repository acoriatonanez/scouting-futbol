"""
========================================================
  PIPELINE DE SCOUTING V12
  StatsBomb open-data + Transfermarkt Kaggle

  Entorno: La Liga | 2014/15 a 2019/20 (6 temporadas)

  Output:
    - 18 CSV: 4 dimensiones + 14 tablas fact
    - 1 reporte HTML de conformidad

  Fixes principales v5:
    1. Sin comandos magicos de Colab dentro del pipeline.
    2. Descarga de datos opcional via --download-data.
    3. Coordenadas preservadas como listas para poder separarlas en x/y.
    4. Pases y recepciones exitosas corregidos: outcome nulo = exito en StatsBomb.
    5. Booleanos robustos al leer CSV.
    6. Transfermarkt deduplicado antes del matching exacto/fuzzy.
    7. Jugadores StatsBomb sin match Transfermarkt se conservan en dim_jugador.
    8. Filtros robustos ante columnas/archivos faltantes.
    9. EDA robusto ante perfiles vacios o con pocos datos.
   10. Sin dependencia de numero de camiseta.

  Cambios v6 (EDA orientado a criterios para DAX):
   11. DEFENSOR: reemplaza despejes_aereos (datos insuficientes + perfil incorrecto)
       por carrys_progresivos_zona_media como proxy de "correccion a campo abierto".
   12. SCATTER INTERACTIVO: el grafico de dispersion es ahora un widget JS con selector
       desplegable que permite cambiar la metrica del eje X en el browser, sin recalcular.
       Los datos se embeben como JSON en el HTML. Se mantiene regresion lineal y medianas.
   13. NORTE DEL EDA CLARIFICADO: el reporte HTML reorganiza sus secciones para que
       el foco sea generar CRITERIOS para construir medidas en Power BI
       (umbrales P50/P75/P90, alertas de outliers, cobertura de datos por metrica).
       La narrativa de storytelling queda reservada para el dashboard final.

  Cambios v7 (robustez + consistencia):
   14. Defaults, nombres de reportes, ZIP y mensajes actualizados de v5/v6 a v7.
   15. Booleanos robustos con normalizacion unicode y soporte para "si"/"sí".
   16. HTML escapado en tablas, labels y hallazgos para evitar markup roto.
   17. EDA tolerante a dimensiones vacias o columnas faltantes.
   18. Texto mojibakeado corregido en reportes y etiquetas.

  Cambios v8 (EDA interactivo):
   19. Histogramas y boxplots de metricas migrados a Canvas interactivo.
   20. Boxplot Canvas con whiskers IQR y outliers, consistente con la tabla IQR.
   21. Delanteros incorporan dribbles exitosos en campo rival.
   22. Notas DAX conservadas como criterios accionables dentro del reporte.

  Cambios v9 (fact_minutes + reestructura EDA):
   23. FACT_MINUTES: nueva tabla con minutos jugados por jugador x partido,
       derivada de eventos Starting XI, Substitution y Half End.
       Columnas: match_id, player_id, team_id, minuto_entrada, minuto_salida,
       minutos_jugados, es_titular, fue_sustituido.
   24. ESTRUCTURA HTML REORDENADA: el reporte EDA sigue el orden pedagogico:
       1. Universo del perfil
       2. Umbrales por percentil
       3. Estadisticas descriptivas
       4. Outliers IQR - alerta de distorsion en rankings
       5. Distribuciones y boxplot IQR (graficos)
       6. Correlacion con valor de mercado
       7. Criterios accionables para Power BI
   25. TERMINOLOGIA LIMPIA: se elimina toda referencia a "DAX" en titulos,
       badges y textos del reporte HTML. Se usa "Power BI" o criterios accionables.

  Cambios v10 (schema rectangular + flags 0/1):
   26. SCHEMA CANONICO POR FACT: cada chunk se reindexa con columnas esperadas
       antes del append incremental, evitando CSV ragged y columnas desalineadas.
   27. FLAGS DERIVADOS SIEMPRE PRESENTES: es_dribble_exitoso, es_duelo_ganado,
       es_pase_completo, es_recepcion_exitosa y equivalentes se generan con
       default explicito y se exportan como enteros 0/1.

  Cambios v11 (valoraciones historicas Transfermarkt):
   28. DIM_VALORACION usa el pico de market_value_in_eur entre FECHAS_INICIO y
       FECHAS_FIN desde player_valuations.csv, no el snapshot actual.
   29. MATCH DE VALORACIONES: fuzzy dedicado contra players.csv con umbral 88
       y diagnostico para Gerard Pique, Ivan Rakitic y Jordi Alba.

  Cambios v12 (6 temporadas + esquema reducido para Power BI):
   30. TEMPORADAS: OBJETIVOS ahora cubre La Liga 2014/15 a 2019/20 (6
       temporadas, season_id 26/27/2/1/4/42). Se excluye 2020/21 (COVID) y
       las demas ligas europeas por tener una sola temporada disponible.
       FECHAS_FIN pasa a 2020-06-30.
   31. FACT_GOALKEEPER ELIMINADA: "Goal Keeper" se excluye de EVENTOS_OBJETIVO,
       COLS_EVENTO y NOMBRE_ARCHIVO (mapeado a None). El universo de porteros
       es insuficiente para rankings percentilados.
   32. ESQUEMA REDUCIDO: COLS_EVENTO se recorta a las columnas necesarias para
       Power BI. Las columnas *_outcome usadas para calcular flags derivados
       (es_pase_completo, es_dribble_exitoso, etc.) viven en COLS_INTERNAS:
       se incluyen en el subset de procesamiento pero no se exportan al CSV.
   33. CONTEXTO REDUCIDO: se eliminan team, player, possession_team,
       play_pattern, timestamp y counterpress (redundantes via FK a las
       dimensiones). equipo_habitual en build_dimensiones() se deriva de
       all_lineups en vez de fact_pass.
   34. TRANSFERMARKT: se elimina highest_market_value_in_eur (snapshot poco
       confiable); dim_valoracion ya cubre el pico historico.
   35. MATCHING CON SCORE COMPUESTO: blocking por pais normalizado + score
       0.60*nombre + 0.25*pais + 0.15*posicion (umbral 0.75). FUZZY_UMBRAL
       queda deprecado.
   36. REPORTE DE CONFORMIDAD: generar_reportes_eda() y sus graficos se
       reemplazan por generar_reporte_conformidad(), que valida estructura
       y cobertura del output (sin contenido analitico). --skip-eda pasa a
       --skip-report.

  Cambios v12.1 (recorte de columnas/tablas no usadas en el modelo DAX):
   37. EVENTOS ELIMINADOS: Clearance, Foul Committed, Foul Won y Block ya
       no se procesan (no aportan a ninguna medida DAX ni a la heatmap).
       Dejan de generarse fact_clearance, fact_foul_committed, fact_foul_won
       y fact_block.
   38. CONTEXTO RECORTADO: se eliminan possession_team_id, period y second
       de CONTEXTO (no se usan en ninguna medida ni relacion). Se mantienen
       team_id, minute, under_pressure y position por conservadurismo
       (uso potencial fuera del DAX documentado).
   39. FACT_SHOT: se agrega shot_type a COLS_EVENTO, requerido por la medida
       "xG Sin Penal" para excluir shot_type = "Penalty".
   40. FACT_PASS: pass_recipient_id (columna que nunca se poblaba, ya que
       flatten_event vuelca pass.recipient.name en "pass_recipient") se
       reemplaza por pass_recipient, requerido por "Total Desmarques Ruptura".

  Cambios v12.2 (matching StatsBomb-Transfermarkt mas fiel):
   41. UNIVERSO LA LIGA: cargar_liga_player_ids() usa appearances.csv
       (competition_id "ES1", FECHAS_INICIO-FECHAS_FIN) para identificar que
       tm_player_id jugaron La Liga en las mismas temporadas. Blocking de alta
       confianza, ya que StatsBomb y Transfermarkt cubren la misma poblacion.
   42. DEDUP DE TM_PLAYERS_MATCH: ante nombres normalizados duplicados, se
       prefiere el candidato del universo La Liga sobre el de mayor
       market_value_in_eur (antes solo se usaba market_value).
   43. MATCHING POR TIERS: matching_jugadores() ahora prueba, en orden,
       (0) match exacto por apodo/player_nickname, (1) fuzzy dentro del
       universo La Liga (umbral 0.65), (2) fuzzy por pais (umbral 0.75, como
       antes), (3) fuzzy global sin blocking (umbral subido a 0.85, mas
       exigente por ser el mas arriesgado).
   44. POSICION REAL EN EL SCORE: se agrega compute_posicion_habitual()
       (lee fact_pass.csv) y se pasa a matching_jugadores() ANTES del
       matching. Corrige un bug donde _posicion_similar() siempre recibia ""
       y el 15% de peso por posicion no aportaba nada.
   45. METODO_MATCH: nueva columna diagnostica en dim_jugador que indica como
       se resolvio cada match (exacto_nombre, exacto_apodo, fuzzy_liga,
       fuzzy_pais, fuzzy_global o nulo si no hubo match).
   46. DIM_VALORACION UNIFICADA: build_dim_valoracion_historica() deja de
       hacer un segundo matching fuzzy por nombre (token_set_ratio >= 88) y
       reutiliza dim_jugador["tm_player_id"]. Antes dim_jugador y
       dim_valoracion podian apuntar a distintas personas de Transfermarkt
       para el mismo player_id.
========================================================
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


OBJETIVOS = [
    {"competition_id": 11, "season_id": 26, "nombre": "La Liga 2014/15"},
    {"competition_id": 11, "season_id": 27, "nombre": "La Liga 2015/16"},
    {"competition_id": 11, "season_id": 2, "nombre": "La Liga 2016/17"},
    {"competition_id": 11, "season_id": 1, "nombre": "La Liga 2017/18"},
    {"competition_id": 11, "season_id": 4, "nombre": "La Liga 2018/19"},
    {"competition_id": 11, "season_id": 42, "nombre": "La Liga 2019/20"},
]

EVENTOS_OBJETIVO = {
    "Pass",
    "Shot",
    "Duel",
    "Dribble",
    "Carry",
    "Pressure",
    "Interception",
    "Ball Receipt*",
    "Miscontrol",
    # Eventos de tiempo de juego para fact_minutes
    "Starting XI",
    "Substitution",
    "Half End",
}

FECHAS_INICIO = "2014-07-01"
FECHAS_FIN = "2020-06-30"

CONTEXTO = [
    "match_id",
    "player_id",
    "team_id",
    "minute",
    "location",
    "under_pressure",
    "position",  # necesario para posicion_habitual en build_dimensiones()
]

COLS_EVENTO = {
    "Pass": [
        "pass_end_location",
        "pass_recipient",
        "pass_shot_assist",
        "pass_goal_assist",
        "pass_cross",
        "pass_switch",
        "pass_through_ball",
    ],
    "Shot": [
        "shot_statsbomb_xg",
        "shot_type",
    ],
    "Duel": [],
    "Dribble": [],
    "Carry": ["carry_end_location"],
    "Pressure": [],
    "Interception": [],
    "Ball Receipt*": [],
    "Miscontrol": [],
    # Columnas para calculo de minutos jugados
    "Starting XI": ["tactics"],
    "Substitution": ["substitution_outcome", "substitution_replacement"],
    "Half End": [],
}

# Columnas que se incluyen en el subset durante el procesamiento (para calcular
# flags derivados) pero se excluyen del esquema final por enforce_fact_schema().
COLS_INTERNAS = {
    "Pass": ["pass_outcome"],
    "Shot": ["shot_outcome"],
    "Duel": ["duel_outcome"],
    "Dribble": ["dribble_outcome"],
    "Interception": ["interception_outcome"],
    "Ball Receipt*": ["ball_receipt_outcome"],
}

NOMBRE_ARCHIVO = {
    "Pass": "fact_pass",
    "Shot": "fact_shot",
    "Duel": "fact_duel",
    "Dribble": "fact_dribble",
    "Carry": "fact_carry",
    "Pressure": "fact_pressure",
    "Interception": "fact_interception",
    "Ball Receipt*": "fact_ball_receipt",
    "Goal Keeper": None,  # excluido del output Power BI
    "Miscontrol": "fact_miscontrol",
    # No se routean a CSV incremental; se procesan en build_fact_minutes
    "Starting XI": "_starting_xi_raw",
    "Substitution": "_substitution_raw",
    "Half End": "_half_end_raw",
}

BOOL_FLAG_COLS = {
    "under_pressure",
    "pass_shot_assist",
    "pass_goal_assist",
    "pass_cross",
    "pass_switch",
    "pass_through_ball",
}

DERIVED_FLAG_COLS = {
    "es_pase_completo",
    "es_asistencia_gol",
    "es_asistencia_tiro",
    "es_gol",
    "es_al_arco",
    "es_duelo_ganado",
    "es_dribble_exitoso",
    "es_intercepcion_exitosa",
    "es_recepcion_exitosa",
}

DERIVED_COLS_EVENTO = {
    "Pass": ["es_pase_completo", "es_asistencia_gol", "es_asistencia_tiro"],
    "Shot": ["es_gol", "es_al_arco"],
    "Duel": ["es_duelo_ganado"],
    "Dribble": ["es_dribble_exitoso"],
    "Interception": ["es_intercepcion_exitosa"],
    "Ball Receipt*": ["es_recepcion_exitosa"],
}

SPLIT_LOCATION_COLS = {
    "location": ["location_x", "location_y"],
    "pass_end_location": ["pass_end_x", "pass_end_y"],
    "carry_end_location": ["carry_end_x", "carry_end_y"],
}

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def safe_cols(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def split_location(df: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
    if col not in df.columns:
        return df

    def extraer(v):
        if isinstance(v, list) and len(v) >= 2:
            return pd.Series([v[0], v[1]])
        return pd.Series([np.nan, np.nan])

    coords = df[col].apply(extraer)
    coords.columns = [f"{prefix}_x", f"{prefix}_y"]
    return pd.concat([df.drop(columns=[col]), coords], axis=1)


def normalizar(nombre) -> str:
    if not isinstance(nombre, str):
        return ""
    nombre = unicodedata.normalize("NFD", nombre)
    nombre = "".join(c for c in nombre if unicodedata.category(c) != "Mn")
    nombre = nombre.lower().strip()
    nombre = re.sub(r"[^a-z\s]", "", nombre)
    return re.sub(r"\s+", " ", nombre)


def normalizar_token(value) -> str:
    if not isinstance(value, str):
        return str(value).strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return value.strip().lower()


def esc_html(value) -> str:
    if pd.isna(value):
        return ""
    return html.escape(str(value), quote=True)


def save(df: pd.DataFrame, nombre: str, output_dir: Path) -> None:
    path = output_dir / f"{nombre}.csv"
    df.to_csv(path, index=False, sep=";", decimal=",")
    print(f"   OK {nombre:<42} -> {len(df):>8,} filas | {len(df.columns):>3} cols")


def append_csv(df: pd.DataFrame, nombre: str, output_dir: Path) -> None:
    path = output_dir / f"{nombre}.csv"
    df.to_csv(
        path,
        mode="a",
        header=not path.exists(),
        index=False,
        sep=";",
        decimal=",",
        quoting=csv.QUOTE_ALL,
    )


def to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
    return df


def to_bool(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    truthy = {"true", "1", "yes", "y", "si", "s", "t"}
    for col in cols:
        if col in df.columns:
            normalizada = df[col].map(normalizar_token)
            df[col] = normalizada.isin(truthy).astype(int)
    return df


def flags_to_int(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    truthy = {True, 1, "1", "true", "t", "yes", "y", "si", "s"}

    def es_true(v) -> int:
        if pd.isna(v):
            return 0
        if isinstance(v, str):
            return int(normalizar_token(v) in truthy)
        return int(v in truthy)

    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(es_true).astype("int8")
    return df


def canonical_fact_cols(tipo: str) -> list[str]:
    cols: list[str] = []
    for col in CONTEXTO + COLS_EVENTO.get(tipo, []):
        cols.extend(SPLIT_LOCATION_COLS.get(col, [col]))
    if tipo == "Carry":
        cols.append("carry_distancia")
    cols.extend(DERIVED_COLS_EVENTO.get(tipo, []))
    return list(dict.fromkeys(cols))


def enforce_fact_schema(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
    cols = canonical_fact_cols(tipo)
    df = df.reindex(columns=cols)
    flag_cols = [
        col
        for col in cols
        if col in BOOL_FLAG_COLS or col in DERIVED_FLAG_COLS or col.startswith("es_")
    ]
    return flags_to_int(df, flag_cols)


def serie_vacia(index=None, dtype="float64") -> pd.Series:
    return pd.Series(index=index, dtype=dtype)


def modo_segura(x: pd.Series, default=None):
    x = x.dropna()
    if x.empty:
        return default
    return x.value_counts().idxmax()


def read_csv_safe(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, sep=";", decimal=",", low_memory=False, **kwargs)
    except ValueError:
        kwargs.pop("usecols", None)
        return pd.read_csv(path, sep=";", decimal=",", low_memory=False, **kwargs)


def require_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col not in df.columns:
            df[col] = np.nan
    return df


def install_if_missing(package: str, import_name: str | None = None) -> None:
    import_name = import_name or package
    try:
        __import__(import_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def download_data(repo_parent: Path, tm_path: Path) -> None:
    repo_dir = repo_parent / "open-data"
    if not repo_dir.exists():
        subprocess.check_call(
            ["git", "clone", "https://github.com/statsbomb/open-data.git", str(repo_dir)]
        )

    if not (tm_path / "players.csv").exists():
        install_if_missing("kaggle")
        tm_path.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            [
                "kaggle",
                "datasets",
                "download",
                "-d",
                "davidcariboo/player-scores",
                "--unzip",
                "-p",
                str(tm_path),
            ]
        )


def flatten_event(ev: dict, match_id: int, comp_id: int, seas_id: int, tipo: str) -> dict:
    row = {
        "match_id": match_id,
        "competition_id": comp_id,
        "season_id": seas_id,
        "type": tipo,
        "period": ev.get("period"),
        "timestamp": ev.get("timestamp"),
        "minute": ev.get("minute"),
        "second": ev.get("second"),
        "location": ev.get("location"),
        "player_id": ev.get("player", {}).get("id")
        if isinstance(ev.get("player"), dict)
        else None,
        "player": ev.get("player", {}).get("name")
        if isinstance(ev.get("player"), dict)
        else None,
        "team_id": ev.get("team", {}).get("id") if isinstance(ev.get("team"), dict) else None,
        "team": ev.get("team", {}).get("name") if isinstance(ev.get("team"), dict) else None,
        "position": ev.get("position", {}).get("name")
        if isinstance(ev.get("position"), dict)
        else None,
        "possession_team_id": ev.get("possession_team", {}).get("id")
        if isinstance(ev.get("possession_team"), dict)
        else None,
        "possession_team": ev.get("possession_team", {}).get("name")
        if isinstance(ev.get("possession_team"), dict)
        else None,
        "play_pattern": ev.get("play_pattern", {}).get("name")
        if isinstance(ev.get("play_pattern"), dict)
        else None,
        "under_pressure": bool(ev.get("under_pressure", False)),
        "counterpress": bool(ev.get("counterpress", False)),
        "duration": ev.get("duration"),
    }

    excluded = {
        "type",
        "player",
        "team",
        "position",
        "possession_team",
        "play_pattern",
        "location",
        "related_events",
        "id",
    }
    for key, val in ev.items():
        if isinstance(val, dict) and key not in excluded:
            for subkey, subval in val.items():
                col = f"{key}_{subkey}"
                if isinstance(subval, dict):
                    row[col] = subval.get("name", str(subval))
                elif isinstance(subval, list):
                    row[col] = subval
                else:
                    row[col] = subval
    return row


def build_fact_subset(subset: pd.DataFrame, tipo: str) -> pd.DataFrame:
    extra = COLS_EVENTO.get(tipo, []) + COLS_INTERNAS.get(tipo, [])
    cols = safe_cols(subset, CONTEXTO + extra)
    subset = subset[cols].copy()

    if tipo == "Pass":
        if "pass_outcome" in subset.columns:
            subset["es_pase_completo"] = subset["pass_outcome"].isna().astype(int)
        else:
            subset["es_pase_completo"] = 1
        subset["es_asistencia_gol"] = (
            (subset["pass_goal_assist"] == True).astype(int)
            if "pass_goal_assist" in subset.columns
            else 0
        )
        subset["es_asistencia_tiro"] = (
            (subset["pass_shot_assist"] == True).astype(int)
            if "pass_shot_assist" in subset.columns
            else 0
        )
        subset = split_location(subset, "location", "location")
        subset = split_location(subset, "pass_end_location", "pass_end")

    elif tipo == "Shot":
        if "shot_outcome" in subset.columns:
            subset["es_gol"] = (subset["shot_outcome"] == "Goal").astype(int)
            subset["es_al_arco"] = subset["shot_outcome"].isin(["Goal", "Saved"]).astype(int)
        else:
            subset["es_gol"] = 0
            subset["es_al_arco"] = 0
        subset = split_location(subset, "location", "location")

    elif tipo == "Carry":
        subset = split_location(subset, "location", "location")
        subset = split_location(subset, "carry_end_location", "carry_end")
        needed = ["location_x", "location_y", "carry_end_x", "carry_end_y"]
        if all(c in subset.columns for c in needed):
            subset[needed] = subset[needed].apply(pd.to_numeric, errors="coerce")
            subset["carry_distancia"] = (
                (subset["carry_end_x"] - subset["location_x"]) ** 2
                + (subset["carry_end_y"] - subset["location_y"]) ** 2
            ).pow(0.5).round(2)

    else:
        subset = split_location(subset, "location", "location")

    if tipo == "Duel":
        subset["es_duelo_ganado"] = (
            subset["duel_outcome"]
            .isin({"Won", "Success", "Success In Play", "Success Out"})
            .astype(int)
            if "duel_outcome" in subset.columns
            else 0
        )
    elif tipo == "Dribble":
        subset["es_dribble_exitoso"] = (
            (subset["dribble_outcome"] == "Complete").astype(int)
            if "dribble_outcome" in subset.columns
            else 0
        )
    elif tipo == "Interception":
        subset["es_intercepcion_exitosa"] = (
            subset["interception_outcome"]
            .isin({"Won", "Success", "Success In Play", "Success Out"})
            .astype(int)
            if "interception_outcome" in subset.columns
            else 0
        )
    elif tipo == "Ball Receipt*":
        subset["es_recepcion_exitosa"] = (
            subset["ball_receipt_outcome"].isna().astype(int)
            if "ball_receipt_outcome" in subset.columns
            else 1
        )

    return enforce_fact_schema(subset, tipo)


def cargar_liga_player_ids(tm_path: Path) -> set[int]:
    """
    Universo de tm_player_id que jugaron en La Liga (competition_id "ES1")
    entre FECHAS_INICIO y FECHAS_FIN, segun appearances.csv.

    Se usa solo como blocking de alta confianza para el matching: StatsBomb
    y Transfermarkt cubren las mismas ligas/temporadas, asi que un candidato
    presente en este universo es mucho mas probable que sea el jugador correcto.
    No se exporta a Power BI.
    """
    appearances_path = tm_path / "appearances.csv"
    if not appearances_path.exists():
        print("   Aviso: appearances.csv no encontrado; matching sin blocking de liga/temporada.")
        return set()

    try:
        apps = pd.read_csv(
            appearances_path,
            usecols=["player_id", "competition_id", "date"],
            low_memory=False,
        )
    except ValueError:
        print("   Aviso: appearances.csv sin las columnas esperadas; matching sin blocking de liga/temporada.")
        return set()

    apps["date"] = pd.to_datetime(apps["date"], errors="coerce")
    apps = apps[
        (apps["competition_id"] == "ES1")
        & (apps["date"] >= FECHAS_INICIO)
        & (apps["date"] <= FECHAS_FIN)
    ]
    liga_player_ids = set(pd.to_numeric(apps["player_id"], errors="coerce").dropna().astype(int))
    print(f"   Universo La Liga ({FECHAS_INICIO} a {FECHAS_FIN}, appearances ES1): {len(liga_player_ids):,} jugadores TM")
    return liga_player_ids


def cargar_transfermarkt(tm_path: Path) -> tuple[pd.DataFrame, set[int], pd.DataFrame]:
    tm_players = pd.read_csv(tm_path / "players.csv", low_memory=False)
    base_cols = [
        "player_id",
        "name",
        "date_of_birth",
        "country_of_citizenship",
        "country_of_birth",  # solo para fallback si citizenship es nulo
        "sub_position",
        "position",  # solo para fallback si sub_position es nulo
        "foot",
        "height_in_cm",
        "market_value_in_eur",
    ]
    tm_players = require_columns(tm_players, base_cols)
    tm_players = tm_players[base_cols].rename(columns={"player_id": "tm_player_id", "name": "tm_name"})
    if "country_of_citizenship" not in tm_players.columns or tm_players["country_of_citizenship"].isna().all():
        tm_players["country_of_citizenship"] = tm_players["country_of_birth"]
    if "sub_position" not in tm_players.columns or tm_players["sub_position"].isna().all():
        tm_players["sub_position"] = tm_players["position"]

    for col in ["height_in_cm", "market_value_in_eur"]:
        tm_players[col] = pd.to_numeric(tm_players[col], errors="coerce")
    tm_players["tm_player_id"] = pd.to_numeric(tm_players["tm_player_id"], errors="coerce").astype(
        "Int64"
    )
    tm_players["nombre_norm"] = tm_players["tm_name"].apply(normalizar)

    liga_player_ids = cargar_liga_player_ids(tm_path)

    tm_players_match = (
        tm_players.assign(en_liga=tm_players["tm_player_id"].isin(liga_player_ids))
        .sort_values(
            ["nombre_norm", "en_liga", "market_value_in_eur"],
            ascending=[True, False, False],
            na_position="last",
        )
        .drop_duplicates("nombre_norm", keep="first")
        .drop(columns=["en_liga"])
        .copy()
    )
    tm_players_match = tm_players_match[tm_players_match["nombre_norm"] != ""].copy()

    tm_valuations = pd.read_csv(tm_path / "player_valuations.csv", low_memory=False)
    tm_valuations["date"] = pd.to_datetime(tm_valuations["date"], errors="coerce")
    tm_valuations = tm_valuations[
        (tm_valuations["date"] >= FECHAS_INICIO) & (tm_valuations["date"] <= FECHAS_FIN)
    ].rename(columns={"player_id": "tm_player_id"})
    tm_valuations["tm_player_id"] = pd.to_numeric(
        tm_valuations["tm_player_id"], errors="coerce"
    ).astype("Int64")
    tm_valuations["market_value_in_eur"] = pd.to_numeric(
        tm_valuations["market_value_in_eur"], errors="coerce"
    )
    return tm_players_match, liga_player_ids, tm_valuations


def procesar_partidos(repo_path: Path, output_dir: Path) -> tuple[list[dict], list[dict], int]:
    for nombre in NOMBRE_ARCHIVO.values():
        if nombre is None:
            continue
        path = output_dir / f"{nombre}.csv"
        if path.exists():
            path.unlink()

    all_matches = []
    all_lineups = []
    conteo_total = 0

    for obj in OBJETIVOS:
        comp_id = obj["competition_id"]
        seas_id = obj["season_id"]
        nombre = obj["nombre"]
        matches_path = repo_path / "matches" / str(comp_id) / f"{seas_id}.json"

        if not matches_path.exists():
            print(f"   Aviso: no encontrado {matches_path}")
            continue

        matches = load_json(matches_path)
        print(f"\n   {nombre} - {len(matches)} partidos")

        for i, match in enumerate(matches):
            mid = match["match_id"]
            all_matches.append(
                {
                    "match_id": mid,
                    "competition_id": comp_id,
                    "competition": match["competition"]["competition_name"],
                    "season_id": seas_id,
                    "season": match["season"]["season_name"],
                    "match_date": match.get("match_date"),
                    "kick_off": match.get("kick_off"),
                    "match_week": match.get("match_week"),
                    "home_team_id": match["home_team"]["home_team_id"],
                    "home_team": match["home_team"]["home_team_name"],
                    "away_team_id": match["away_team"]["away_team_id"],
                    "away_team": match["away_team"]["away_team_name"],
                    "home_score": match.get("home_score"),
                    "away_score": match.get("away_score"),
                    "stadium": match.get("stadium", {}).get("name")
                    if match.get("stadium")
                    else None,
                    "referee": match.get("referee", {}).get("name")
                    if match.get("referee")
                    else None,
                }
            )

            lineups_path = repo_path / "lineups" / f"{mid}.json"
            if lineups_path.exists():
                for team_lineup in load_json(lineups_path):
                    for player in team_lineup.get("lineup", []):
                        all_lineups.append(
                            {
                                "match_id": mid,
                                "team_id": team_lineup["team_id"],
                                "team": team_lineup["team_name"],
                                "player_id": player["player_id"],
                                "player": player["player_name"],
                                "player_nickname": player.get("player_nickname"),
                                "jersey_number": player.get("jersey_number"),
                                "country": player.get("country", {}).get("name")
                                if player.get("country")
                                else None,
                            }
                        )

            events_path = repo_path / "events" / f"{mid}.json"
            if not events_path.exists():
                continue

            rows = []
            for ev in load_json(events_path):
                tipo_raw = ev.get("type")
                tipo = tipo_raw.get("name") if isinstance(tipo_raw, dict) else tipo_raw
                if tipo in EVENTOS_OBJETIVO:
                    rows.append(flatten_event(ev, mid, comp_id, seas_id, tipo))

            if not rows:
                continue

            df_match = pd.DataFrame(rows)
            conteo_total += len(df_match)

            # Tipos de tiempo de juego: se acumulan en archivos raw temporales (prefijo _)
            # separados para no contaminar las fact tables de eventos.
            TIPOS_TIEMPO = {"Starting XI", "Substitution", "Half End"}

            for tipo, nombre_csv in NOMBRE_ARCHIVO.items():
                if nombre_csv is None:
                    continue
                subset = df_match[df_match["type"] == tipo].copy()
                if subset.empty:
                    continue
                if tipo in TIPOS_TIEMPO:
                    # Solo guardar columnas clave para build_fact_minutes
                    cols_tiempo = safe_cols(subset, ["match_id", "player_id", "team_id", "period", "minute", "second", "type"] + COLS_EVENTO.get(tipo, []))
                    append_csv(subset[cols_tiempo], nombre_csv, output_dir)
                else:
                    append_csv(build_fact_subset(subset, tipo), nombre_csv, output_dir)

            if (i + 1) % 10 == 0:
                print(
                    f"      {i + 1}/{len(matches)} partidos procesados - "
                    f"{conteo_total:,} eventos acumulados"
                )

    return all_matches, all_lineups, conteo_total


GRUPOS_POSICION = {
    "delantero": {
        "Center Forward", "Left Wing", "Right Wing",
        "Secondary Striker", "Left Center Forward",
        "Right Center Forward",
    },
    "mediocampista": {
        "Center Midfield", "Center Attacking Midfield",
        "Center Defensive Midfield", "Left Midfield",
        "Right Midfield", "Left Center Midfield",
        "Right Center Midfield", "Left Defensive Midfield",
        "Right Defensive Midfield",
    },
    "defensor": {"Center Back", "Left Center Back", "Right Center Back"},
    "lateral": {
        "Left Back", "Right Back", "Left Wing Back",
        "Right Wing Back",
    },
    "portero": {"Goalkeeper"},
}

TM_A_GRUPO = {
    "Centre-Forward": "delantero", "Left Winger": "delantero",
    "Right Winger": "delantero", "Second Striker": "delantero",
    "Central Midfield": "mediocampista",
    "Attacking Midfield": "mediocampista",
    "Defensive Midfield": "mediocampista",
    "Left Midfield": "mediocampista", "Right Midfield": "mediocampista",
    "Centre-Back": "defensor",
    "Left-Back": "lateral", "Right-Back": "lateral",
    "Goalkeeper": "portero",
}


def _posicion_similar(pos_sb: str, sub_pos_tm: str) -> float:
    if not pos_sb or not sub_pos_tm:
        return 0.0
    grupo_sb = next(
        (g for g, s in GRUPOS_POSICION.items() if pos_sb in s), None
    )
    grupo_tm = TM_A_GRUPO.get(sub_pos_tm)
    return 1.0 if grupo_sb and grupo_sb == grupo_tm else 0.0


def compute_posicion_habitual(output_dir: Path) -> pd.DataFrame:
    """
    posicion_habitual (StatsBomb position name) por player_id, derivada de
    fact_pass.csv. Se calcula antes del matching para que _posicion_similar()
    pueda usarla como senal real (antes siempre era "" porque sb_players no
    tenia esta columna), y se reutiliza en build_dimensiones().
    """
    fact_pass = read_csv_safe(
        output_dir / "fact_pass.csv",
        usecols=["player_id", "position"],
        nrows=500000,
        on_bad_lines="skip",
    )
    if fact_pass.empty or not {"player_id", "position"}.issubset(fact_pass.columns):
        return pd.DataFrame(columns=["player_id", "posicion_habitual"])
    return (
        fact_pass.groupby("player_id")["position"]
        .agg(lambda x: modo_segura(x, "Desconocida"))
        .reset_index()
        .rename(columns={"position": "posicion_habitual"})
    )


# Umbrales del score compuesto (0.60*nombre + 0.25*pais + 0.15*posicion) por tier
# de candidatos. El tier "liga" (jugadores que constan en appearances.csv de
# La Liga durante FECHAS_INICIO-FECHAS_FIN) es de alta confianza porque
# StatsBomb y Transfermarkt cubren exactamente la misma liga y temporadas:
# basta con un score moderado para aceptar el match. El tier global (sin
# blocking) es el mas arriesgado y exige un score mayor.
UMBRAL_LIGA = 0.65
UMBRAL_PAIS = 0.75
UMBRAL_GLOBAL = 0.85

MERGE_FINAL_COLS = [
    "player_id",
    "player",
    "country",
    "nombre_norm",
    "tm_player_id",
    "tm_name",
    "date_of_birth",
    "country_of_citizenship",
    "sub_position",
    "foot",
    "height_in_cm",
    "market_value_in_eur",
    "fuzzy_score",
    "metodo_match",
]


def matching_jugadores(
    all_lineups: list[dict],
    tm_players_match: pd.DataFrame,
    liga_player_ids: set[int],
    pos_habitual: pd.DataFrame,
) -> pd.DataFrame:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        install_if_missing("rapidfuzz")
        from rapidfuzz import fuzz

    lineups_df = pd.DataFrame(all_lineups)
    if lineups_df.empty:
        return pd.DataFrame(columns=MERGE_FINAL_COLS)

    if "player_nickname" not in lineups_df.columns:
        lineups_df["player_nickname"] = pd.NA

    sb_players = (
        lineups_df.groupby("player_id")
        .agg(
            player=("player", "first"),
            country=("country", "first"),
            player_nickname=("player_nickname", "first"),
        )
        .reset_index()
    )
    sb_players["nombre_norm"] = sb_players["player"].apply(normalizar)
    sb_players["nickname_norm"] = sb_players["player_nickname"].apply(normalizar)
    sb_players = sb_players.merge(pos_habitual, on="player_id", how="left")
    sb_players["posicion_habitual"] = sb_players["posicion_habitual"].fillna("Desconocida")

    tm_cols = [
        "tm_player_id",
        "tm_name",
        "nombre_norm",
        "date_of_birth",
        "country_of_citizenship",
        "sub_position",
        "foot",
        "height_in_cm",
        "market_value_in_eur",
    ]
    merge_exacto = sb_players.merge(tm_players_match[tm_cols], on="nombre_norm", how="left")
    merge_exacto["fuzzy_score"] = np.where(merge_exacto["tm_player_id"].notna(), 100, np.nan)
    merge_exacto["metodo_match"] = np.where(
        merge_exacto["tm_player_id"].notna(), "exacto_nombre", pd.NA
    )

    con_match = merge_exacto[merge_exacto["tm_player_id"].notna()].copy()
    sin_match = merge_exacto[merge_exacto["tm_player_id"].isna()][
        ["player_id", "player", "nombre_norm", "country", "nickname_norm", "posicion_habitual"]
    ].copy()
    print(f"   Match exacto (nombre): {len(con_match):>4} jugadores")
    print(f"   Sin match:             {len(sin_match):>4} jugadores - aplicando apodo/fuzzy")

    tm_players_match = tm_players_match.copy()
    tm_players_match["pais_norm"] = tm_players_match["country_of_citizenship"].apply(
        lambda x: normalizar(str(x)) if pd.notna(x) else ""
    )
    tm_por_pais = {
        pais: grupo
        for pais, grupo in tm_players_match.groupby("pais_norm")
        if pais != ""
    }
    liga_pool = tm_players_match[tm_players_match["tm_player_id"].isin(liga_player_ids)]
    tm_data = tm_players_match.set_index("nombre_norm")

    def mejor_en_pool(pool: pd.DataFrame, nombres_sb: list[str], pais_sb: str, pos_sb: str) -> tuple[float, str | None]:
        if pool.empty:
            return 0.0, None
        mejor_score = 0.0
        mejor_nombre = None
        for _, tm_row in pool.iterrows():
            tm_norm = tm_row["nombre_norm"]
            s_nombre = max(
                (fuzz.token_set_ratio(nom, tm_norm) / 100 for nom in nombres_sb), default=0.0
            )
            s_pais = 1.0 if pais_sb and tm_row["pais_norm"] == pais_sb else 0.0
            s_posicion = _posicion_similar(pos_sb, str(tm_row.get("sub_position", "") or ""))
            score_total = 0.60 * s_nombre + 0.25 * s_pais + 0.15 * s_posicion
            if score_total > mejor_score:
                mejor_score = score_total
                mejor_nombre = tm_norm
        return mejor_score, mejor_nombre

    fuzzy_rows = []
    no_match_rows = []

    for _, row in sin_match.iterrows():
        nombre_sb = row["nombre_norm"]
        nick_sb = row["nickname_norm"]
        pais_sb = normalizar(str(row.get("country", "") or ""))
        pos_sb = str(row.get("posicion_habitual", "") or "")
        nombres_sb = [n for n in {nombre_sb, nick_sb} if n]

        if not nombres_sb:
            no_match_rows.append(_fila_sin_match(row))
            continue

        # 0. Match exacto por apodo (ej. "Leo Messi" -> tm_name "Lionel Messi"
        # solo coincide via nickname "Messi" no, pero "Coutinho", "Pirlo", etc si).
        # Se exige largo minimo para evitar falsos positivos con apodos cortos.
        if nick_sb and len(nick_sb) >= 6 and nick_sb in tm_data.index and nick_sb != nombre_sb:
            tm_row = tm_data.loc[nick_sb]
            if isinstance(tm_row, pd.DataFrame):
                tm_row = tm_row.iloc[0]
            fuzzy_rows.append(_fila_match(row, tm_row, 100.0, "exacto_apodo"))
            continue

        # 1. Tier liga: jugadores presentes en La Liga durante las mismas
        # temporadas segun Transfermarkt. Blocking de muy alta confianza.
        liga_pool_pais = (
            liga_pool[liga_pool["pais_norm"] == pais_sb] if pais_sb and not liga_pool.empty else pd.DataFrame()
        )
        score, nombre = mejor_en_pool(
            liga_pool_pais if not liga_pool_pais.empty else liga_pool, nombres_sb, pais_sb, pos_sb
        )
        if score >= UMBRAL_LIGA and nombre:
            fuzzy_rows.append(_fila_match(row, tm_data.loc[nombre], score * 100, "fuzzy_liga"))
            continue

        # 2. Tier pais: candidatos del mismo pais con nombre fuzzy >= 60
        candidatos_pais = tm_por_pais.get(pais_sb, pd.DataFrame())
        if not candidatos_pais.empty:
            mask = candidatos_pais["nombre_norm"].apply(
                lambda n: any(fuzz.token_set_ratio(nom, n) >= 60 for nom in nombres_sb)
            )
            candidatos = candidatos_pais[mask]
        else:
            candidatos = pd.DataFrame()

        score, nombre = mejor_en_pool(candidatos, nombres_sb, pais_sb, pos_sb)
        if score >= UMBRAL_PAIS and nombre:
            fuzzy_rows.append(_fila_match(row, tm_data.loc[nombre], score * 100, "fuzzy_pais"))
            continue

        # 3. Tier global: sin blocking, umbral mas exigente
        score, nombre = mejor_en_pool(tm_players_match, nombres_sb, pais_sb, pos_sb)
        if score >= UMBRAL_GLOBAL and nombre:
            fuzzy_rows.append(_fila_match(row, tm_data.loc[nombre], score * 100, "fuzzy_global"))
        else:
            no_match_rows.append(_fila_sin_match(row))

    merge_fuzzy = pd.DataFrame(fuzzy_rows)
    merge_sin_match = pd.DataFrame(no_match_rows)
    if not merge_fuzzy.empty:
        for metodo in ["exacto_apodo", "fuzzy_liga", "fuzzy_pais", "fuzzy_global"]:
            n = (merge_fuzzy["metodo_match"] == metodo).sum()
            if n:
                print(f"   {metodo:<14}: {n:>4} jugadores adicionales")

    partes = [con_match[MERGE_FINAL_COLS]]
    if not merge_fuzzy.empty:
        partes.append(merge_fuzzy[MERGE_FINAL_COLS])
    if not merge_sin_match.empty:
        partes.append(merge_sin_match[MERGE_FINAL_COLS])

    merge_final = pd.concat(partes, ignore_index=True)
    merge_final["fuzzy_score"] = pd.to_numeric(merge_final["fuzzy_score"], errors="coerce")
    sin_match_final = merge_final["tm_player_id"].isna().sum()
    print(f"   Sin match final: {sin_match_final:>3} jugadores conservados con TM nulo")
    return merge_final


def _fila_match(row: pd.Series, tm_row: pd.Series, score: float, metodo: str) -> dict:
    return {
        "player_id": row["player_id"],
        "player": row["player"],
        "country": row["country"],
        "nombre_norm": row["nombre_norm"],
        "tm_player_id": tm_row["tm_player_id"],
        "tm_name": tm_row["tm_name"],
        "date_of_birth": tm_row["date_of_birth"],
        "country_of_citizenship": tm_row["country_of_citizenship"],
        "sub_position": tm_row["sub_position"],
        "foot": tm_row["foot"],
        "height_in_cm": tm_row["height_in_cm"],
        "market_value_in_eur": tm_row["market_value_in_eur"],
        "fuzzy_score": round(score, 1),
        "metodo_match": metodo,
    }


def _fila_sin_match(row: pd.Series) -> dict:
    return {
        "player_id": row["player_id"],
        "player": row["player"],
        "country": row["country"],
        "nombre_norm": row["nombre_norm"],
        "tm_player_id": pd.NA,
        "tm_name": pd.NA,
        "date_of_birth": pd.NA,
        "country_of_citizenship": pd.NA,
        "sub_position": pd.NA,
        "foot": pd.NA,
        "height_in_cm": np.nan,
        "market_value_in_eur": np.nan,
        "fuzzy_score": np.nan,
        "metodo_match": pd.NA,
    }


def build_dim_valoracion_historica(
    dim_jugador: pd.DataFrame,
    tm_valuations: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye dim_valoracion a partir del tm_player_id que matching_jugadores()
    ya resolvio para cada jugador StatsBomb (dim_jugador["tm_player_id"]).

    No se hace un segundo matching por nombre: usar el mismo tm_player_id en
    toda la tabla evita que dim_jugador y dim_valoracion terminen apuntando a
    personas distintas de Transfermarkt para el mismo player_id.
    """
    val_cols = [
        "player_id",
        "tm_player_id",
        "date",
        "market_value_in_eur",
        "current_club_name",
        "player_club_domestic_competition_id",
    ]
    if dim_jugador.empty or tm_valuations.empty:
        return pd.DataFrame(columns=val_cols)

    vals = tm_valuations.copy()
    vals["date"] = pd.to_datetime(vals["date"], errors="coerce")
    vals["market_value_in_eur"] = pd.to_numeric(vals["market_value_in_eur"], errors="coerce")
    vals = vals[
        (vals["date"] >= FECHAS_INICIO)
        & (vals["date"] <= FECHAS_FIN)
        & vals["market_value_in_eur"].notna()
    ].copy()
    if vals.empty:
        return pd.DataFrame(columns=val_cols)

    vals = vals.sort_values(
        ["tm_player_id", "market_value_in_eur", "date"],
        ascending=[True, False, True],
        na_position="last",
    )
    base = dim_jugador[["player_id", "tm_player_id"]].dropna(subset=["tm_player_id"]).drop_duplicates("player_id")
    base = base.copy()
    base["tm_player_id"] = pd.to_numeric(base["tm_player_id"], errors="coerce").astype("Int64")

    dim_valoracion = base.merge(vals, on="tm_player_id", how="inner")
    for col in val_cols:
        if col not in dim_valoracion.columns:
            dim_valoracion[col] = pd.NA
    dim_valoracion = dim_valoracion[val_cols].copy()
    dim_valoracion["date"] = pd.to_datetime(dim_valoracion["date"], errors="coerce")
    dim_valoracion["date"] = dim_valoracion["date"].fillna(pd.Timestamp("2016-01-01"))
    dim_valoracion = dim_valoracion.sort_values(["player_id", "date"]).reset_index(drop=True)

    n_jug = dim_valoracion["player_id"].nunique()
    print(f"   OK dim_valoracion: {len(dim_valoracion):,} registros / {n_jug:,} jugadores "
          f"(via tm_player_id de matching_jugadores)")

    print("   Check valoraciones historicas:")
    for check in ["Gerard Pique", "Ivan Rakitic", "Jordi Alba"]:
        check_norm = normalizar(check)
        sb_row = dim_jugador[dim_jugador["player"].apply(normalizar) == check_norm]
        if sb_row.empty:
            print(f"      {check} -> sin jugador StatsBomb encontrado")
            continue
        pid = sb_row.iloc[0]["player_id"]
        val_row = dim_valoracion[dim_valoracion["player_id"] == pid]
        if val_row.empty:
            tm_pid = sb_row.iloc[0].get("tm_player_id")
            print(f"      {check} -> sin valoracion (tm_player_id={tm_pid})")
            continue
        value = val_row["market_value_in_eur"].max()
        print(f"      {check} -> pico {value:,.0f} EUR ({len(val_row)} registros)")
        if value < 5_000_000:
            print(f"      Aviso: {check} quedo por debajo de 5M; revisar match.")

    return dim_valoracion


def build_dimensiones(
    all_matches: list[dict],
    all_lineups: list[dict],
    merge_final: pd.DataFrame,
    tm_valuations: pd.DataFrame,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dim_partido = pd.DataFrame(all_matches).drop_duplicates("match_id")
    if not dim_partido.empty:
        dim_partido["match_date"] = pd.to_datetime(dim_partido["match_date"], errors="coerce")
    save(dim_partido, "dim_partido", output_dir)

    lineups_df = pd.DataFrame(all_lineups)
    if lineups_df.empty:
        base_pos = pd.DataFrame(columns=["player_id", "posicion_habitual", "equipo_habitual"])
    else:
        base_pos = (
            lineups_df.groupby("player_id")["team"]
            .agg(lambda x: modo_segura(x, "Desconocido"))
            .reset_index()
            .rename(columns={"team": "equipo_habitual"})
        )
        base_pos["posicion_habitual"] = "Desconocida"

    pos_habitual = compute_posicion_habitual(output_dir)
    if not pos_habitual.empty:
        base_pos = (
            base_pos.drop(columns=["posicion_habitual"], errors="ignore")
            .merge(pos_habitual, on="player_id", how="outer")
        )

    dim_jugador = (
        merge_final.drop(columns=["nombre_norm"], errors="ignore")
        .merge(base_pos, on="player_id", how="left")
        .sort_values(["player_id", "fuzzy_score"], ascending=[True, False], na_position="last")
        .drop_duplicates(subset="player_id", keep="first")
        .reset_index(drop=True)
    )
    for col in ["height_in_cm", "market_value_in_eur"]:
        if col in dim_jugador.columns:
            dim_jugador[col] = pd.to_numeric(dim_jugador[col], errors="coerce")
    dim_jugador["posicion_habitual"] = dim_jugador["posicion_habitual"].fillna("Desconocida")
    dim_jugador["equipo_habitual"] = dim_jugador["equipo_habitual"].fillna("Desconocido")
    save(dim_jugador, "dim_jugador", output_dir)

    dim_valoracion = build_dim_valoracion_historica(dim_jugador, tm_valuations)
    save(dim_valoracion, "dim_valoracion", output_dir)

    return dim_partido, dim_jugador, dim_valoracion


def build_calendario(output_dir: Path) -> pd.DataFrame:
    fechas = pd.date_range(start=FECHAS_INICIO, end=FECHAS_FIN, freq="D")
    dim_calendario = pd.DataFrame({"Date": fechas})
    dim_calendario["Anio"] = dim_calendario["Date"].dt.year
    dim_calendario["Mes_Numero"] = dim_calendario["Date"].dt.month
    dim_calendario["Mes_Nombre"] = dim_calendario["Date"].dt.strftime("%B")
    dim_calendario["Trimestre"] = "Q" + dim_calendario["Date"].dt.quarter.astype(str)
    dim_calendario["Semana_Anio"] = dim_calendario["Date"].dt.isocalendar().week.astype(int)
    dim_calendario["Dia_Semana_Numero"] = dim_calendario["Date"].dt.dayofweek + 1
    dim_calendario["Dia_Semana_Nombre"] = dim_calendario["Date"].dt.strftime("%A")
    dim_calendario["Es_Fin_De_Semana"] = (dim_calendario["Dia_Semana_Numero"] >= 6).astype(int)
    dim_calendario["Temporada"] = dim_calendario["Date"].apply(
        lambda fecha: f"{fecha.year}/{fecha.year + 1}"
        if fecha.month >= 7
        else f"{fecha.year - 1}/{fecha.year}"
    )
    dim_calendario["Date"] = dim_calendario["Date"].dt.strftime("%Y-%m-%d")
    save(dim_calendario, "dim_calendario", output_dir)
    return dim_calendario


def build_fact_minutes(output_dir: Path) -> pd.DataFrame:
    """
    Construye fact_minutes con minutos jugados por jugador x partido.

    Logica:
    - Titulares (Starting XI): minuto_entrada = 0.
    - Sustitutos que entran: minuto_entrada = minuto del evento Substitution
      donde substitution_replacement_id == player_id.
    - Jugadores que salen por sustitucion: minuto_salida = minuto del evento.
    - Jugadores que no salen: minuto_salida = ultimo minuto registrado en Half End
      del partido (tipicamente 45 o 90 + descuento).
    - minutos_jugados = minuto_salida - minuto_entrada (minimo 1 para evitar ceros).

    Columnas output:
      match_id, player_id, team_id, minuto_entrada, minuto_salida,
      minutos_jugados, es_titular, fue_sustituido
    """
    raw_xi_path   = output_dir / "_starting_xi_raw.csv"
    raw_sub_path  = output_dir / "_substitution_raw.csv"
    raw_half_path = output_dir / "_half_end_raw.csv"

    # Leer archivos raw; tolerar que no existan (primer run parcial)
    df_xi   = read_csv_safe(raw_xi_path)   if raw_xi_path.exists()   else pd.DataFrame()
    df_sub  = read_csv_safe(raw_sub_path)  if raw_sub_path.exists()  else pd.DataFrame()
    df_half = read_csv_safe(raw_half_path) if raw_half_path.exists() else pd.DataFrame()

    if df_xi.empty:
        print("   Aviso: no hay datos de Starting XI; fact_minutes sera vacia.")
        empty = pd.DataFrame(columns=["match_id", "player_id", "team_id",
                                       "minuto_entrada", "minuto_salida",
                                       "minutos_jugados", "es_titular", "fue_sustituido"])
        save(empty, "fact_minutes", output_dir)
        return empty

    # --- Normalizar tipos ---
    for df in [df_xi, df_sub, df_half]:
        for col in ["match_id", "player_id", "team_id", "minute", "period"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Ultimo minuto por partido (Half End, periodo 2 o el mayor disponible) ---
    if not df_half.empty and "minute" in df_half.columns:
        ultimo_minuto = (
            df_half.groupby("match_id")["minute"]
            .max()
            .reset_index()
            .rename(columns={"minute": "minuto_fin_partido"})
        )
    else:
        ultimo_minuto = pd.DataFrame(columns=["match_id", "minuto_fin_partido"])

    # --- Titulares ---
    # Un evento Starting XI por equipo; el player_id es el del tecnico/equipo.
    # Los jugadores titulares se identifican desde los lineups (all_lineups).
    # Sin embargo, en StatsBomb el evento Starting XI no tiene player_id individual,
    # sino tactics.lineup con la lista. Para simplificar y ser robustos,
    # tomamos como titulares a los jugadores que aparecen en los lineups
    # del partido pero NO aparecen como sustitutos que entran.
    # Esto es correcto: lineup = plantel convocado; el que entra de cero es titular.

    # Jugadores que ENTRAN como sustitutos: identificados por substitution_replacement_id
    reemplazos_col = None
    for col in ["substitution_replacement_id", "substitution_replacement"]:
        if not df_sub.empty and col in df_sub.columns:
            reemplazos_col = col
            break

    entradas_sub = pd.DataFrame()
    salidas_sub = pd.DataFrame()

    if not df_sub.empty and reemplazos_col is not None:
        # El player_id del evento es quien SALE
        salidas_sub = df_sub[["match_id", "player_id", "team_id", "minute"]].copy()
        salidas_sub = salidas_sub.rename(columns={"player_id": "player_id_sale", "minute": "minuto_salida"})

        # El reemplazante es quien ENTRA
        df_sub["replacement_id"] = pd.to_numeric(
            df_sub[reemplazos_col].astype(str).str.extract(r"(\d+)", expand=False),
            errors="coerce"
        )
        entradas_sub = df_sub[df_sub["replacement_id"].notna()][["match_id", "replacement_id", "team_id", "minute"]].copy()
        entradas_sub = entradas_sub.rename(columns={"replacement_id": "player_id", "minute": "minuto_entrada"})
        entradas_sub["es_titular"] = 0
        entradas_sub["fue_sustituido"] = 0  # el sustituto podria a su vez salir

    # Necesitamos los lineups para saber los titulares.
    # Los leemos desde dim_jugador o desde fact_minutes parciales.
    # La forma mas directa: leer el CSV de dim_partido o los raw de XI.
    # Usamos df_xi que tiene match_id y team_id al nivel de partido;
    # para los player_ids de titulares leemos el _lineup_raw si existe,
    # sino recurrimos a inferencia: todos los jugadores con eventos en el partido
    # que no son sustitutos entrantes = titulares.

    # Estrategia robusta: leer fact_pass u otro fact masivo para obtener
    # (match_id, player_id, team_id) unicos, luego descontar sustitutos entrantes.
    fact_ref_path = output_dir / "fact_pass.csv"
    if not fact_ref_path.exists():
        fact_ref_path = output_dir / "fact_shot.csv"
    if not fact_ref_path.exists():
        fact_ref_path = output_dir / "fact_pressure.csv"

    if fact_ref_path.exists():
        df_ref = read_csv_safe(fact_ref_path, usecols=["match_id", "player_id", "team_id"])
        df_ref["match_id"] = pd.to_numeric(df_ref["match_id"], errors="coerce")
        df_ref["player_id"] = pd.to_numeric(df_ref["player_id"], errors="coerce")
        df_ref["team_id"] = pd.to_numeric(df_ref["team_id"], errors="coerce")
        jugadores_por_partido = df_ref.dropna(subset=["match_id", "player_id"]).drop_duplicates(
            subset=["match_id", "player_id"]
        )
    else:
        jugadores_por_partido = pd.DataFrame(columns=["match_id", "player_id", "team_id"])

    # Titulares = jugadores del partido que NO son sustitutos entrantes
    subs_entrantes_ids = set()
    if not entradas_sub.empty:
        subs_entrantes_ids = set(
            zip(entradas_sub["match_id"].astype(int), entradas_sub["player_id"].astype(int))
        )

    if not jugadores_por_partido.empty:
        mask_titular = jugadores_por_partido.apply(
            lambda r: (int(r["match_id"]), int(r["player_id"])) not in subs_entrantes_ids
            if pd.notna(r["match_id"]) and pd.notna(r["player_id"]) else False,
            axis=1
        )
        titulares = jugadores_por_partido[mask_titular].copy()
        titulares["minuto_entrada"] = 0
        titulares["es_titular"] = 1
    else:
        titulares = pd.DataFrame(columns=["match_id", "player_id", "team_id", "minuto_entrada", "es_titular"])

    # --- Combinar titulares + sustitutos entrantes ---
    frames = [titulares[["match_id", "player_id", "team_id", "minuto_entrada", "es_titular"]]]
    if not entradas_sub.empty:
        entradas_sub["es_titular"] = 0
        frames.append(entradas_sub[["match_id", "player_id", "team_id", "minuto_entrada", "es_titular"]])

    df_minutes = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["match_id", "player_id"])

    # --- Agregar minuto de salida ---
    # 1. Los que salen por sustitucion
    if not salidas_sub.empty:
        df_minutes = df_minutes.merge(
            salidas_sub[["match_id", "player_id_sale", "minuto_salida"]].rename(
                columns={"player_id_sale": "player_id"}
            ),
            on=["match_id", "player_id"],
            how="left",
        )
        df_minutes["fue_sustituido"] = df_minutes["minuto_salida"].notna().astype(int)
    else:
        df_minutes["minuto_salida"] = np.nan
        df_minutes["fue_sustituido"] = 0

    # 2. Los que no salieron: usar ultimo minuto del partido
    df_minutes = df_minutes.merge(ultimo_minuto, on="match_id", how="left")
    df_minutes["minuto_fin_partido"] = df_minutes["minuto_fin_partido"].fillna(90)
    df_minutes["minuto_salida"] = df_minutes["minuto_salida"].fillna(df_minutes["minuto_fin_partido"])

    # --- Calcular minutos jugados ---
    df_minutes["minuto_entrada"] = pd.to_numeric(df_minutes["minuto_entrada"], errors="coerce").fillna(0)
    df_minutes["minuto_salida"] = pd.to_numeric(df_minutes["minuto_salida"], errors="coerce")
    df_minutes["minutos_jugados"] = (df_minutes["minuto_salida"] - df_minutes["minuto_entrada"]).clip(lower=1).round(0).astype("Int64")

    # --- Limpiar y exportar ---
    df_minutes = df_minutes[["match_id", "player_id", "team_id",
                              "minuto_entrada", "minuto_salida",
                              "minutos_jugados", "es_titular", "fue_sustituido"]].copy()
    df_minutes = df_minutes.dropna(subset=["player_id", "match_id"])
    df_minutes["match_id"]  = df_minutes["match_id"].astype("Int64")
    df_minutes["player_id"] = df_minutes["player_id"].astype("Int64")
    df_minutes["team_id"]   = df_minutes["team_id"].astype("Int64")

    save(df_minutes, "fact_minutes", output_dir)

    # Eliminar archivos temporales raw
    for tmp in [raw_xi_path, raw_sub_path, raw_half_path]:
        if tmp.exists():
            tmp.unlink()

    return df_minutes


# Columnas clave a chequear por tabla en el reporte de conformidad.
FACT_COLUMNAS_CLAVE = {
    "fact_shot": ["player_id", "match_id", "shot_statsbomb_xg", "location_x"],
    "fact_pass": ["player_id", "match_id", "es_pase_completo", "pass_end_x"],
    "fact_carry": ["player_id", "match_id", "carry_distancia"],
    "fact_duel": ["player_id", "match_id", "es_duelo_ganado", "location_x"],
    "fact_dribble": ["player_id", "match_id", "es_dribble_exitoso", "location_x"],
    "fact_pressure": ["player_id", "match_id", "location_x"],
    "fact_interception": ["player_id", "match_id", "es_intercepcion_exitosa"],
    "fact_ball_receipt": ["player_id", "match_id", "es_recepcion_exitosa"],
    "fact_minutes": ["player_id", "match_id", "minutos_jugados"],
    "dim_jugador": ["player_id", "tm_player_id", "sub_position", "market_value_in_eur"],
}


def _tabla_rangos_html(serie: pd.Series, bins: list[tuple[float, float, str]], color: str) -> str:
    s = pd.to_numeric(serie, errors="coerce").dropna()
    total = len(s)
    filas = ""
    for lo, hi, label in bins:
        if hi is None:
            n = (s >= lo).sum()
        else:
            n = ((s >= lo) & (s < hi)).sum()
        pct = (n / total * 100) if total else 0
        ancho = max(1, round(pct))
        filas += f"""<tr><td>{esc_html(label)}</td><td>{n:,}</td>
        <td>{pct:.1f}%</td>
        <td><div class="bar" style="width:{ancho}%;background:{color}"></div></td></tr>"""
    return f"""<table class="tbl"><thead><tr style="background:{color};color:white">
    <th>Rango</th><th>N</th><th>%</th><th></th>
    </tr></thead><tbody>{filas}</tbody></table>"""


def generar_reporte_conformidad(
    output_dir: Path,
    dim_jugador: pd.DataFrame,
    conteo_total: int,
    temporadas: list[str],
    t_inicio: float,
) -> None:
    color = "#2196F3"
    tiempo_total = time.time() - t_inicio
    fecha_ejecucion = time.strftime("%Y-%m-%d %H:%M:%S")
    alertas: list[tuple[str, str]] = []

    # --- Seccion 1: resumen de ejecucion ---
    dim_partido = read_csv_safe(output_dir / "dim_partido.csv")
    partidos_totales = len(dim_partido)
    temporadas_li = "".join(f"<li>{esc_html(t)}</li>" for t in temporadas)
    seccion1 = f"""
    <div class="two-cols">
      <table class="tbl"><thead><tr style="background:{color};color:white"><th>Metrica</th><th>Valor</th></tr></thead>
        <tbody>
          <tr><td>Partidos totales</td><td>{partidos_totales:,}</td></tr>
          <tr><td>Eventos totales</td><td>{conteo_total:,}</td></tr>
          <tr><td>Fecha y hora de ejecucion</td><td>{fecha_ejecucion}</td></tr>
          <tr><td>Tiempo total</td><td>{tiempo_total:.1f} s</td></tr>
        </tbody></table>
      <div><strong>Temporadas procesadas</strong><ul>{temporadas_li}</ul></div>
    </div>"""

    # --- Seccion 2: cobertura del matching StatsBomb-Transfermarkt ---
    total_jug = len(dim_jugador)
    fuzzy_score = pd.to_numeric(dim_jugador.get("fuzzy_score", pd.Series(dtype=float)), errors="coerce")
    tiene_tm = dim_jugador.get("tm_player_id", pd.Series(dtype="object")).notna()
    n_exacto = int(((fuzzy_score == 100) & tiene_tm).sum())
    n_sin_match = int((~tiene_tm).sum())
    n_fuzzy = int(total_jug - n_exacto - n_sin_match)
    pct_sin_match = (n_sin_match / total_jug * 100) if total_jug else 0

    if pct_sin_match > 20:
        alertas.append(("naranja", f"{pct_sin_match:.1f}% de jugadores sin match con Transfermarkt (umbral: 20%)."))

    bins_fuzzy = [
        (0, 60, "< 60"),
        (60, 70, "60 - 70"),
        (70, 80, "70 - 80"),
        (80, 90, "80 - 90"),
        (90, 100, "90 - 100"),
        (100, None, "100 (exacto)"),
    ]
    histo_fuzzy = _tabla_rangos_html(fuzzy_score, bins_fuzzy, color)

    seccion2 = f"""
    <table class="tbl"><thead><tr style="background:{color};color:white">
      <th>Tipo de match</th><th>N</th><th>%</th>
    </tr></thead><tbody>
      <tr><td>Exacto</td><td>{n_exacto:,}</td><td>{(n_exacto / total_jug * 100) if total_jug else 0:.1f}%</td></tr>
      <tr><td>Fuzzy</td><td>{n_fuzzy:,}</td><td>{(n_fuzzy / total_jug * 100) if total_jug else 0:.1f}%</td></tr>
      <tr><td>Sin match</td><td>{n_sin_match:,}</td><td>{pct_sin_match:.1f}%</td></tr>
      <tr><td><strong>Total</strong></td><td><strong>{total_jug:,}</strong></td><td>100.0%</td></tr>
    </tbody></table>
    <h4>Distribucion de fuzzy_score</h4>
    {histo_fuzzy}"""

    # --- Seccion 3: calidad por tabla de hechos ---
    filas_seccion3 = ""
    for nombre, cols_clave in FACT_COLUMNAS_CLAVE.items():
        df = dim_jugador if nombre == "dim_jugador" else read_csv_safe(output_dir / f"{nombre}.csv")
        n_filas = len(df)
        if n_filas == 0:
            alertas.append(("rojo", f"{nombre} tiene 0 filas."))

        rango_match = "-"
        if "match_id" in df.columns and n_filas:
            mids = pd.to_numeric(df["match_id"], errors="coerce").dropna()
            if len(mids):
                rango_match = f"{int(mids.min())} - {int(mids.max())}"

        nulos_partes = []
        for col in cols_clave:
            if col not in df.columns:
                nulos_partes.append(f"{esc_html(col)}: ausente")
                alertas.append(("rojo", f"{nombre}.{col}: columna ausente."))
                continue
            pct_null = (df[col].isna().mean() * 100) if n_filas else 100.0
            nulos_partes.append(f"{esc_html(col)}: {pct_null:.1f}%")
            if pct_null > 5:
                alertas.append(("rojo", f"{nombre}.{col}: {pct_null:.1f}% de nulos (umbral: 5%)."))
            elif pct_null >= 2:
                alertas.append(("amarillo", f"{nombre}.{col}: {pct_null:.1f}% de nulos (rango 2-5%)."))

        filas_seccion3 += f"""<tr><td><code>{esc_html(nombre)}</code></td>
        <td>{n_filas:,}</td><td>{rango_match}</td><td>{'<br>'.join(nulos_partes)}</td></tr>"""

    seccion3 = f"""<table class="tbl"><thead><tr style="background:{color};color:white">
    <th>Tabla</th><th>Filas</th><th>Rango match_id</th><th>% Nulos columnas clave</th>
    </tr></thead><tbody>{filas_seccion3}</tbody></table>"""

    # --- Seccion 4: distribucion de minutos jugados ---
    fact_minutes = read_csv_safe(output_dir / "fact_minutes.csv")
    minutos = pd.to_numeric(fact_minutes.get("minutos_jugados", pd.Series(dtype=float)), errors="coerce").dropna()
    bins_minutos = [
        (0, 15, "0 - 15"),
        (15, 30, "15 - 30"),
        (30, 45, "30 - 45"),
        (45, 60, "45 - 60"),
        (60, 75, "60 - 75"),
        (75, 90, "75 - 90"),
        (90, None, "90+"),
    ]
    histo_minutos = _tabla_rangos_html(minutos, bins_minutos, color)

    n_jug_minutos = 0
    n_sobre_450 = 0
    pct_sobre_450 = 0.0
    if "player_id" in fact_minutes.columns and "minutos_jugados" in fact_minutes.columns:
        minutos_por_jugador = (
            fact_minutes.assign(minutos_jugados=pd.to_numeric(fact_minutes["minutos_jugados"], errors="coerce"))
            .groupby("player_id")["minutos_jugados"]
            .sum()
        )
        n_jug_minutos = len(minutos_por_jugador)
        n_sobre_450 = int((minutos_por_jugador > 450).sum())
        pct_sobre_450 = (n_sobre_450 / n_jug_minutos * 100) if n_jug_minutos else 0

    seccion4 = f"""
    <h4>Distribucion de minutos_jugados (por jugador x partido)</h4>
    {histo_minutos}
    <table class="tbl" style="margin-top:14px"><thead><tr style="background:{color};color:white">
      <th>Metrica</th><th>Valor</th>
    </tr></thead><tbody>
      <tr><td>Jugadores que superan 450 min totales</td><td>{n_sobre_450:,} ({pct_sobre_450:.1f}% del universo)</td></tr>
    </tbody></table>"""

    # --- Seccion 5: alertas automaticas ---
    if not alertas:
        alertas_li = '<li class="verde">Verde: todo dentro de los umbrales.</li>'
    else:
        alertas_li = "".join(f'<li class="{nivel}">{nivel.capitalize()}: {esc_html(texto)}</li>' for nivel, texto in alertas)

    seccion5 = f"""<div class="card"><ul class="alertas">{alertas_li}</ul></div>"""

    html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>Reporte de conformidad - Pipeline v12</title>
<style>
  *{{box-sizing:border-box}} body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f5f7fa;color:#1f2937;line-height:1.55}}
  .header{{background:linear-gradient(135deg,#0D47A1,{color});color:white;padding:42px 36px}}
  .header h1{{margin:0 0 6px;font-size:2.0rem}}
  .container{{max-width:1100px;margin:0 auto;padding:34px 22px}} .section{{margin-bottom:42px}}
  .sec-title{{border-left:5px solid {color};padding-left:12px;color:#0D47A1;font-size:1.3rem;font-weight:700;margin-bottom:18px}}
  .card{{background:white;border:1px solid #e5e7eb;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
  .tbl{{width:100%;border-collapse:collapse;font-size:.88rem;background:white}} .tbl th,.tbl td{{padding:9px 12px;text-align:right;border-bottom:1px solid #e5e7eb}}
  .tbl th:first-child,.tbl td:first-child{{text-align:left}} .two-cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  .bar{{height:10px;border-radius:4px}}
  code{{background:#f5f7fa;padding:2px 5px;border-radius:4px;color:#0D47A1}}
  ul.alertas{{list-style:none;padding:0;margin:0}} ul.alertas li{{padding:8px 12px;margin:6px 0;border-radius:6px;font-weight:600}}
  .rojo{{background:#fde2e1;color:#b91c1c}} .naranja{{background:#fef0d8;color:#b45309}}
  .amarillo{{background:#fef9c3;color:#854d0e}} .verde{{background:#dcfce7;color:#15803d}}
  @media(max-width:760px){{.two-cols{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="header">
  <h1>Reporte de conformidad - Pipeline v12</h1>
  <p>Verificacion estructural del output para Power BI. No incluye analisis ni recomendaciones.</p>
</div>
<div class="container">
  <div class="section"><div class="sec-title">1. Resumen de ejecucion</div><div class="card">{seccion1}</div></div>
  <div class="section"><div class="sec-title">2. Cobertura del matching StatsBomb-Transfermarkt</div><div class="card">{seccion2}</div></div>
  <div class="section"><div class="sec-title">3. Calidad por tabla de hechos</div><div class="card" style="overflow-x:auto">{seccion3}</div></div>
  <div class="section"><div class="sec-title">4. Distribucion de minutos jugados</div><div class="card">{seccion4}</div></div>
  <div class="section"><div class="sec-title">5. Alertas automaticas</div>{seccion5}</div>
</div>
</body></html>"""

    (output_dir / "reporte_conformidad.html").write_text(html_out, encoding="utf-8")
    print(f"   OK reporte_conformidad.html generado en {tiempo_total:.1f}s")


def zip_output(output_dir: Path, zip_name: str) -> Path:
    base = output_dir.parent / zip_name
    zip_path = Path(shutil.make_archive(str(base), "zip", str(output_dir)))
    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline de scouting v12.")
    parser.add_argument("--repo-path", type=Path, default=Path("open-data/data"), help="Ruta a open-data/data de StatsBomb.")
    parser.add_argument("--tm-path", type=Path, default=Path("transfermarkt_data"), help="Ruta a CSVs de Transfermarkt.")
    parser.add_argument("--output-dir", type=Path, default=Path("scouting_v12_output"), help="Carpeta de salida.")
    parser.add_argument("--download-data", action="store_true", help="Descarga StatsBomb open-data y Transfermarkt via Kaggle.")
    parser.add_argument(
        "--skip-report", action="store_true",
        help="Genera solo CSV, sin reporte HTML de conformidad."
    )
    parser.add_argument("--zip", action="store_true", help="Comprime la salida en scouting_v12_final.zip.")
    return parser.parse_args()


def main() -> None:
    t_inicio = time.time()
    args = parse_args()
    if args.download_data:
        download_data(Path("."), args.tm_path)

    if not args.repo_path.exists():
        raise FileNotFoundError(
            f"No existe {args.repo_path}. Clona StatsBomb open-data o usa --download-data."
        )
    if not (args.tm_path / "players.csv").exists() or not (args.tm_path / "player_valuations.csv").exists():
        raise FileNotFoundError(
            f"No encuentro players.csv/player_valuations.csv en {args.tm_path}. Usa --download-data o ajusta --tm-path."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  PIPELINE DE SCOUTING V12")
    print("=" * 60)

    print("\n-- BLOQUE 1: Carga Transfermarkt")
    tm_players_match, liga_player_ids, tm_valuations = cargar_transfermarkt(args.tm_path)
    print(f"   OK tm_players_match: {len(tm_players_match):,} nombres unicos")
    print(f"   OK tm_valuations {FECHAS_INICIO} a {FECHAS_FIN}: {len(tm_valuations):,} registros")

    print("\n-- BLOQUE 2: Procesamiento incremental")
    all_matches, all_lineups, conteo_total = procesar_partidos(args.repo_path, args.output_dir)
    print(f"\n   OK total eventos procesados: {conteo_total:,}")

    print("\n-- BLOQUE 3: Matching StatsBomb - Transfermarkt")
    pos_habitual = compute_posicion_habitual(args.output_dir)
    merge_final = matching_jugadores(all_lineups, tm_players_match, liga_player_ids, pos_habitual)

    print("\n-- BLOQUE 4: Dimensiones")
    _, dim_jugador, _ = build_dimensiones(
        all_matches, all_lineups, merge_final, tm_valuations, args.output_dir
    )

    print("\n-- BLOQUE 5: Dimension calendario")
    build_calendario(args.output_dir)

    print("\n-- BLOQUE 6: Minutos jugados por partido")
    build_fact_minutes(args.output_dir)

    if not args.skip_report:
        generar_reporte_conformidad(
            args.output_dir,
            dim_jugador,
            conteo_total,
            [obj["nombre"] for obj in OBJETIVOS],
            t_inicio,
        )

    csvs = list(args.output_dir.glob("*.csv"))
    htmls = list(args.output_dir.glob("*.html"))
    total_mb = sum(f.stat().st_size for f in csvs + htmls) / 1024 / 1024

    print("\n" + "=" * 60)
    print("  PIPELINE V12 COMPLETADO")
    print("=" * 60)
    print(f"\n  {len(csvs)} archivos CSV en ./{args.output_dir}/")
    print(f"  {len(htmls)} reportes HTML en ./{args.output_dir}/")
    print(f"  Tamano total: {total_mb:.1f} MB")

    if args.zip:
        zip_path = zip_output(args.output_dir, "scouting_v12_final")
        print(f"  ZIP generado: {zip_path}")

    print(
        """
  ARCHIVOS ESPERADOS:
  - dim_jugador, dim_partido, dim_valoracion, dim_calendario
  - fact_shot, fact_pass, fact_duel, fact_dribble, fact_carry
  - fact_pressure, fact_interception
  - fact_ball_receipt, fact_miscontrol
  - fact_minutes  [minutos jugados por jugador x partido]
  - 1 reporte HTML de conformidad

  POWER BI:
  - Importar CSV con separador ';' y decimal ','
  - dim_calendario[Date] -> dim_partido[match_date]
  - dim_jugador[player_id] -> fact_*[player_id]
  - dim_partido[match_id] -> fact_*[match_id]
  - fact_minutes[match_id] -> dim_partido[match_id]
  - fact_minutes[player_id] -> dim_jugador[player_id]
"""
    )


if __name__ == "__main__":
    main()
