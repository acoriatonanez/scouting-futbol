"""
========================================================
  PIPELINE DE SCOUTING V5 - CORREGIDO
  StatsBomb open-data + Transfermarkt Kaggle

  Entorno: La Liga | 2014/15, 2015/16, 2016/17

  Output:
    - 18 CSV: 4 dimensiones + 14 tablas fact
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
========================================================
"""

from __future__ import annotations

import argparse
import base64
import csv
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
    truthy = {"true", "1", "yes", "si", "sí", "s"}
    for col in cols:
        if col in df.columns:
            df[col] = (
                df[col].astype(str).str.strip().str.lower().isin(truthy).astype(int)
            )
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

            for tipo, nombre_csv in NOMBRE_ARCHIVO.items():
                subset = df_match[df_match["type"] == tipo].copy()
                if subset.empty:
                    continue
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


def setup_plotting():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from scipy import stats
        return plt, stats
    except ImportError:
        install_if_missing("matplotlib")
        install_if_missing("scipy")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from scipy import stats
        return plt, stats


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


def grafico_histograma(df, col, color, titulo_col, fondo, plt, stats) -> str:
    if col not in df.columns:
        return ""
    datos = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(datos) < 5:
        return ""
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    ax.hist(datos, bins=min(40, max(5, len(datos) // 2)), color=color, alpha=0.7, edgecolor="white", linewidth=0.5)
    if len(datos) > 10 and datos.std() > 0:
        kde_x = np.linspace(datos.min(), datos.max(), 300)
        kde = stats.gaussian_kde(datos)
        ax2 = ax.twinx()
        ax2.plot(kde_x, kde(kde_x), color=color, linewidth=2.5, alpha=0.9)
        ax2.set_yticks([])
        ax2.set_facecolor(fondo)
    ax.axvline(datos.mean(), color="#333333", linestyle="--", linewidth=1.5, label=f"Media: {datos.mean():.2f}")
    ax.axvline(datos.median(), color="#888888", linestyle=":", linewidth=1.5, label=f"Mediana: {datos.median():.2f}")
    ax.set_title(f"Distribucion - {titulo_col}", fontsize=12, fontweight="bold")
    ax.set_xlabel(titulo_col)
    ax.set_ylabel("Frecuencia")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9, framealpha=0.7)
    plt.tight_layout()
    return fig_to_b64(fig, plt)


def grafico_boxplot_multiple(df, cols, titulos, color, fondo, plt) -> str:
    cols_ok = [c for c in cols if c in df.columns and pd.to_numeric(df[c], errors="coerce").dropna().shape[0] > 5]
    if not cols_ok:
        return ""
    titulos_ok = [titulos[cols.index(c)] for c in cols_ok]
    fig, axes = plt.subplots(1, len(cols_ok), figsize=(4 * len(cols_ok), 5))
    fig.patch.set_facecolor(fondo)
    if len(cols_ok) == 1:
        axes = [axes]
    for ax, col, titulo in zip(axes, cols_ok, titulos_ok):
        datos = pd.to_numeric(df[col], errors="coerce").dropna()
        ax.set_facecolor(fondo)
        bp = ax.boxplot(datos, patch_artist=True, medianprops=dict(color="#333333", linewidth=2.5))
        bp["boxes"][0].set_facecolor(color)
        bp["boxes"][0].set_alpha(0.65)
        ax.set_title(titulo, fontsize=10, fontweight="bold")
        ax.set_xticks([])
        ax.spines[["top", "right", "bottom"]].set_visible(False)
    fig.suptitle("Boxplots - dispersion y outliers", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return fig_to_b64(fig, plt)


def grafico_scatter_valoracion(df, metrica, label_metrica, color, fondo, titulo, plt) -> str:
    if metrica not in df.columns or "valor_mercado_promedio" not in df.columns:
        return ""
    df_plot = df[
        pd.to_numeric(df[metrica], errors="coerce").notna()
        & pd.to_numeric(df["valor_mercado_promedio"], errors="coerce").notna()
        & (pd.to_numeric(df["valor_mercado_promedio"], errors="coerce") > 0)
    ].copy()
    if len(df_plot) < 10:
        return ""
    df_plot[metrica] = pd.to_numeric(df_plot[metrica], errors="coerce")
    df_plot["valor_mercado_promedio"] = pd.to_numeric(df_plot["valor_mercado_promedio"], errors="coerce")

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    ax.scatter(df_plot[metrica], df_plot["valor_mercado_promedio"] / 1e6, color=color, alpha=0.45, s=35, edgecolors="white", linewidth=0.4)
    ax.axvline(df_plot[metrica].median(), color="#aaaaaa", linestyle="--", linewidth=1, alpha=0.7)
    ax.axhline((df_plot["valor_mercado_promedio"] / 1e6).median(), color="#aaaaaa", linestyle="--", linewidth=1, alpha=0.7)
    try:
        z = np.polyfit(df_plot[metrica], df_plot["valor_mercado_promedio"] / 1e6, 1)
        p = np.poly1d(z)
        x_line = np.linspace(df_plot[metrica].min(), df_plot[metrica].max(), 100)
        ax.plot(x_line, p(x_line), color=color, linewidth=1.5, alpha=0.5)
    except Exception:
        pass
    ax.set_xlabel(label_metrica)
    ax.set_ylabel("Valor de mercado promedio (M EUR)")
    ax.set_title(titulo, fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig_to_b64(fig, plt)


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
        <tr><td><code>{titulo}</code></td><td>{len(d):,}</td>
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
        <tr><td><code>{titulo}</code></td><td>{r['Q1']:.2f}</td><td>{r['Q3']:.2f}</td>
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
    rows_eq = "".join(f"<tr><td>{eq}</td><td>{cnt}</td></tr>" for eq, cnt in equipos.items())
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
    img_scatter,
    img_cuartiles,
    t_stats,
    t_iqr,
    t_universo,
    colores,
    hallazgos,
) -> str:
    c = colores
    grids = "".join(
        f"""<div class="chart-card"><h3>{tit}</h3><img src="data:image/png;base64,{img}"/></div>"""
        for tit, img in zip(titulos_metricas, imgs_hist)
        if img
    )
    if not grids:
        grids = "<p>No hay datos suficientes para graficar este perfil.</p>"
    img_box_block = (
        f"""<img src="data:image/png;base64,{img_box}" class="wide-img"/>"""
        if img_box
        else "<p>No hay datos suficientes para boxplots.</p>"
    )
    hist_val_block = (
        f"""<div class="chart-card"><h3>Distribucion de valor de mercado</h3><img src="data:image/png;base64,{img_hist_val}"/></div>"""
        if img_hist_val
        else ""
    )
    cuartiles_block = (
        f"""<div class="chart-card"><h3>Valor por cuartiles</h3><img src="data:image/png;base64,{img_cuartiles}"/></div>"""
        if img_cuartiles
        else ""
    )
    scatter_block = (
        f"""<div class="chart-card span-2"><h3>Rendimiento vs valor de mercado</h3><img src="data:image/png;base64,{img_scatter}"/></div>"""
        if img_scatter
        else ""
    )
    hallazgos_li = "".join(f"<li>{h}</li>" for h in hallazgos)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<title>EDA v5 - {perfil}</title>
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
  <h1>EDA v5 - {perfil}</h1>
  <p>{subtitulo}</p>
  <p><em>{filosofia}</em></p>
  <span class="badge">{len(df_analitico):,} jugadores analizados</span>
  <span class="badge">{len(cols_metricas)} metricas</span>
  <span class="badge">La Liga 2014-2017</span>
  <span class="badge">Transfermarkt</span>
</div>
<div class="container">
  <div class="section"><div class="sec-title">1. Universo del perfil</div><div class="card">{t_universo}</div></div>
  <div class="section"><div class="sec-title">2. Distribuciones</div><div class="charts-grid">{grids}</div></div>
  <div class="section"><div class="sec-title">3. Estadisticos descriptivos</div><div class="card" style="overflow-x:auto">{t_stats}</div></div>
  <div class="section"><div class="sec-title">4. Outliers IQR</div><div class="card" style="overflow-x:auto">{t_iqr}</div></div>
  <div class="section"><div class="sec-title">5. Boxplots</div><div class="card">{img_box_block}</div></div>
  <div class="section"><div class="sec-title">6. Valoraciones</div><div class="charts-grid">{hist_val_block}{cuartiles_block}{scatter_block}</div></div>
  <div class="section"><div class="sec-title">7. Hallazgos para DAX</div><div class="card"><ul>{hallazgos_li}</ul></div></div>
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
    plt, stats = setup_plotting()
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
        imgs_hist = [grafico_histograma(df, col, c["primario"], tit, c["fondo"], plt, stats) for col, tit in zip(cols, tits)]
        img_box = grafico_boxplot_multiple(df, cols, tits, c["primario"], c["fondo"], plt)
        img_hist_val = grafico_hist_valoracion(df["valor_mercado_promedio"], c["primario"], c["fondo"], plt)
        img_scatter = grafico_scatter_valoracion(df, metrica_principal, label_principal, c["primario"], c["fondo"], f"{label_principal} vs valor de mercado", plt)
        img_cuartiles = grafico_boxplot_cuartiles(df, metrica_principal, c["primario"], c["fondo"], label_principal, plt)
        html = generar_html_perfil(
            perfil,
            subtitulo,
            filosofia,
            df,
            cols,
            tits,
            imgs_hist,
            img_box,
            img_hist_val,
            img_scatter,
            img_cuartiles,
            tabla_stats_html(df, cols, tits, c["primario"]),
            tabla_iqr_html(df, cols, tits, c["primario"]),
            tabla_universo_html(df, c["primario"]),
            c,
            hallazgos,
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

    posiciones_del = {"Center Forward", "Left Wing", "Right Wing", "Left Center Forward", "Right Center Forward", "Secondary Striker"}
    players_del = dim_jugador_slim[dim_jugador_slim["posicion_habitual"].isin(posiciones_del)]["player_id"].unique()
    xg_sp = df_shot[df_shot["player_id"].isin(players_del) & (df_shot.get("shot_type", serie_vacia(df_shot.index, "object")) != "Penalty")].groupby("player_id")["shot_statsbomb_xg"].sum().reset_index().rename(columns={"shot_statsbomb_xg": "xg_sin_penal"})
    presiones = df_pres[df_pres["player_id"].isin(players_del) & (df_pres["location_x"] > 70)].groupby("player_id").size().reset_index(name="presiones_ultimo_tercio")
    duelos_cr = df_duel[df_duel["player_id"].isin(players_del) & (df_duel["location_x"] > 60) & (df_duel["es_duelo_ganado"] == 1)].groupby("player_id").size().reset_index(name="duelos_campo_rival")
    recepciones = df_recv[df_recv["player_id"].isin(players_del) & (df_recv["location_x"] > 60)].groupby("player_id").size().reset_index(name="recepciones_campo_rival")
    df_del = dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_del)].merge(xg_sp, on="player_id", how="left").merge(presiones, on="player_id", how="left").merge(duelos_cr, on="player_id", how="left").merge(recepciones, on="player_id", how="left").merge(valor_mercado_promedio(dim_valoracion, players_del), on="player_id", how="left").fillna(0)
    cols_del = ["xg_sin_penal", "presiones_ultimo_tercio", "duelos_campo_rival", "recepciones_campo_rival"]
    tits_del = ["xG sin penal", "Presiones ultimo tercio", "Duelos ganados campo rival", "Recepciones campo rival"]
    escribir_reporte(
        "eda_v5_delanteros.html",
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
            "Para DAX: score delantero = percentil(xG) * 0.4 + percentil(presiones) * 0.3 + percentil(recepciones) * 0.3.",
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
        "eda_v5_mediocampistas.html",
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
            "Para DAX: filtrar muestras con total_pases > 300 antes de rankear ratio_pases_prog.",
        ],
    )

    posiciones_def = {"Center Back", "Left Center Back", "Right Center Back"}
    players_def = dim_jugador_slim[dim_jugador_slim["posicion_habitual"].isin(posiciones_def)]["player_id"].unique()
    duelos_zona = df_duel[df_duel["player_id"].isin(players_def) & (df_duel["location_x"] > 40) & (df_duel["es_duelo_ganado"] == 1)].groupby("player_id").size().reset_index(name="duelos_zona_alta")
    intercep_cr = df_int[df_int["player_id"].isin(players_def) & (df_int["location_x"] > 60)].groupby("player_id").size().reset_index(name="intercepciones_campo_rival")
    pases_prog_def = df_pass[df_pass["player_id"].isin(players_def) & (df_pass["location_x"] < 40) & (df_pass["pass_end_x"] > df_pass["location_x"] + 15)].groupby("player_id").size().reset_index(name="pases_prog_desde_atras")
    despejes_aereos = df_clear[df_clear["player_id"].isin(players_def) & (df_clear["clearance_aerial_won"] == 1)].groupby("player_id").size().reset_index(name="despejes_aereos")
    df_def = dim_jugador_slim[dim_jugador_slim["player_id"].isin(players_def)].merge(duelos_zona, on="player_id", how="left").merge(intercep_cr, on="player_id", how="left").merge(pases_prog_def, on="player_id", how="left").merge(despejes_aereos, on="player_id", how="left").merge(valor_mercado_promedio(dim_valoracion, players_def), on="player_id", how="left").fillna(0)
    cols_def = ["duelos_zona_alta", "intercepciones_campo_rival", "pases_prog_desde_atras", "despejes_aereos"]
    tits_def = ["Duelos ganados zona alta", "Intercepciones campo rival", "Pases progresivos desde atras", "Despejes aereos"]
    escribir_reporte(
        "eda_v5_defensores.html",
        "Defensores",
        "Libero moderno - zonas altas y salida limpia.",
        "Centrales que defienden lejos del arco y construyen desde atras.",
        df_def,
        cols_def,
        tits_def,
        "defensor",
        "duelos_zona_alta",
        "Duelos ganados zona alta",
        [
            f"Universo: {len(df_def)} defensores. P75 duelos zona alta = {df_def['duelos_zona_alta'].quantile(.75):.0f}.",
            "Para DAX: score defensor = duelos_zona_alta * 0.35 + intercepciones_campo_rival * 0.30 + pases_prog_desde_atras * 0.35.",
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
        "eda_v5_laterales.html",
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
            "Para DAX: score lateral = duelos_defensivos_ganados * 0.30 + conducciones_hacia_centro * 0.35 + pases_hacia_adentro * 0.35.",
        ],
    )


def zip_output(output_dir: Path, zip_name: str) -> Path:
    base = output_dir.parent / zip_name
    zip_path = Path(shutil.make_archive(str(base), "zip", str(output_dir)))
    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline de scouting v5 corregido.")
    parser.add_argument("--repo-path", type=Path, default=Path("open-data/data"), help="Ruta a open-data/data de StatsBomb.")
    parser.add_argument("--tm-path", type=Path, default=Path("transfermarkt_data"), help="Ruta a CSVs de Transfermarkt.")
    parser.add_argument("--output-dir", type=Path, default=Path("scouting_v5_output"), help="Carpeta de salida.")
    parser.add_argument("--download-data", action="store_true", help="Descarga StatsBomb open-data y Transfermarkt via Kaggle.")
    parser.add_argument("--skip-eda", action="store_true", help="Genera solo CSV, sin reportes HTML.")
    parser.add_argument("--zip", action="store_true", help="Comprime la salida en scouting_v5_final.zip.")
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
    print("  PIPELINE DE SCOUTING V5")
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

    if not args.skip_eda:
        generar_reportes_eda(args.output_dir, dim_jugador, dim_valoracion)

    csvs = list(args.output_dir.glob("*.csv"))
    htmls = list(args.output_dir.glob("*.html"))
    total_mb = sum(f.stat().st_size for f in csvs + htmls) / 1024 / 1024

    print("\n" + "=" * 60)
    print("  PIPELINE V5 COMPLETADO")
    print("=" * 60)
    print(f"\n  {len(csvs)} archivos CSV en ./{args.output_dir}/")
    print(f"  {len(htmls)} reportes HTML en ./{args.output_dir}/")
    print(f"  Tamano total: {total_mb:.1f} MB")

    if args.zip:
        zip_path = zip_output(args.output_dir, "scouting_v5_final")
        print(f"  ZIP generado: {zip_path}")

    print(
        """
  ARCHIVOS ESPERADOS:
  - dim_jugador, dim_partido, dim_valoracion, dim_calendario
  - fact_shot, fact_pass, fact_duel, fact_dribble, fact_carry
  - fact_pressure, fact_interception, fact_clearance
  - fact_ball_receipt, fact_goalkeeper, fact_foul_committed
  - fact_foul_won, fact_miscontrol, fact_block

  POWER BI:
  - Importar CSV con separador ';' y decimal ','
  - dim_calendario[Date] -> dim_partido[match_date]
  - dim_jugador[player_id] -> fact_*[player_id]
  - dim_partido[match_id] -> fact_*[match_id]
"""
    )


if __name__ == "__main__":
    main()
