"""
========================================================
  PIPELINE DE SCOUTING V9
  StatsBomb open-data + Transfermarkt Kaggle

  Entorno: La Liga | 2014/15, 2015/16, 2016/17

  Output:
    - 19 CSV: 4 dimensiones + 15 tablas fact
    - 4 reportes HTML de EDA por perfil

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
========================================================
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


OBJETIVOS = [
    {"competition_id": 11, "season_id": 26, "nombre": "La Liga 2014/15"},
    {"competition_id": 11, "season_id": 27, "nombre": "La Liga 2015/16"},
    {"competition_id": 11, "season_id": 2, "nombre": "La Liga 2016/17"},
]

EVENTOS_OBJETIVO = {
    "Pass",
    "Shot",
    "Duel",
    "Dribble",
    "Carry",
    "Pressure",
    "Interception",
    "Clearance",
    "Ball Receipt*",
    "Goal Keeper",
    "Foul Committed",
    "Foul Won",
    "Miscontrol",
    "Block",
    # v9: eventos de tiempo de juego para fact_minutes
    "Starting XI",
    "Substitution",
    "Half End",
}

FECHAS_INICIO = "2014-07-01"
FECHAS_FIN = "2017-06-30"
FUZZY_UMBRAL = 85

CONTEXTO = [
    "match_id",
    "player_id",
    "player",
    "team_id",
    "team",
    "position",
    "period",
    "minute",
    "second",
    "timestamp",
    "location",
    "under_pressure",
    "counterpress",
    "play_pattern",
    "possession_team_id",
    "possession_team",
]

COLS_EVENTO = {
    "Pass": [
        "pass_length",
        "pass_angle",
        "pass_body_part",
        "pass_height",
        "pass_technique",
        "pass_type",
        "pass_outcome",
        "pass_end_location",
        "pass_recipient_id",
        "pass_recipient",
        "pass_shot_assist",
        "pass_goal_assist",
        "pass_cross",
        "pass_switch",
        "pass_through_ball",
        "pass_aerial_won",
        "pass_miscommunication",
        "pass_deflected",
        "pass_inswinging",
        "pass_outswinging",
        "pass_straight",
        "pass_cut_back",
        "pass_no_touch",
        "duration",
    ],
    "Shot": [
        "shot_statsbomb_xg",
        "shot_outcome",
        "shot_technique",
        "shot_body_part",
        "shot_type",
        "shot_end_location",
        "shot_first_time",
        "shot_aerial_won",
        "shot_deflected",
        "shot_key_pass_id",
        "duration",
    ],
    "Duel": ["duel_type", "duel_outcome", "duration"],
    "Dribble": ["dribble_outcome", "dribble_nutmeg", "dribble_no_touch", "duration"],
    "Carry": ["carry_end_location", "duration"],
    "Pressure": ["duration"],
    "Interception": ["interception_outcome", "duration"],
    "Clearance": [
        "clearance_body_part",
        "clearance_aerial_won",
        "clearance_head",
        "clearance_left_foot",
        "clearance_right_foot",
        "duration",
    ],
    "Ball Receipt*": ["ball_receipt_outcome"],
    "Goal Keeper": [
        "goalkeeper_type",
        "goalkeeper_outcome",
        "goalkeeper_technique",
        "goalkeeper_body_part",
        "goalkeeper_position",
        "goalkeeper_end_location",
        "duration",
    ],
    "Foul Committed": [
        "foul_committed_type",
        "foul_committed_card",
        "foul_committed_advantage",
        "duration",
    ],
    "Foul Won": ["foul_won_advantage", "foul_won_defensive", "duration"],
    "Miscontrol": ["miscontrol_aerial_won", "duration"],
    "Block": ["block_deflection", "duration"],
    # v9: columnas para calculo de minutos jugados
    "Starting XI": ["tactics"],
    "Substitution": ["substitution_outcome", "substitution_replacement"],
    "Half End": [],
}

NOMBRE_ARCHIVO = {
    "Pass": "fact_pass",
    "Shot": "fact_shot",
    "Duel": "fact_duel",
    "Dribble": "fact_dribble",
    "Carry": "fact_carry",
    "Pressure": "fact_pressure",
    "Interception": "fact_interception",
    "Clearance": "fact_clearance",
    "Ball Receipt*": "fact_ball_receipt",
    "Goal Keeper": "fact_goalkeeper",
    "Foul Committed": "fact_foul_committed",
    "Foul Won": "fact_foul_won",
    "Miscontrol": "fact_miscontrol",
    "Block": "fact_block",
    # v9: no se routean a CSV incremental; se procesan en build_fact_minutes
    "Starting XI": "_starting_xi_raw",
    "Substitution": "_substitution_raw",
    "Half End": "_half_end_raw",
}

BOOL_FLAG_COLS = {
    "under_pressure",
    "counterpress",
    "pass_shot_assist",
    "pass_goal_assist",
    "pass_cross",
    "pass_switch",
    "pass_through_ball",
    "pass_aerial_won",
    "pass_miscommunication",
    "pass_deflected",
    "pass_inswinging",
    "pass_outswinging",
    "pass_straight",
    "pass_cut_back",
    "pass_no_touch",
    "shot_first_time",
    "shot_aerial_won",
    "shot_deflected",
    "dribble_nutmeg",
    "dribble_no_touch",
    "clearance_aerial_won",
    "clearance_head",
    "clearance_left_foot",
    "clearance_right_foot",
    "foul_committed_advantage",
    "foul_won_advantage",
    "foul_won_defensive",
    "miscontrol_aerial_won",
    "block_deflection",
}

COLORES = {
    "delantero": {
        "primario": "#E63946",
        "secundario": "#FF6B6B",
        "fondo": "#FFF5F5",
        "acento": "#C1121F",
    },
    "mediocampista": {
        "primario": "#2196F3",
        "secundario": "#64B5F6",
        "fondo": "#F0F8FF",
        "acento": "#0D47A1",
    },
    "defensor": {
        "primario": "#2E7D32",
        "secundario": "#66BB6A",
        "fondo": "#F1F8F1",
        "acento": "#1B5E20",
    },
    "lateral": {
        "primario": "#7B2D8B",
        "secundario": "#CE93D8",
        "fondo": "#F9F0FF",
        "acento": "#4A148C",
    },
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
    extra = COLS_EVENTO.get(tipo, [])
    cols = safe_cols(subset, CONTEXTO + extra)
    subset = subset[cols].copy()

    if tipo == "Pass":
        if "pass_outcome" in subset.columns:
            subset["es_pase_completo"] = subset["pass_outcome"].isna().astype(int)
        if "pass_goal_assist" in subset.columns:
            subset["es_asistencia_gol"] = (subset["pass_goal_assist"] == True).astype(int)
        if "pass_shot_assist" in subset.columns:
            subset["es_asistencia_tiro"] = (subset["pass_shot_assist"] == True).astype(int)
        subset = split_location(subset, "location", "location")
        subset = split_location(subset, "pass_end_location", "pass_end")

    elif tipo == "Shot":
        if "shot_outcome" in subset.columns:
            subset["es_gol"] = (subset["shot_outcome"] == "Goal").astype(int)
            subset["es_al_arco"] = subset["shot_outcome"].isin(["Goal", "Saved"]).astype(int)
        subset = split_location(subset, "location", "location")
        subset = split_location(subset, "shot_end_location", "shot_end")

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

    elif tipo == "Goal Keeper":
        subset = split_location(subset, "location", "location")
        subset = split_location(subset, "goalkeeper_end_location", "gk_end")

    else:
        subset = split_location(subset, "location", "location")

    if tipo == "Duel" and "duel_outcome" in subset.columns:
        subset["es_duelo_ganado"] = subset["duel_outcome"].isin(
            {"Won", "Success", "Success In Play", "Success Out"}
        ).astype(int)
    elif tipo == "Dribble" and "dribble_outcome" in subset.columns:
        subset["es_dribble_exitoso"] = (subset["dribble_outcome"] == "Complete").astype(int)
    elif tipo == "Interception" and "interception_outcome" in subset.columns:
        subset["es_intercepcion_exitosa"] = subset["interception_outcome"].isin(
            {"Won", "Success", "Success In Play", "Success Out"}
        ).astype(int)
    elif tipo == "Ball Receipt*" and "ball_receipt_outcome" in subset.columns:
        subset["es_recepcion_exitosa"] = subset["ball_receipt_outcome"].isna().astype(int)

    subset = flags_to_int(subset, safe_cols(subset, list(BOOL_FLAG_COLS)))
    return subset


def cargar_transfermarkt(tm_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tm_players = pd.read_csv(tm_path / "players.csv", low_memory=False)
    tm_players = tm_players[
        [
            "player_id",
            "name",
            "date_of_birth",
            "country_of_citizenship",
            "sub_position",
            "foot",
            "height_in_cm",
            "market_value_in_eur",
            "highest_market_value_in_eur",
        ]
    ].rename(columns={"player_id": "tm_player_id", "name": "tm_name"})

    for col in ["height_in_cm", "market_value_in_eur", "highest_market_value_in_eur"]:
        tm_players[col] = pd.to_numeric(tm_players[col], errors="coerce")
    tm_players["tm_player_id"] = pd.to_numeric(tm_players["tm_player_id"], errors="coerce").astype(
        "Int64"
    )
    tm_players["nombre_norm"] = tm_players["tm_name"].apply(normalizar)

    tm_players_match = (
        tm_players.sort_values(
            ["nombre_norm", "market_value_in_eur", "highest_market_value_in_eur"],
            ascending=[True, False, False],
            na_position="last",
        )
        .drop_duplicates("nombre_norm", keep="first")
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
    return tm_players, tm_players_match, tm_valuations


def procesar_partidos(repo_path: Path, output_dir: Path) -> tuple[list[dict], list[dict], int]:
    for nombre in NOMBRE_ARCHIVO.values():
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


def matching_jugadores(
    all_lineups: list[dict], tm_players_match: pd.DataFrame
) -> pd.DataFrame:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        install_if_missing("rapidfuzz")
        from rapidfuzz import fuzz

    lineups_df = pd.DataFrame(all_lineups)
    if lineups_df.empty:
        return pd.DataFrame(
            columns=[
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
                "highest_market_value_in_eur",
                "fuzzy_score",
            ]
        )

    sb_players = (
        lineups_df.groupby("player_id")
        .agg(player=("player", "first"), country=("country", "first"))
        .reset_index()
    )
    sb_players["nombre_norm"] = sb_players["player"].apply(normalizar)

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
        "highest_market_value_in_eur",
    ]
    merge_exacto = sb_players.merge(tm_players_match[tm_cols], on="nombre_norm", how="left")
    merge_exacto["fuzzy_score"] = np.where(merge_exacto["tm_player_id"].notna(), 100, np.nan)

    con_match = merge_exacto[merge_exacto["tm_player_id"].notna()].copy()
    sin_match = merge_exacto[merge_exacto["tm_player_id"].isna()][
        ["player_id", "player", "nombre_norm", "country"]
    ].copy()
    print(f"   Match exacto: {len(con_match):>4} jugadores")
    print(f"   Sin match:    {len(sin_match):>4} jugadores - aplicando fuzzy")

    tm_nombres = tm_players_match["nombre_norm"].tolist()
    tm_data = tm_players_match.set_index("nombre_norm")
    fuzzy_rows = []
    no_match_rows = []

    for _, row in sin_match.iterrows():
        nombre_sb = row["nombre_norm"]
        mejor_score = 0
        mejor_nombre = None
        if nombre_sb:
            for tm_nombre in tm_nombres:
                score = fuzz.token_set_ratio(nombre_sb, tm_nombre)
                if score > mejor_score:
                    mejor_score = score
                    mejor_nombre = tm_nombre

        if mejor_score >= FUZZY_UMBRAL and mejor_nombre:
            tm_row = tm_data.loc[mejor_nombre]
            fuzzy_rows.append(
                {
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
                    "highest_market_value_in_eur": tm_row["highest_market_value_in_eur"],
                    "fuzzy_score": mejor_score,
                }
            )
        else:
            no_match_rows.append(
                {
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
                    "highest_market_value_in_eur": np.nan,
                    "fuzzy_score": np.nan,
                }
            )

    merge_fuzzy = pd.DataFrame(fuzzy_rows)
    merge_sin_match = pd.DataFrame(no_match_rows)
    print(f"   Match fuzzy:  {len(merge_fuzzy):>4} jugadores adicionales")

    cols_merge = [
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
        "highest_market_value_in_eur",
        "fuzzy_score",
    ]
    partes = [con_match[cols_merge]]
    if not merge_fuzzy.empty:
        partes.append(merge_fuzzy[cols_merge])
    if not merge_sin_match.empty:
        partes.append(merge_sin_match[cols_merge])

    merge_final = pd.concat(partes, ignore_index=True)
    merge_final["fuzzy_score"] = pd.to_numeric(merge_final["fuzzy_score"], errors="coerce")
    sin_match_final = merge_final["tm_player_id"].isna().sum()
    print(f"   Sin match final: {sin_match_final:>3} jugadores conservados con TM nulo")
    return merge_final


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
            lineups_df.groupby("player_id")
            .agg(
                equipo_habitual=("team", lambda x: modo_segura(x, "Desconocido")),
            )
            .reset_index()
        )
        base_pos["posicion_habitual"] = "Desconocida"

    fact_pass = read_csv_safe(
        output_dir / "fact_pass.csv",
        usecols=["player_id", "position", "team"],
        nrows=500000,
        on_bad_lines="skip",
    )
    if not fact_pass.empty and {"player_id", "position", "team"}.issubset(fact_pass.columns):
        pos_habitual = (
            fact_pass.groupby("player_id")["position"]
            .agg(lambda x: modo_segura(x, "Desconocida"))
            .reset_index()
            .rename(columns={"position": "posicion_habitual"})
        )
        equipo_habitual = (
            fact_pass.groupby("player_id")["team"]
            .agg(lambda x: modo_segura(x, "Desconocido"))
            .reset_index()
            .rename(columns={"team": "equipo_habitual"})
        )
        base_pos = (
            base_pos.drop(columns=["posicion_habitual", "equipo_habitual"], errors="ignore")
            .merge(pos_habitual, on="player_id", how="outer")
            .merge(equipo_habitual, on="player_id", how="outer")
        )

    dim_jugador = (
        merge_final.drop(columns=["nombre_norm"], errors="ignore")
        .merge(base_pos, on="player_id", how="left")
        .sort_values(["player_id", "fuzzy_score"], ascending=[True, False], na_position="last")
        .drop_duplicates(subset="player_id", keep="first")
        .reset_index(drop=True)
    )
    for col in ["height_in_cm", "market_value_in_eur", "highest_market_value_in_eur"]:
        if col in dim_jugador.columns:
            dim_jugador[col] = pd.to_numeric(dim_jugador[col], errors="coerce")
    dim_jugador["posicion_habitual"] = dim_jugador["posicion_habitual"].fillna("Desconocida")
    dim_jugador["equipo_habitual"] = dim_jugador["equipo_habitual"].fillna("Desconocido")
    save(dim_jugador, "dim_jugador", output_dir)

    id_map = merge_final[merge_final["tm_player_id"].notna()][["player_id", "tm_player_id"]].copy()
    id_map["tm_player_id"] = pd.to_numeric(id_map["tm_player_id"], errors="coerce").astype("Int64")
    id_map = id_map.drop_duplicates()

    val_cols = [
        "player_id",
        "tm_player_id",
        "date",
        "market_value_in_eur",
        "current_club_name",
        "player_club_domestic_competition_id",
    ]
    dim_valoracion = tm_valuations.merge(id_map, on="tm_player_id", how="inner")
    for col in val_cols:
        if col not in dim_valoracion.columns:
            dim_valoracion[col] = pd.NA
    dim_valoracion = dim_valoracion[val_cols].sort_values(["player_id", "date"]).reset_index(drop=True)
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
    v9: Construye fact_minutes con minutos jugados por jugador x partido.

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


def setup_plotting():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        install_if_missing("matplotlib")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt


def calcular_iqr(serie: pd.Series) -> dict:
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    if len(serie) == 0:
        return {"Q1": 0, "Q3": 0, "IQR": 0, "lower": 0, "upper": 0, "n_outliers": 0, "pct_outliers": 0}
    q1 = serie.quantile(0.25)
    q3 = serie.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = serie[(serie < lower) | (serie > upper)]
    return {
        "Q1": q1,
        "Q3": q3,
        "IQR": iqr,
        "lower": lower,
        "upper": upper,
        "n_outliers": len(outliers),
        "pct_outliers": round(len(outliers) / len(serie) * 100, 2),
    }


def fig_to_b64(fig, plt) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded


def grafico_scatter_valoracion(df, metrica, label_metrica, color, fondo, titulo, plt) -> str:
    """Compatibilidad legacy: el scatter ahora es interactivo en el HTML."""
    return ""


def preparar_json_scatter(df: pd.DataFrame, cols_metricas: list[str], titulos_metricas: list[str]) -> str:
    """Genera el JSON embebido para el scatter interactivo v8.
    Incluye todas las metricas del perfil para que el selector JS pueda cambiar el eje X."""
    col_val = "valor_mercado_promedio"
    registros = []
    df_work = df.copy()
    for col in cols_metricas + [col_val]:
        if col in df_work.columns:
            df_work[col] = pd.to_numeric(df_work[col], errors="coerce")
    df_work = df_work[pd.to_numeric(df_work.get(col_val, pd.Series(dtype=float)), errors="coerce") > 0].copy()
    name_col = "player" if "player" in df_work.columns else (df_work.columns[0] if len(df_work.columns) > 0 else None)
    for _, row in df_work.iterrows():
        rec: dict = {"vm": round(float(row[col_val]) / 1e6, 3) if pd.notna(row.get(col_val)) else None}
        if name_col and pd.notna(row.get(name_col)):
            rec["n"] = str(row[name_col])
        for col in cols_metricas:
            if col in row.index and pd.notna(row[col]):
                rec[col] = round(float(row[col]), 2)
        if rec.get("vm") is not None:
            registros.append(rec)
    meta = [{"col": c, "label": str(t)} for c, t in zip(cols_metricas, titulos_metricas)]
    return json.dumps({"data": registros, "metricas": meta}, ensure_ascii=False)


def preparar_json_histo_box(df: pd.DataFrame, cols_metricas: list[str], titulos_metricas: list[str]) -> str:
    """Genera el JSON embebido para histogramas y boxplots interactivos v8."""
    registros = []
    df_work = df.copy()
    for col in cols_metricas:
        if col in df_work.columns:
            df_work[col] = pd.to_numeric(df_work[col], errors="coerce")

    for _, row in df_work.iterrows():
        rec: dict = {}
        for col in cols_metricas:
            if col in row.index and pd.notna(row[col]):
                rec[col] = round(float(row[col]), 2)
        if rec:
            registros.append(rec)

    meta = [{"col": c, "label": str(t)} for c, t in zip(cols_metricas, titulos_metricas)]
    return json.dumps({"data": registros, "metricas": meta}, ensure_ascii=False)


def grafico_boxplot_cuartiles(df, metrica, color, fondo, label_metrica, plt) -> str:
    if metrica not in df.columns or "valor_mercado_promedio" not in df.columns:
        return ""
    df_plot = df[
        pd.to_numeric(df[metrica], errors="coerce").notna()
        & pd.to_numeric(df["valor_mercado_promedio"], errors="coerce").notna()
        & (pd.to_numeric(df["valor_mercado_promedio"], errors="coerce") > 0)
    ].copy()
    if len(df_plot) < 20 or df_plot[metrica].nunique(dropna=True) < 4:
        return ""
    df_plot[metrica] = pd.to_numeric(df_plot[metrica], errors="coerce")
    try:
        df_plot["cuartil"] = pd.qcut(df_plot[metrica], q=4, duplicates="drop")
    except ValueError:
        return ""
    intervalos = list(df_plot["cuartil"].dropna().cat.categories)
    if len(intervalos) < 2:
        return ""
    labels = [f"Q{i + 1}" for i in range(len(intervalos))]
    grupos = [
        df_plot[df_plot["cuartil"] == intervalo]["valor_mercado_promedio"].values / 1e6
        for intervalo in intervalos
    ]

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    bp = ax.boxplot(grupos, patch_artist=True, labels=labels)
    for box in bp["boxes"]:
        box.set_facecolor(color)
        box.set_alpha(0.7)
    ax.set_xlabel(f"Cuartil de rendimiento - {label_metrica}")
    ax.set_ylabel("Valor de mercado (M EUR)")
    ax.set_title("El mercado precia esta metrica?", fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig_to_b64(fig, plt)


def grafico_hist_valoracion(serie_valores, color, fondo, plt) -> str:
    datos = pd.to_numeric(serie_valores, errors="coerce").dropna()
    datos = datos[datos > 0] / 1e6
    if len(datos) < 5:
        return ""
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    ax.hist(datos, bins=min(30, max(5, len(datos) // 2)), color=color, alpha=0.7, edgecolor="white", linewidth=0.5)
    ax.axvline(datos.mean(), color="#333333", linestyle="--", linewidth=1.5, label=f"Media: {datos.mean():.1f}M EUR")
    ax.axvline(datos.median(), color="#888888", linestyle=":", linewidth=1.5, label=f"Mediana: {datos.median():.1f}M EUR")
    ax.set_xlabel("Valor de mercado promedio (M EUR)")
    ax.set_ylabel("Jugadores")
    ax.set_title("Distribucion de valor de mercado del perfil", fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9, framealpha=0.7)
    plt.tight_layout()
    return fig_to_b64(fig, plt)


def tabla_stats_html(df, cols, titulos, color) -> str:
    filas = ""
    for col, titulo in zip(cols, titulos):
        if col not in df.columns:
            continue
        d = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(d) < 2:
            continue
        skew = d.skew()
        kurt = d.kurtosis()
        lbl = "Simetrica" if abs(skew) < 0.5 else ("Asim. +" if skew > 0 else "Asim. -")
        filas += f"""
        <tr><td><code>{esc_html(titulo)}</code></td><td>{len(d):,}</td>
        <td>{d.mean():.2f}</td><td>{d.median():.2f}</td><td>{d.std():.2f}</td>
        <td>{d.min():.2f}</td><td>{d.max():.2f}</td>
        <td>{skew:.2f} <em>({lbl})</em></td><td>{kurt:.2f}</td></tr>"""
    return f"""<table class="tbl"><thead><tr style="background:{color};color:white">
    <th>Variable</th><th>N</th><th>Media</th><th>Mediana</th><th>Desv.Est.</th>
    <th>Min.</th><th>Max.</th><th>Asimetria</th><th>Curtosis</th>
    </tr></thead><tbody>{filas}</tbody></table>"""


def tabla_iqr_html(df, cols, titulos, color) -> str:
    filas = ""
    for col, titulo in zip(cols, titulos):
        if col not in df.columns:
            continue
        r = calcular_iqr(df[col])
        sem = "rojo" if r["pct_outliers"] > 10 else ("amarillo" if r["pct_outliers"] > 5 else "verde")
        filas += f"""
        <tr><td><code>{esc_html(titulo)}</code></td><td>{r['Q1']:.2f}</td><td>{r['Q3']:.2f}</td>
        <td>{r['IQR']:.2f}</td><td>{r['lower']:.2f}</td><td>{r['upper']:.2f}</td>
        <td><strong>{r['n_outliers']:,}</strong></td><td>{r['pct_outliers']}% ({sem})</td></tr>"""
    return f"""<table class="tbl"><thead><tr style="background:{color};color:white">
    <th>Variable</th><th>Q1</th><th>Q3</th><th>IQR</th><th>Limite inf.</th>
    <th>Limite sup.</th><th>N outliers</th><th>% outliers</th>
    </tr></thead><tbody>{filas}</tbody></table>"""


def tabla_universo_html(df, color) -> str:
    n_jug = len(df)
    n_convm = (pd.to_numeric(df.get("valor_mercado_promedio", pd.Series(dtype=float)), errors="coerce") > 0).sum()
    valores = pd.to_numeric(df.get("valor_mercado_promedio", pd.Series(dtype=float)), errors="coerce")
    med_val = valores[valores > 0].median()
    pct_convm = (n_convm / n_jug * 100) if n_jug else 0
    med_val_txt = f"{med_val / 1e6:.1f} M EUR" if pd.notna(med_val) else "Sin datos"
    equipos = df.get("equipo_habitual", pd.Series(dtype=str)).value_counts().head(5)
    rows_eq = "".join(f"<tr><td>{esc_html(eq)}</td><td>{cnt}</td></tr>" for eq, cnt in equipos.items())
    return f"""
    <div class="two-cols">
      <table class="tbl"><thead><tr style="background:{color};color:white"><th>Metrica</th><th>Valor</th></tr></thead>
        <tbody><tr><td>Jugadores unicos</td><td><strong>{n_jug:,}</strong></td></tr>
        <tr><td>Con valor de mercado</td><td>{n_convm:,} ({pct_convm:.0f}%)</td></tr>
        <tr><td>Valor mediano del periodo</td><td>{med_val_txt}</td></tr></tbody></table>
      <table class="tbl"><thead><tr style="background:{color};color:white"><th>Equipo</th><th>Jugadores</th></tr></thead>
        <tbody>{rows_eq}</tbody></table>
    </div>"""


def generar_html_perfil(
    perfil,
    subtitulo,
    filosofia,
    df_analitico,
    cols_metricas,
    titulos_metricas,
    imgs_hist,
    img_box,
    img_hist_val,
    img_scatter,        # compatibilidad legacy, se usa json_scatter
    img_cuartiles,
    t_stats,
    t_iqr,
    t_universo,
    colores,
    hallazgos,
    json_scatter="{}",
    json_histo_box="{}",
) -> str:
    c = colores
    hist_val_block = (
        f"""<div class="chart-card"><h3>Distribucion de valor de mercado</h3><img src="data:image/png;base64,{img_hist_val}"/></div>"""
        if img_hist_val
        else ""
    )
    cuartiles_block = (
        f"""<div class="chart-card"><h3>Valor por cuartiles de rendimiento</h3><img src="data:image/png;base64,{img_cuartiles}"/></div>"""
        if img_cuartiles
        else ""
    )
    hallazgos_li = "".join(f"<li>{esc_html(h)}</li>" for h in hallazgos)

    # Tabla de umbrales percentiles
    umbral_rows = ""
    for col, tit in zip(cols_metricas, titulos_metricas):
        if col in df_analitico.columns:
            s = pd.to_numeric(df_analitico[col], errors="coerce").dropna()
            if len(s) > 4:
                p50 = s.quantile(0.50)
                p75 = s.quantile(0.75)
                p90 = s.quantile(0.90)
                cov = round(s[s > 0].count() / len(s) * 100, 1)
                alerta = "baja cobertura" if cov < 40 else ("ok" if cov > 70 else "media")
                umbral_rows += f"""<tr>
                  <td><code>{esc_html(tit)}</code></td>
                  <td style="text-align:right">{p50:.1f}</td>
                  <td style="text-align:right;font-weight:700;color:var(--a)">{p75:.1f}</td>
                  <td style="text-align:right">{p90:.1f}</td>
                  <td style="text-align:right">{cov}% {alerta}</td>
                </tr>"""
    umbral_table = f"""
    <table class="tbl">
      <thead><tr style="background:{c['primario']};color:white">
        <th>Metrica</th><th>P50</th><th>P75</th><th>P90</th><th>Cobertura</th>
      </tr></thead>
      <tbody>{umbral_rows}</tbody>
    </table>
    <p style="font-size:.82rem;color:#666;margin-top:8px">P75 = umbral sugerido para filtrar candidatos en Power BI. Cobertura = % de jugadores con valor &gt; 0 en esa metrica.</p>
    """ if umbral_rows else "<p>Sin datos suficientes.</p>"

    # Histograma + boxplot interactivos. El boxplot usa whiskers IQR y dibuja outliers.
    histo_box_widget = f"""
    <div class="chart-card span-2" style="padding:24px">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
        <h3 style="margin:0">Distribucion y outliers</h3>
        <label style="font-size:.88rem;color:#555">Metrica:
          <select id="sel-metrica-hb" style="margin-left:6px;padding:4px 8px;border:1px solid #ccc;border-radius:6px;font-size:.88rem"></select>
        </label>
        <span id="hb-summary" style="font-size:.82rem;color:#666"></span>
      </div>
      <canvas id="histo-canvas" height="300" style="width:100%;margin-bottom:22px"></canvas>
      <canvas id="box-canvas" height="210" style="width:100%"></canvas>
    </div>
    <script>
    (function(){{
      const RAW = {json_histo_box};
      if(!RAW.data || RAW.data.length < 2 || !RAW.metricas || !RAW.metricas.length) return;
      const DATA = RAW.data;
      const METRICAS = RAW.metricas;
      const COLOR = "{c['primario']}";
      const sel = document.getElementById('sel-metrica-hb');
      const summary = document.getElementById('hb-summary');
      METRICAS.forEach(function(m){{
        const o = document.createElement('option');
        o.value = m.col; o.textContent = m.label;
        sel.appendChild(o);
      }});

      const histoCanvas = document.getElementById('histo-canvas');
      const boxCanvas = document.getElementById('box-canvas');
      const histoCtx = histoCanvas.getContext('2d');
      const boxCtx = boxCanvas.getContext('2d');

      function hexToRgb(hex){{
        const r = parseInt(hex.slice(1,3),16);
        const g = parseInt(hex.slice(3,5),16);
        const b = parseInt(hex.slice(5,7),16);
        return r+','+g+','+b;
      }}

      function values(colKey){{
        return DATA.map(function(d){{return d[colKey];}}).filter(function(v){{return Number.isFinite(v);}});
      }}

      function quantile(sorted, q){{
        if(!sorted.length) return null;
        const pos = (sorted.length - 1) * q;
        const base = Math.floor(pos);
        const rest = pos - base;
        if(sorted[base + 1] !== undefined) return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
        return sorted[base];
      }}

      function stats(vals){{
        const sorted = [...vals].sort(function(a,b){{return a-b;}});
        const q1 = quantile(sorted, .25);
        const q2 = quantile(sorted, .50);
        const q3 = quantile(sorted, .75);
        const iqr = q3 - q1;
        const lowFence = q1 - 1.5 * iqr;
        const highFence = q3 + 1.5 * iqr;
        const inliers = sorted.filter(function(v){{return v >= lowFence && v <= highFence;}});
        const outliers = sorted.filter(function(v){{return v < lowFence || v > highFence;}});
        const mean = vals.reduce(function(a,b){{return a+b;}}, 0) / vals.length;
        return {{
          sorted: sorted,
          min: sorted[0],
          max: sorted[sorted.length - 1],
          q1: q1,
          q2: q2,
          q3: q3,
          iqr: iqr,
          lower: inliers.length ? inliers[0] : sorted[0],
          upper: inliers.length ? inliers[inliers.length - 1] : sorted[sorted.length - 1],
          outliers: outliers,
          mean: mean
        }};
      }}

      function clear(ctx, canvas, height){{
        const W = canvas.offsetWidth || canvas.clientWidth || 600;
        canvas.width = W; canvas.height = height;
        ctx.clearRect(0, 0, W, height);
        return W;
      }}

      function drawEmpty(ctx, text, y){{
        ctx.fillStyle = '#777';
        ctx.font = '14px Arial';
        ctx.textAlign = 'left';
        ctx.fillText(text, 40, y);
      }}

      function drawHistograma(colKey){{
        const W = clear(histoCtx, histoCanvas, 300);
        const vals = values(colKey);
        if(vals.length < 2){{ drawEmpty(histoCtx, 'Datos insuficientes.', 150); return; }}
        const st = stats(vals);
        const min = st.min, max = st.max;
        const range = max - min || 1;
        const bins = Math.max(5, Math.min(30, Math.ceil(Math.sqrt(vals.length))));
        const binSize = range / bins;
        const counts = Array(bins).fill(0);
        vals.forEach(function(v){{
          let idx = Math.floor((v - min) / binSize);
          if(idx >= bins) idx = bins - 1;
          counts[idx]++;
        }});

        const maxCount = Math.max.apply(null, counts) || 1;
        const pad = {{l:54,r:22,t:18,b:48}};
        const W2 = W - pad.l - pad.r, H2 = 300 - pad.t - pad.b;
        const rgb = hexToRgb(COLOR);
        const toX = function(v){{return pad.l + ((v - min) / range) * W2;}};

        histoCtx.strokeStyle = '#d1d5db'; histoCtx.lineWidth = 1;
        histoCtx.beginPath(); histoCtx.moveTo(pad.l, pad.t); histoCtx.lineTo(pad.l, pad.t + H2); histoCtx.lineTo(pad.l + W2, pad.t + H2); histoCtx.stroke();

        counts.forEach(function(cnt, i){{
          const h = (cnt / maxCount) * H2;
          const x = pad.l + (i / bins) * W2;
          const w = Math.max(1, W2 / bins - 2);
          histoCtx.fillStyle = 'rgba(' + rgb + ',0.68)';
          histoCtx.fillRect(x, pad.t + H2 - h, w, h);
        }});

        histoCtx.setLineDash([]);
        histoCtx.strokeStyle = '#333'; histoCtx.lineWidth = 1.6;
        histoCtx.beginPath(); histoCtx.moveTo(toX(st.mean), pad.t); histoCtx.lineTo(toX(st.mean), pad.t + H2); histoCtx.stroke();
        histoCtx.strokeStyle = '#777'; histoCtx.setLineDash([4,4]);
        histoCtx.beginPath(); histoCtx.moveTo(toX(st.q2), pad.t); histoCtx.lineTo(toX(st.q2), pad.t + H2); histoCtx.stroke();
        histoCtx.setLineDash([]);

        histoCtx.fillStyle = '#555'; histoCtx.font = '11px Arial'; histoCtx.textAlign = 'center';
        [0,.25,.5,.75,1].forEach(function(t){{
          const xv = min + t * range;
          histoCtx.fillText(xv.toFixed(1), toX(xv), pad.t + H2 + 17);
        }});
        histoCtx.fillText('Media ' + st.mean.toFixed(2), pad.l + W2 * .28, 286);
        histoCtx.fillText('Mediana ' + st.q2.toFixed(2), pad.l + W2 * .72, 286);
      }}

      function drawBoxplot(colKey){{
        const W = clear(boxCtx, boxCanvas, 210);
        const vals = values(colKey);
        if(vals.length < 2){{ drawEmpty(boxCtx, 'Datos insuficientes.', 105); return; }}
        const st = stats(vals);
        const scaleMin = Math.min(st.lower, st.min);
        const scaleMax = Math.max(st.upper, st.max);
        const range = scaleMax - scaleMin || 1;
        const pad = {{l:58,r:26,t:20,b:42}};
        const W2 = W - pad.l - pad.r, H2 = 210 - pad.t - pad.b;
        const toX = function(v){{return pad.l + ((v - scaleMin) / range) * W2;}};
        const y = pad.t + H2 / 2;
        const boxH = 54;
        const rgb = hexToRgb(COLOR);

        boxCtx.strokeStyle = '#d1d5db'; boxCtx.lineWidth = 1;
        boxCtx.beginPath(); boxCtx.moveTo(pad.l, y); boxCtx.lineTo(pad.l + W2, y); boxCtx.stroke();

        boxCtx.strokeStyle = '#777'; boxCtx.lineWidth = 1.5;
        boxCtx.beginPath(); boxCtx.moveTo(toX(st.lower), y); boxCtx.lineTo(toX(st.q1), y); boxCtx.moveTo(toX(st.q3), y); boxCtx.lineTo(toX(st.upper), y); boxCtx.stroke();
        boxCtx.beginPath(); boxCtx.moveTo(toX(st.lower), y - 22); boxCtx.lineTo(toX(st.lower), y + 22); boxCtx.moveTo(toX(st.upper), y - 22); boxCtx.lineTo(toX(st.upper), y + 22); boxCtx.stroke();

        boxCtx.fillStyle = 'rgba(' + rgb + ',0.48)';
        boxCtx.strokeStyle = '#333'; boxCtx.lineWidth = 2;
        boxCtx.fillRect(toX(st.q1), y - boxH / 2, Math.max(1, toX(st.q3) - toX(st.q1)), boxH);
        boxCtx.strokeRect(toX(st.q1), y - boxH / 2, Math.max(1, toX(st.q3) - toX(st.q1)), boxH);

        boxCtx.strokeStyle = '#111'; boxCtx.lineWidth = 2.5;
        boxCtx.beginPath(); boxCtx.moveTo(toX(st.q2), y - boxH / 2); boxCtx.lineTo(toX(st.q2), y + boxH / 2); boxCtx.stroke();

        boxCtx.fillStyle = '#b91c1c';
        st.outliers.slice(0, 80).forEach(function(v){{
          boxCtx.beginPath(); boxCtx.arc(toX(v), y, 3, 0, 2 * Math.PI); boxCtx.fill();
        }});

        boxCtx.fillStyle = '#555'; boxCtx.font = '11px Arial'; boxCtx.textAlign = 'center';
        [0,.25,.5,.75,1].forEach(function(t){{
          const xv = scaleMin + t * range;
          boxCtx.fillText(xv.toFixed(1), toX(xv), pad.t + H2 + 28);
        }});
        boxCtx.textAlign = 'left';
        boxCtx.fillText('Q1 ' + st.q1.toFixed(2) + ' | Q2 ' + st.q2.toFixed(2) + ' | Q3 ' + st.q3.toFixed(2) + ' | outliers ' + st.outliers.length, pad.l, 20);
        summary.textContent = 'N=' + vals.length + ' | outliers IQR=' + st.outliers.length;
      }}

      function drawAll(){{
        drawHistograma(sel.value);
        drawBoxplot(sel.value);
      }}

      sel.addEventListener('change', drawAll);
      drawAll();
      window.addEventListener('resize', drawAll);
    }})();
    </script>"""

    # Scatter interactivo JS
    scatter_interactivo = f"""
    <div class="chart-card span-2" style="padding:24px">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
        <h3 style="margin:0">Rendimiento vs valor de mercado</h3>
        <label style="font-size:.88rem;color:#555">Metrica eje X:
          <select id="sel-metrica" style="margin-left:6px;padding:4px 8px;border:1px solid #ccc;border-radius:6px;font-size:.88rem"></select>
        </label>
        <span id="scatter-r" style="font-size:.82rem;color:#888"></span>
      </div>
      <canvas id="scatter-canvas" height="380" style="width:100%;cursor:crosshair"></canvas>
      <div id="scatter-tooltip" style="position:fixed;background:rgba(30,30,30,.92);color:#fff;padding:7px 12px;border-radius:7px;font-size:.82rem;pointer-events:none;display:none;z-index:99;max-width:220px;line-height:1.5"></div>
    </div>
    <script>
    (function(){{
      const RAW = {json_scatter};
      if(!RAW.data || RAW.data.length < 5) return;
      const DATA = RAW.data;
      const METRICAS = RAW.metricas;
      const COLOR = "{c['primario']}";
      const sel = document.getElementById('sel-metrica');
      METRICAS.forEach(function(m,i){{
        const o = document.createElement('option');
        o.value = m.col; o.textContent = m.label;
        sel.appendChild(o);
      }});

      const canvas = document.getElementById('scatter-canvas');
      const tt = document.getElementById('scatter-tooltip');
      const ctx = canvas.getContext('2d');
      let currentPoints = [];

      function hexToRgb(hex){{
        const r = parseInt(hex.slice(1,3),16);
        const g = parseInt(hex.slice(3,5),16);
        const b = parseInt(hex.slice(5,7),16);
        return r+','+g+','+b;
      }}

      function linReg(xs,ys){{
        const n=xs.length; if(n<3) return null;
        const mx=xs.reduce((a,b)=>a+b,0)/n, my=ys.reduce((a,b)=>a+b,0)/n;
        let num=0,den=0;
        for(let i=0;i<n;i++){{num+=(xs[i]-mx)*(ys[i]-my);den+=(xs[i]-mx)**2;}}
        if(den===0) return null;
        const m=num/den, b=my-m*mx;
        const ss_res=ys.reduce((a,y,i)=>a+(y-(m*xs[i]+b))**2,0);
        const ss_tot=ys.reduce((a,y)=>a+(y-my)**2,0);
        const r2=ss_tot===0?0:1-ss_res/ss_tot;
        return {{m,b,r2}};
      }}

      function median(arr){{
        const s=[...arr].sort((a,b)=>a-b);
        const mid=Math.floor(s.length/2);
        return s.length%2===0?(s[mid-1]+s[mid])/2:s[mid];
      }}

      function draw(colKey){{
        const W=canvas.offsetWidth; canvas.width=W; canvas.height=380;
        const pts=DATA.filter(d=>d[colKey]!=null && d.vm!=null);
        if(pts.length<5){{ ctx.fillStyle='#999'; ctx.font='14px Arial'; ctx.fillText('Datos insuficientes para esta metrica.',40,200); return; }}
        const xs=pts.map(d=>d[colKey]), ys=pts.map(d=>d.vm);
        const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
        const pad={{l:60,r:24,t:20,b:50}};
        const W2=W-pad.l-pad.r, H2=380-pad.t-pad.b;
        const toX=v=>pad.l+(v-xmin)/(xmax-xmin||1)*W2;
        const toY=v=>pad.t+H2-(v-ymin)/(ymax-ymin||1)*H2;

        ctx.clearRect(0,0,W,380);

        // Lineas de mediana
        const mx=median(xs), my=median(ys);
        ctx.setLineDash([5,4]); ctx.strokeStyle='#cccccc'; ctx.lineWidth=1;
        ctx.beginPath(); ctx.moveTo(toX(mx),pad.t); ctx.lineTo(toX(mx),pad.t+H2); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(pad.l,toY(my)); ctx.lineTo(pad.l+W2,toY(my)); ctx.stroke();
        ctx.setLineDash([]);

        // Regresion
        const reg=linReg(xs,ys);
        if(reg){{
          ctx.strokeStyle='rgba('+hexToRgb(COLOR)+',.45)'; ctx.lineWidth=1.8;
          ctx.beginPath(); ctx.moveTo(toX(xmin),toY(reg.m*xmin+reg.b)); ctx.lineTo(toX(xmax),toY(reg.m*xmax+reg.b)); ctx.stroke();
          document.getElementById('scatter-r').textContent='R^2 = '+reg.r2.toFixed(3);
        }}

        // Ejes
        ctx.strokeStyle='#cccccc'; ctx.lineWidth=1; ctx.setLineDash([]);
        ctx.beginPath(); ctx.moveTo(pad.l,pad.t); ctx.lineTo(pad.l,pad.t+H2); ctx.lineTo(pad.l+W2,pad.t+H2); ctx.stroke();
        ctx.fillStyle='#555'; ctx.font='11px Arial'; ctx.textAlign='center';
        [0,.25,.5,.75,1].forEach(function(t){{
          const xv=xmin+t*(xmax-xmin), px=toX(xv);
          ctx.fillText(xv.toFixed(0),px,pad.t+H2+16);
        }});
        ctx.textAlign='right';
        [0,.25,.5,.75,1].forEach(function(t){{
          const yv=ymin+t*(ymax-ymin), py=toY(yv);
          ctx.fillText(yv.toFixed(1)+'M',pad.l-6,py+4);
        }});

        // Puntos
        currentPoints=[];
        pts.forEach(function(d){{
          const px=toX(d[colKey]), py=toY(d.vm);
          ctx.beginPath(); ctx.arc(px,py,5,0,2*Math.PI);
          ctx.fillStyle='rgba('+hexToRgb(COLOR)+',.55)';
          ctx.strokeStyle='rgba(255,255,255,.7)'; ctx.lineWidth=1;
          ctx.fill(); ctx.stroke();
          currentPoints.push({{px,py,d}});
        }});
      }}

      function getColLabel(colKey){{
        const m=METRICAS.find(function(x){{return x.col===colKey;}});
        return m?m.label:colKey;
      }}

      canvas.addEventListener('mousemove',function(e){{
        const rect=canvas.getBoundingClientRect();
        const mx=e.clientX-rect.left, my=e.clientY-rect.top;
        let closest=null, bestD=Infinity;
        currentPoints.forEach(function(p){{
          const d=Math.hypot(p.px-mx,p.py-my);
          if(d<bestD){{bestD=d;closest=p;}}
        }});
        if(closest && bestD<18){{
          const colKey=sel.value;
          tt.style.display='block';
          tt.style.left=(e.clientX+14)+'px'; tt.style.top=(e.clientY-10)+'px';
          const name=closest.d.n||'Jugador';
          tt.innerHTML='<strong>'+name+'</strong><br>'+getColLabel(colKey)+': '+closest.d[colKey]+'<br>Valor: '+closest.d.vm.toFixed(1)+' M EUR';
        }} else {{ tt.style.display='none'; }}
      }});
      canvas.addEventListener('mouseleave',function(){{tt.style.display='none';}});

      sel.addEventListener('change',function(){{draw(sel.value);}});
      draw(sel.value);
      window.addEventListener('resize',function(){{draw(sel.value);}});
    }})();
    </script>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>EDA v9 - {esc_html(perfil)}</title>
<style>
  :root{{--p:{c['primario']};--s:{c['secundario']};--f:{c['fondo']};--a:{c['acento']};--txt:#1f2937;--b:#e5e7eb;}}
  *{{box-sizing:border-box}} body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:var(--f);color:var(--txt);line-height:1.55}}
  .header{{background:linear-gradient(135deg,var(--a),var(--p),var(--s));color:white;padding:42px 36px}}
  .header h1{{margin:0 0 6px;font-size:2.2rem}} .header p{{max-width:980px}}
  .badge{{display:inline-block;margin:4px 6px 0 0;padding:5px 12px;border:1px solid rgba(255,255,255,.35);border-radius:999px;background:rgba(255,255,255,.16);font-size:.85rem}}
  .container{{max-width:1200px;margin:0 auto;padding:34px 22px}} .section{{margin-bottom:42px}}
  .sec-title{{border-left:5px solid var(--p);padding-left:12px;color:var(--a);font-size:1.35rem;font-weight:700;margin-bottom:18px}}
  .card,.chart-card{{background:white;border:1px solid var(--b);border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
  .charts-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}
  .span-2{{grid-column:span 2}} img{{max-width:100%;border-radius:6px}} .wide-img{{width:100%}}
  .tbl{{width:100%;border-collapse:collapse;font-size:.88rem}} .tbl th,.tbl td{{padding:9px 12px;text-align:right;border-bottom:1px solid var(--b)}}
  .tbl th:first-child,.tbl td:first-child{{text-align:left}} .two-cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  code{{background:var(--f);padding:2px 5px;border-radius:4px;color:var(--a)}} li{{margin:8px 0}}
  @media(max-width:760px){{.two-cols{{grid-template-columns:1fr}}.span-2{{grid-column:span 1}}.header h1{{font-size:1.7rem}}}}
</style>
</head>
<body>
<div class="header">
  <h1>EDA v9 - {esc_html(perfil)}</h1>
  <p>{esc_html(subtitulo)}</p>
  <p><em>{esc_html(filosofia)}</em></p>
  <span class="badge">{len(df_analitico):,} jugadores analizados</span>
  <span class="badge">{len(cols_metricas)} metricas</span>
  <span class="badge">La Liga 2014-2017</span>
  <span class="badge">Criterios para Power BI</span>
</div>
<div class="container">
  <div class="section">
    <div class="sec-title">1. Universo del perfil</div>
    <div class="card">{t_universo}</div>
  </div>
  <div class="section">
    <div class="sec-title">2. Umbrales por percentil</div>
    <div class="card">{umbral_table}</div>
  </div>
  <div class="section">
    <div class="sec-title">3. Estadisticas descriptivas</div>
    <div class="card" style="overflow-x:auto">{t_stats}</div>
  </div>
  <div class="section">
    <div class="sec-title">4. Outliers IQR - alerta de distorsion en rankings</div>
    <div class="card" style="overflow-x:auto">{t_iqr}</div>
  </div>
  <div class="section">
    <div class="sec-title">5. Distribuciones y boxplot IQR</div>
    <div class="charts-grid">{histo_box_widget}</div>
  </div>
  <div class="section">
    <div class="sec-title">6. Correlacion con valor de mercado</div>
    <div class="charts-grid">{hist_val_block}{cuartiles_block}{scatter_interactivo}</div>
  </div>
  <div class="section">
    <div class="sec-title">7. Criterios accionables para Power BI</div>
    <div class="card"><ul>{hallazgos_li}</ul></div>
  </div>
</div>
</body></html>"""


def valor_mercado_promedio(dim_valoracion: pd.DataFrame, player_ids) -> pd.DataFrame:
    if dim_valoracion.empty:
        return pd.DataFrame({"player_id": player_ids, "valor_mercado_promedio": np.nan})
    return (
        dim_valoracion[dim_valoracion["player_id"].isin(player_ids)]
        .groupby("player_id")["market_value_in_eur"]
        .mean()
        .reset_index()
        .rename(columns={"market_value_in_eur": "valor_mercado_promedio"})
    )


def generar_reportes_eda(output_dir: Path, dim_jugador: pd.DataFrame, dim_valoracion: pd.DataFrame) -> None:
    warnings.filterwarnings("ignore")
    plt = setup_plotting()
    dim_jugador = require_columns(
        dim_jugador.copy(),
        ["player_id", "posicion_habitual", "equipo_habitual", "market_value_in_eur"],
    )
    dim_jugador_slim = dim_jugador[
        ["player_id", "posicion_habitual", "equipo_habitual", "market_value_in_eur"]
    ].copy()

    def completar(df, cols):
        for col in cols:
            if col not in df.columns:
                df[col] = np.nan
        return df

    def escribir_reporte(nombre_archivo, perfil, subtitulo, filosofia, df, cols, tits, color_key, metrica_principal, label_principal, hallazgos):
        c = COLORES[color_key]
        img_hist_val = grafico_hist_valoracion(df["valor_mercado_promedio"], c["primario"], c["fondo"], plt)
        img_scatter = ""  # compatibilidad legacy; el scatter real es interactivo
        img_cuartiles = grafico_boxplot_cuartiles(df, metrica_principal, c["primario"], c["fondo"], label_principal, plt)
        json_scatter = preparar_json_scatter(df, cols, tits)
        json_histo_box = preparar_json_histo_box(df, cols, tits)
        html = generar_html_perfil(
            perfil,
            subtitulo,
            filosofia,
            df,
            cols,
            tits,
            [],
            "",
            img_hist_val,
            img_scatter,
            img_cuartiles,
            tabla_stats_html(df, cols, tits, c["primario"]),
            tabla_iqr_html(df, cols, tits, c["primario"]),
            tabla_universo_html(df, c["primario"]),
            c,
            hallazgos,
            json_scatter=json_scatter,
            json_histo_box=json_histo_box,
        )
        (output_dir / nombre_archivo).write_text(html, encoding="utf-8")
        print(f"   OK {nombre_archivo} - {len(df):,} jugadores")

    print("\n-- BLOQUE 6: EDA por perfil")

    df_shot = completar(read_csv_safe(output_dir / "fact_shot.csv", on_bad_lines="skip"), ["player_id", "shot_statsbomb_xg", "location_x", "shot_type"])
    df_shot = to_num(df_shot, ["player_id", "shot_statsbomb_xg", "location_x", "es_gol", "es_al_arco"])
    df_pres = completar(read_csv_safe(output_dir / "fact_pressure.csv", on_bad_lines="skip"), ["player_id", "location_x", "location_y"])
    df_pres = to_num(df_pres, ["player_id", "location_x", "location_y"])
    df_duel = completar(read_csv_safe(output_dir / "fact_duel.csv", on_bad_lines="skip"), ["player_id", "location_x", "location_y", "es_duelo_ganado"])
    df_duel = to_num(df_duel, ["player_id", "location_x", "location_y", "es_duelo_ganado"])
    df_recv = completar(read_csv_safe(output_dir / "fact_ball_receipt.csv", on_bad_lines="skip"), ["player_id", "location_x", "es_recepcion_exitosa"])
    df_recv = to_num(df_recv, ["player_id", "location_x", "es_recepcion_exitosa"])
    df_pass = completar(read_csv_safe(output_dir / "fact_pass.csv", on_bad_lines="skip"), ["player_id", "location_x", "location_y", "pass_end_x", "pass_end_y", "es_pase_completo", "under_pressure"])
    df_pass = to_num(df_pass, ["player_id", "location_x", "location_y", "pass_end_x", "pass_end_y", "es_pase_completo"])
    df_pass = to_bool(df_pass, ["under_pressure"])
    df_carry = completar(read_csv_safe(output_dir / "fact_carry.csv", on_bad_lines="skip"), ["player_id", "location_x", "location_y", "carry_end_x", "carry_end_y", "carry_distancia"])
    df_carry = to_num(df_carry, ["player_id", "location_x", "location_y", "carry_end_x", "carry_end_y", "carry_distancia"])
    df_misc = completar(read_csv_safe(output_dir / "fact_miscontrol.csv", on_bad_lines="skip"), ["player_id"])
    df_misc = to_num(df_misc, ["player_id"])
    df_int = completar(read_csv_safe(output_dir / "fact_interception.csv", on_bad_lines="skip"), ["player_id", "location_x", "es_intercepcion_exitosa"])
    df_int = to_num(df_int, ["player_id", "location_x", "es_intercepcion_exitosa"])
    df_clear = completar(read_csv_safe(output_dir / "fact_clearance.csv", on_bad_lines="skip"), ["player_id", "clearance_aerial_won"])
    df_clear = to_num(df_clear, ["player_id", "clearance_aerial_won"])
    df_drib = completar(read_csv_safe(output_dir / "fact_dribble.csv", on_bad_lines="skip"), ["player_id", "location_x", "es_dribble_exitoso"])
    df_drib = to_num(df_drib, ["player_id", "location_x", "es_dribble_exitoso"])

    posiciones_del = {"Center Forward", "Left Wing", "Right Wing", "Left Center Forward", "Right Center Forward", "Secondary Striker"}
    players_del = dim_jugador_slim[dim_jugador_slim["posicion_habitual"].isin(posiciones_del)]["player_id"].unique()
    xg_sp = df_shot[df_shot["player_id"].isin(players_del) & (df_shot.get("shot_type", serie_vacia(df_shot.index, "object")) != "Penalty")].groupby("player_id")["shot_statsbomb_xg"].sum().reset_index().rename(columns={"shot_statsbomb_xg": "xg_sin_penal"})
    presiones = df_pres[df_pres["player_id"].isin(players_del) & (df_pres["location_x"] > 70)].groupby("player_id").size().reset_index(name="presiones_ultimo_tercio")
    duelos_cr = df_duel[df_duel["player_id"].isin(players_del) & (df_duel["location_x"] > 60) & (df_duel["es_duelo_ganado"] == 1)].groupby("player_id").size().reset_index(name="duelos_campo_rival")
    recepciones = df_recv[df_recv["player_id"].isin(players_del) & (df_recv["location_x"] > 60)].groupby("player_id").size().reset_index(name="recepciones_campo_rival")
    dribbles = df_drib[df_drib["player_id"].isin(players_del) & (df_drib["location_x"] > 60) & (df_drib["es_dribble_exitoso"] == 1)].groupby("player_id").size().reset_index(name="dribbles_exitosos")
    df_del = dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_del)].merge(xg_sp, on="player_id", how="left").merge(presiones, on="player_id", how="left").merge(duelos_cr, on="player_id", how="left").merge(recepciones, on="player_id", how="left").merge(dribbles, on="player_id", how="left").merge(valor_mercado_promedio(dim_valoracion, players_del), on="player_id", how="left").fillna(0)
    cols_del = ["xg_sin_penal", "presiones_ultimo_tercio", "duelos_campo_rival", "recepciones_campo_rival", "dribbles_exitosos"]
    tits_del = ["xG sin penal", "Presiones ultimo tercio", "Duelos ganados campo rival", "Recepciones campo rival", "Dribbles exitosos"]
    escribir_reporte(
        "eda_v8_delanteros.html",
        "Delanteros",
        "9 falso cruyffista - presion, movilidad y xG sin penal.",
        "Atacantes que generan peligro, presionan alto y participan fuera del area.",
        df_del,
        cols_del,
        tits_del,
        "delantero",
        "xg_sin_penal",
        "xG sin penal",
        [
            f"Universo: {len(df_del)} delanteros. Umbral sugerido de xG: percentil 75 = {df_del['xg_sin_penal'].quantile(.75):.1f}.",
            f"Dribbles exitosos: percentil 75 = {df_del['dribbles_exitosos'].quantile(.75):.0f}; indicador de desequilibrio y movilidad en campo rival.",
            "Score sugerido en Power BI: percentil(xG) * 0.35 + percentil(presiones) * 0.25 + percentil(recepciones) * 0.20 + percentil(dribbles) * 0.20.",
        ],
    )

    posiciones_mid = {"Center Defensive Midfield", "Center Midfield", "Left Center Midfield", "Right Center Midfield", "Left Midfield", "Right Midfield", "Left Defensive Midfield", "Right Defensive Midfield", "Center Attacking Midfield"}
    players_mid = dim_jugador_slim[dim_jugador_slim["posicion_habitual"].isin(posiciones_mid)]["player_id"].unique()
    pases_prog = df_pass[df_pass["player_id"].isin(players_mid) & (df_pass["pass_end_x"] > df_pass["location_x"] + 8)].groupby("player_id").size().reset_index(name="pases_progresivos")
    total_pases = df_pass[df_pass["player_id"].isin(players_mid)].groupby("player_id").size().reset_index(name="total_pases")
    cond_prog = df_carry[df_carry["player_id"].isin(players_mid) & (df_carry["carry_end_x"] > df_carry["location_x"] + 5)].groupby("player_id").size().reset_index(name="conducciones_progresivas")
    acc_presion = df_pass[df_pass["player_id"].isin(players_mid) & (df_pass["under_pressure"] == 1) & (df_pass["es_pase_completo"] == 1)].groupby("player_id").size().reset_index(name="pases_exitosos_bajo_presion")
    perdidas = df_misc[df_misc["player_id"].isin(players_mid)].groupby("player_id").size().reset_index(name="perdidas_balon")
    df_mid = dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_mid)].merge(pases_prog, on="player_id", how="left").merge(total_pases, on="player_id", how="left").merge(cond_prog, on="player_id", how="left").merge(acc_presion, on="player_id", how="left").merge(perdidas, on="player_id", how="left").merge(valor_mercado_promedio(dim_valoracion, players_mid), on="player_id", how="left").fillna(0)
    df_mid["ratio_pases_prog"] = np.where(df_mid["total_pases"] > 0, df_mid["pases_progresivos"] / df_mid["total_pases"], 0)
    cols_mid = ["pases_progresivos", "ratio_pases_prog", "conducciones_progresivas", "pases_exitosos_bajo_presion", "perdidas_balon"]
    tits_mid = ["Pases progresivos", "Ratio pases progresivos", "Conducciones progresivas", "Pases exitosos bajo presion", "Perdidas de balon"]
    escribir_reporte(
        "eda_v8_mediocampistas.html",
        "Mediocampistas",
        "Entre lineas - progresion, presion y bajo error.",
        "Jugadores que aceleran el juego hacia adelante y resisten la presion.",
        df_mid,
        cols_mid,
        tits_mid,
        "mediocampista",
        "pases_progresivos",
        "Pases progresivos",
        [
            f"Universo: {len(df_mid)} mediocampistas. P75 pases progresivos = {df_mid['pases_progresivos'].quantile(.75):.0f}.",
            "En Power BI: filtrar jugadores con total_pases > 300 antes de rankear ratio_pases_prog.",
        ],
    )

    posiciones_def = {"Center Back", "Left Center Back", "Right Center Back"}
    players_def = dim_jugador_slim[dim_jugador_slim["posicion_habitual"].isin(posiciones_def)]["player_id"].unique()
    duelos_zona = df_duel[df_duel["player_id"].isin(players_def) & (df_duel["location_x"] > 40) & (df_duel["es_duelo_ganado"] == 1)].groupby("player_id").size().reset_index(name="duelos_zona_alta")
    intercep_cr = df_int[df_int["player_id"].isin(players_def) & (df_int["location_x"] > 60)].groupby("player_id").size().reset_index(name="intercepciones_campo_rival")
    pases_prog_def = df_pass[df_pass["player_id"].isin(players_def) & (df_pass["location_x"] < 40) & (df_pass["pass_end_x"] > df_pass["location_x"] + 15)].groupby("player_id").size().reset_index(name="pases_prog_desde_atras")
    # v8: mantiene el reemplazo de despejes_aereos por un proxy mas consistente con el perfil.
    # Proxy de "correccion a campo abierto": carries en zona media (x 35-65) con avance >= 8m.
    carrys_zona_media = df_carry[
        df_carry["player_id"].isin(players_def)
        & (df_carry["location_x"] >= 35) & (df_carry["location_x"] <= 65)
        & (df_carry["carry_end_x"] > df_carry["location_x"] + 8)
    ].groupby("player_id").size().reset_index(name="carrys_progresivos_zona_media")
    df_def = dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_def)].merge(duelos_zona, on="player_id", how="left").merge(intercep_cr, on="player_id", how="left").merge(pases_prog_def, on="player_id", how="left").merge(carrys_zona_media, on="player_id", how="left").merge(valor_mercado_promedio(dim_valoracion, players_def), on="player_id", how="left").fillna(0)
    cols_def = ["duelos_zona_alta", "intercepciones_campo_rival", "pases_prog_desde_atras", "carrys_progresivos_zona_media"]
    tits_def = ["Duelos ganados zona alta", "Intercepciones campo rival", "Pases progresivos desde atras", "Carrys progresivos zona media"]
    escribir_reporte(
        "eda_v8_defensores.html",
        "Defensores",
        "Libero moderno - zonas altas y salida limpia.",
        "Centrales que defienden lejos del arco, interceptan en avance y corrigen conduciendo.",
        df_def,
        cols_def,
        tits_def,
        "defensor",
        "duelos_zona_alta",
        "Duelos ganados zona alta",
        [
            f"Universo: {len(df_def)} defensores. P75 duelos zona alta = {df_def['duelos_zona_alta'].quantile(.75):.0f}.",
            f"P75 carrys_progresivos_zona_media = {df_def['carrys_progresivos_zona_media'].quantile(.75):.0f}; usar como umbral minimo en Power BI.",
            "Score sugerido en Power BI: score defensor = duelos_zona_alta*0.35 + intercepciones_campo_rival*0.30 + pases_prog_desde_atras*0.20 + carrys_progresivos_zona_media*0.15.",
            "v8: despejes_aereos se mantiene eliminado porque tiene datos insuficientes y contradice el perfil de central rapido buscado.",
        ],
    )

    posiciones_lat = {"Left Back", "Right Back", "Left Wing Back", "Right Wing Back", "Left Midfield", "Right Midfield", "Left Defensive Midfield", "Right Defensive Midfield"}
    players_lat = dim_jugador_slim[dim_jugador_slim["posicion_habitual"].isin(posiciones_lat)]["player_id"].unique()
    duelos_def = df_duel[df_duel["player_id"].isin(players_lat) & (df_duel["es_duelo_ganado"] == 1)].groupby("player_id").size().reset_index(name="duelos_defensivos_ganados")
    cond_centro = df_carry[df_carry["player_id"].isin(players_lat) & (((df_carry["location_y"] < 30) & (df_carry["carry_end_y"] > df_carry["location_y"])) | ((df_carry["location_y"] > 50) & (df_carry["carry_end_y"] < df_carry["location_y"])))].groupby("player_id").size().reset_index(name="conducciones_hacia_centro")
    pases_adentro = df_pass[df_pass["player_id"].isin(players_lat) & (((df_pass["location_y"] < 25) & (df_pass["pass_end_y"] > df_pass["location_y"] + 5)) | ((df_pass["location_y"] > 55) & (df_pass["pass_end_y"] < df_pass["location_y"] - 5)))].groupby("player_id").size().reset_index(name="pases_hacia_adentro")
    presiones_banda = df_pres[df_pres["player_id"].isin(players_lat) & ((df_pres["location_y"] < 20) | (df_pres["location_y"] > 60))].groupby("player_id").size().reset_index(name="presiones_en_banda")
    df_lat = dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_lat)].merge(duelos_def, on="player_id", how="left").merge(cond_centro, on="player_id", how="left").merge(pases_adentro, on="player_id", how="left").merge(presiones_banda, on="player_id", how="left").merge(valor_mercado_promedio(dim_valoracion, players_lat), on="player_id", how="left").fillna(0)
    cols_lat = ["duelos_defensivos_ganados", "conducciones_hacia_centro", "pases_hacia_adentro", "presiones_en_banda"]
    tits_lat = ["Duelos defensivos ganados", "Conducciones hacia el centro", "Pases hacia adentro", "Presiones en banda"]
    escribir_reporte(
        "eda_v8_laterales.html",
        "Laterales",
        "Lateral invertido - versatilidad y juego interior.",
        "Laterales firmes en el duelo y capaces de cerrarse hacia zonas interiores.",
        df_lat,
        cols_lat,
        tits_lat,
        "lateral",
        "conducciones_hacia_centro",
        "Conducciones hacia el centro",
        [
            f"Universo: {len(df_lat)} laterales. P75 duelos defensivos = {df_lat['duelos_defensivos_ganados'].quantile(.75):.0f}.",
            "Score sugerido en Power BI: score lateral = duelos_defensivos_ganados * 0.30 + conducciones_hacia_centro * 0.35 + pases_hacia_adentro * 0.35.",
        ],
    )


def zip_output(output_dir: Path, zip_name: str) -> Path:
    base = output_dir.parent / zip_name
    zip_path = Path(shutil.make_archive(str(base), "zip", str(output_dir)))
    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline de scouting v8.")
    parser.add_argument("--repo-path", type=Path, default=Path("open-data/data"), help="Ruta a open-data/data de StatsBomb.")
    parser.add_argument("--tm-path", type=Path, default=Path("transfermarkt_data"), help="Ruta a CSVs de Transfermarkt.")
    parser.add_argument("--output-dir", type=Path, default=Path("scouting_v8_output"), help="Carpeta de salida.")
    parser.add_argument("--download-data", action="store_true", help="Descarga StatsBomb open-data y Transfermarkt via Kaggle.")
    parser.add_argument("--skip-eda", action="store_true", help="Genera solo CSV, sin reportes HTML.")
    parser.add_argument("--zip", action="store_true", help="Comprime la salida en scouting_v8_final.zip.")
    return parser.parse_args()


def main() -> None:
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
    print("  PIPELINE DE SCOUTING V8")
    print("=" * 60)

    print("\n-- BLOQUE 1: Carga Transfermarkt")
    _, tm_players_match, tm_valuations = cargar_transfermarkt(args.tm_path)
    print(f"   OK tm_players_match: {len(tm_players_match):,} nombres unicos")
    print(f"   OK tm_valuations 2014-2017: {len(tm_valuations):,} registros")

    print("\n-- BLOQUE 2: Procesamiento incremental")
    all_matches, all_lineups, conteo_total = procesar_partidos(args.repo_path, args.output_dir)
    print(f"\n   OK total eventos procesados: {conteo_total:,}")

    print("\n-- BLOQUE 3: Matching StatsBomb - Transfermarkt")
    merge_final = matching_jugadores(all_lineups, tm_players_match)

    print("\n-- BLOQUE 4: Dimensiones")
    _, dim_jugador, dim_valoracion = build_dimensiones(
        all_matches, all_lineups, merge_final, tm_valuations, args.output_dir
    )

    print("\n-- BLOQUE 5: Dimension calendario")
    build_calendario(args.output_dir)

    print("\n-- BLOQUE 6: Minutos jugados por partido")
    build_fact_minutes(args.output_dir)

    if not args.skip_eda:
        generar_reportes_eda(args.output_dir, dim_jugador, dim_valoracion)

    csvs = list(args.output_dir.glob("*.csv"))
    htmls = list(args.output_dir.glob("*.html"))
    total_mb = sum(f.stat().st_size for f in csvs + htmls) / 1024 / 1024

    print("\n" + "=" * 60)
    print("  PIPELINE V9 COMPLETADO")
    print("=" * 60)
    print(f"\n  {len(csvs)} archivos CSV en ./{args.output_dir}/")
    print(f"  {len(htmls)} reportes HTML en ./{args.output_dir}/")
    print(f"  Tamano total: {total_mb:.1f} MB")

    if args.zip:
        zip_path = zip_output(args.output_dir, "scouting_v9_final")
        print(f"  ZIP generado: {zip_path}")

    print(
        """
  ARCHIVOS ESPERADOS:
  - dim_jugador, dim_partido, dim_valoracion, dim_calendario
  - fact_shot, fact_pass, fact_duel, fact_dribble, fact_carry
  - fact_pressure, fact_interception, fact_clearance
  - fact_ball_receipt, fact_goalkeeper, fact_foul_committed
  - fact_foul_won, fact_miscontrol, fact_block
  - fact_minutes  [v9: minutos jugados por jugador x partido]

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
