# Radiografía Power BI — scouting_dashboard_v12.pbix

Generado el 19/06/2026 15:58

## Resumen ejecutivo

| Métrica | Valor |
| --- | --- |
| Tablas | 26 |
| Columnas | 215 |
| Columnas calculadas | 26 |
| Medidas DAX | 69 |
| Consultas M / Power Query | 26 |
| Relaciones | 26 |
| Páginas del reporte | 3 |
| Visuales totales | 31 |
| Visuales Python | 2 |
| Visuales R | 0 |

## Tablas del modelo

### fact_heatmap_jugador

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| player_id | int64 |  |  | 0 |
| match_id | int64 |  |  | 0 |
| tipo | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `fact_heatmap_jugador` (tipo: `calculated`)
```powerquery
UNION(
    SELECTCOLUMNS(fact_ball_receipt, "location_x", fact_ball_receipt[location_x], "location_y", fact_ball_receipt[location_y], "player_id", fact_ball_receipt[player_id], "match_id", fact_ball_receipt[match_id], "tipo", "recepcion"),
    SELECTCOLUMNS(fact_pressure,     "location_x", fact_pressure[location_x],     "location_y", fact_pressure[location_y],     "player_id", fact_pressure[player_id],     "match_id", fact_pressure[match_id],     "tipo", "presion"),
    SELECTCOLUMNS(fact_shot,         "location_x", fact_shot[location_x],         "location_y", fact_shot[location_y],         "player_id", fact_shot[player_id],         "match_id", fact_shot[match_id],         "tipo", "remate"),
    SELECTCOLUMNS(fact_dribble,      "location_x", fact_dribble[location_x],      "location_y", fact_dribble[location_y],      "player_id", fact_dribble[player_id],      "match_id", fact_dribble[match_id],      "tipo", "dribble"),
    SELECTCOLUMNS(fact_carry,        "location_x", fact_carry[location_x],        "location_y", fact_carry[location_y],        "player_id", fact_carry[player_id],        "match_id", fact_carry[match_id],        "tipo", "conduccion"),
    SELECTCOLUMNS(fact_pass,         "location_x", fact_pass[location_x],         "location_y", fact_pass[location_y],         "player_id", fact_pass[player_id],         "match_id", fact_pass[match_id],         "tipo", "pase"),
    SELECTCOLUMNS(fact_duel,         "location_x", fact_duel[location_x],         "location_y", fact_duel[location_y],         "player_id", fact_duel[player_id],         "match_id", fact_duel[match_id],         "tipo", "duelo"),
    SELECTCOLUMNS(fact_interception, "location_x", fact_interception[location_x], "location_y", fact_interception[location_y], "player_id", fact_interception[player_id], "match_id", fact_interception[match_id], "tipo", "intercepcion")
)
```

### medidas

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |

#### Medidas DAX

##### `Minutos Jugados`
```dax
SUM(fact_minutes[minutos_jugados])
```
Formato: `0`

##### `Total Pases`
```dax
CALCULATE(COUNTROWS(fact_pass))
```
Formato: `0`

##### `Valor de Mercado Actual`
```dax
CALCULATE(
    MAX(dim_valoracion[market_value_in_eur]),
    FILTER(
        dim_valoracion,
        dim_valoracion[date] = CALCULATE(MAX(dim_valoracion[date]))
    )
)
```
Formato: `0`

##### `score_d por millón de eur`
```dax
DIVIDE([Score Delantero], [Valor de Mercado Actual] / 1000000)
```

##### `score_m por millón de eur`
```dax
DIVIDE([Score Mediocampista], [Valor de Mercado Actual] / 1000000)
```

##### `score_def por millón de eur`
```dax
DIVIDE([Score Defensor], [Valor de Mercado Actual] / 1000000)
```

##### `score_lat por millón de eur`
```dax
DIVIDE([Score Lateral], [Valor de Mercado Actual] / 1000000)
```

##### `Valor Dinámico Mediana`
```dax
50
```
Formato: `0`

#### Consultas M / Power Query

**Partición:** `medidas` (tipo: `m`)
```powerquery
let
    Origen = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i44FAA==", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [Columna1 = _t]),
    #"Tipo cambiado" = Table.TransformColumnTypes(Origen,{{"Columna1", type text}}),
    #"Columnas quitadas" = Table.RemoveColumns(#"Tipo cambiado",{"Columna1"})
in
    #"Columnas quitadas"
```

### medidas_del

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |

#### Medidas DAX

##### `xG Sin Penal`
```dax
CALCULATE(
    SUM(fact_shot[shot_statsbomb_xg]),
    fact_shot[shot_type] <> "Penalty"
)
```

##### `xG Sin Penal por 90`
```dax
DIVIDE([xG Sin Penal] * 90, [Minutos Jugados])
```

##### `Presiones Ultimo Tercio`
```dax
CALCULATE(COUNTROWS(fact_pressure), fact_pressure[location_x] > 80)
```
Formato: `0`

##### `Presiones por 90`
```dax
DIVIDE([Presiones Ultimo Tercio] * 90, [Minutos Jugados])
```

##### `Recepciones Campo Rival`
```dax
CALCULATE(COUNTROWS(fact_ball_receipt), fact_ball_receipt[location_x] > 80)
```
Formato: `0`

##### `Recepciones por 90`
```dax
DIVIDE([Recepciones Campo Rival] * 90, [Minutos Jugados])
```

##### `Total Desmarques Ruptura`
```dax
VAR NombreJugador = SELECTEDVALUE(dim_jugador[player])
RETURN
IF(
    ISBLANK(NombreJugador),
    BLANK(),
    COUNTROWS(
        FILTER(
            ALL(fact_pass),
            fact_pass[es_desmarque_ruptura] = TRUE()
            && fact_pass[pass_recipient] = NombreJugador
        )
    )
)
```
Formato: `0`

##### `Desmarques por 90`
```dax
DIVIDE([Total Desmarques Ruptura] * 90, [Minutos Jugados])
```

##### `Dribbles`
```dax
CALCULATE(COUNTROWS(fact_dribble), fact_dribble[es_dribble_exitoso] = 1)
```
Formato: `0`

##### `Dribbles por 90`
```dax
DIVIDE([Dribbles] * 90, [Minutos Jugados])
```

##### `Score Delantero`
```dax
IF(
    [Minutos Jugados] < 450,
    BLANK(),
    VAR Total = CALCULATE(DISTINCTCOUNT(dim_jugador[player_id]), ALL(dim_jugador))
    VAR RankDesmarques  = DIVIDE(RANKX(ALL(dim_jugador), [Desmarques por 90],, ASC, Dense), Total)
    VAR RankPresiones   = DIVIDE(RANKX(ALL(dim_jugador), [Presiones por 90],, ASC, Dense), Total)
    VAR RankXG          = DIVIDE(RANKX(ALL(dim_jugador), [xG Sin Penal por 90],, ASC, Dense), Total)
    VAR RankRecepciones = DIVIDE(RANKX(ALL(dim_jugador), [Recepciones por 90],, ASC, Dense), Total)
    RETURN
        RankDesmarques   * 0.30 +
        RankPresiones    * 0.30 +
        RankXG           * 0.20 +
        RankRecepciones  * 0.20
)
```

##### `Pct Desmarques`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Delantero]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Desmarques por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Presiones`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Delantero]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Presiones por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct xG`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Delantero]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [xG Sin Penal por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Recepciones`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Delantero]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Recepciones por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Dribbles`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Delantero]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Dribbles por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Valor Dinámico Jugador`
```dax
SWITCH(
    SELECTEDVALUE(dim_metricas_1[Delanteros]),
    "Desmarques p90",   [Pct Desmarques],
    "Presiones p90",    [Pct Presiones],
    "xG Sin Penal p90", [Pct xG],
    "Recepciones p90",  [Pct Recepciones],
    "Dribbles p90",     [Pct Dribbles]
)
```

#### Consultas M / Power Query

**Partición:** `medidas_del` (tipo: `m`)
```powerquery
let
    Origen = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i44FAA==", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [Columna1 = _t]),
    #"Tipo cambiado" = Table.TransformColumnTypes(Origen,{{"Columna1", type text}}),
    #"Columnas quitadas" = Table.RemoveColumns(#"Tipo cambiado",{"Columna1"})
in
    #"Columnas quitadas"
```

### medidas_mid

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |

#### Medidas DAX

##### `Pases Progresivos`
```dax
CALCULATE(
    COUNTROWS(fact_pass),
    fact_pass[es_pase_completo] = 1,
    fact_pass[pass_end_x] > fact_pass[location_x] + 8
)
```
Formato: `0`

##### `Pases Prog por 90`
```dax
DIVIDE([Pases Progresivos] * 90, [Minutos Jugados])
```

##### `Ratio Pases Prog`
```dax
DIVIDE([Pases Progresivos], [Total Pases])
```

##### `Conducciones Progresivas`
```dax
CALCULATE(
    COUNTROWS(fact_carry),
    fact_carry[carry_end_x] > fact_carry[location_x] + 5
)
```
Formato: `0`

##### `Conducciones Prog por 90`
```dax
DIVIDE([Conducciones Progresivas] * 90, [Minutos Jugados])
```

##### `Pases Exitosos Bajo Presion`
```dax
CALCULATE(
    COUNTROWS(fact_pass),
    fact_pass[es_pase_completo] = 1,
    fact_pass[under_pressure] = 1
)
```
Formato: `0`

##### `Pases Bajo Presion por 90`
```dax
DIVIDE([Pases Exitosos Bajo Presion] * 90, [Minutos Jugados])
```

##### `Perdidas de Balon`
```dax
COUNTROWS(fact_miscontrol)
```
Formato: `0`

##### `Perdidas por 90`
```dax
DIVIDE([Perdidas de Balon] * 90, [Minutos Jugados])
```

##### `Score Mediocampista`
```dax
IF(
    [Minutos Jugados] < 450,
    BLANK(),
    VAR Total = CALCULATE(DISTINCTCOUNT(dim_jugador[player_id]), ALL(dim_jugador))
    VAR RankPasesProg   = DIVIDE(RANKX(ALL(dim_jugador), [Pases Prog por 90],, ASC, Dense), Total)
    VAR RankRatioPases  = DIVIDE(RANKX(ALL(dim_jugador), [Ratio Pases Prog],, ASC, Dense), Total)
    VAR RankCondProg    = DIVIDE(RANKX(ALL(dim_jugador), [Conducciones Prog por 90],, ASC, Dense), Total)
    VAR RankBajoPresion = DIVIDE(RANKX(ALL(dim_jugador), [Pases Bajo Presion por 90],, ASC, Dense), Total)
    VAR RankPerdidas    = DIVIDE(RANKX(ALL(dim_jugador), [Perdidas por 90],, DESC, Dense), Total)
    RETURN
        RankPasesProg   * 0.25 +
        RankRatioPases  * 0.25 +
        RankCondProg    * 0.20 +
        RankBajoPresion * 0.20 +
        RankPerdidas    * 0.10
)
```

##### `Pct Pases Prog`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Mediocampista]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Pases Prog por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Ratio Pases Prog`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Mediocampista]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Ratio Pases Prog],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Conducciones Prog`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Mediocampista]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Conducciones Prog por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Pases Bajo Presion`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Mediocampista]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Pases Bajo Presion por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Perdidas`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Mediocampista]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Perdidas por 90],, DESC, Dense), COUNTROWS(Cohorte))
```

##### `Valor Dinámico Jugador Mid`
```dax
SWITCH(
    SELECTEDVALUE(dim_metricas_1[Mediocampo]),
    "Pases Prog p90",        [Pct Pases Prog],
    "Ratio Pases Prog",      [Pct Ratio Pases Prog],
    "Conducciones Prog p90", [Pct Conducciones Prog],
    "Pases Bajo Presion p90",[Pct Pases Bajo Presion],
    "Perdidas p90",          [Pct Perdidas]
)
```

#### Consultas M / Power Query

**Partición:** `medidas_mid` (tipo: `m`)
```powerquery
let
    Origen = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i44FAA==", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [Columna1 = _t]),
    #"Tipo cambiado" = Table.TransformColumnTypes(Origen,{{"Columna1", type text}}),
    #"Columnas quitadas" = Table.RemoveColumns(#"Tipo cambiado",{"Columna1"})
in
    #"Columnas quitadas"
```

### medidas_def

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |

#### Medidas DAX

##### `Duelos Zona Alta`
```dax
CALCULATE(
    COUNTROWS(fact_duel),
    fact_duel[location_x] > 40,
    fact_duel[es_duelo_ganado] = 1
)
```
Formato: `0`

##### `Intercepciones Campo Rival`
```dax
CALCULATE(COUNTROWS(fact_interception), fact_interception[location_x] > 60)
```
Formato: `0`

##### `Intercepciones CR por 90`
```dax
DIVIDE([Intercepciones Campo Rival] * 90, [Minutos Jugados])
```

##### `Pases Prog Desde Atras`
```dax
CALCULATE(
    COUNTROWS(fact_pass),
    fact_pass[es_pase_completo] = 1,
    fact_pass[location_x] < 40,
    fact_pass[pass_end_x] > fact_pass[location_x] + 15
)
```
Formato: `0`

##### `Pases Prog Atras por 90`
```dax
DIVIDE([Pases Prog Desde Atras] * 90, [Minutos Jugados])
```

##### `Carrys Progresivos Zona Media`
```dax
CALCULATE(
    COUNTROWS(fact_carry),
    fact_carry[location_x] >= 35,
    fact_carry[location_x] <= 65,
    fact_carry[carry_end_x] > fact_carry[location_x] + 8
)
```
Formato: `0`

##### `Carrys Zona Media por 90`
```dax
DIVIDE([Carrys Progresivos Zona Media] * 90, [Minutos Jugados])
```

##### `Score Defensor`
```dax
IF(
    [Minutos Jugados] < 450,
    BLANK(),
    VAR Total = CALCULATE(DISTINCTCOUNT(dim_jugador[player_id]), ALL(dim_jugador))
    VAR RankDuelos     = DIVIDE(RANKX(ALL(dim_jugador), [Duelos Zona Alta por 90],, ASC, Dense), Total)
    VAR RankIntercep   = DIVIDE(RANKX(ALL(dim_jugador), [Intercepciones CR por 90],, ASC, Dense), Total)
    VAR RankPasesAtras = DIVIDE(RANKX(ALL(dim_jugador), [Pases Prog Atras por 90],, ASC, Dense), Total)
    VAR RankCarrys     = DIVIDE(RANKX(ALL(dim_jugador), [Carrys Zona Media por 90],, ASC, Dense), Total)
    RETURN
        RankDuelos     * 0.20 +
        RankIntercep   * 0.30 +
        RankPasesAtras * 0.30 +
        RankCarrys     * 0.20
)
```

##### `Pct Duelos Zona Alta`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Defensor]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Duelos Zona Alta por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Duelos Zona Alta por 90`
```dax
DIVIDE([Duelos Zona Alta] * 90, [Minutos Jugados])
```

##### `Pct Intercepciones CR`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Defensor]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Intercepciones CR por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Pases Prog Atras`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Defensor]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Pases Prog Atras por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Carrys Zona Media`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Defensor]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Carrys Zona Media por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Valor Dinámico Jugador Def`
```dax
SWITCH(
    SELECTEDVALUE(dim_metricas_2[Defensivos]),
    "Duelos Zona Alta p90",  [Pct Duelos Zona Alta],
    "Intercepciones CR p90", [Pct Intercepciones CR],
    "Pases Prog Atras p90",  [Pct Pases Prog Atras],
    "Carrys Zona Media p90", [Pct Carrys Zona Media]
)
```

#### Consultas M / Power Query

**Partición:** `medidas_def` (tipo: `m`)
```powerquery
let
    Origen = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i44FAA==", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [Columna1 = _t]),
    #"Tipo cambiado" = Table.TransformColumnTypes(Origen,{{"Columna1", type text}}),
    #"Columnas quitadas" = Table.RemoveColumns(#"Tipo cambiado",{"Columna1"})
in
    #"Columnas quitadas"
```

### medidas_lat

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |

#### Medidas DAX

##### `Duelos Defensivos Ganados`
```dax
CALCULATE(COUNTROWS(fact_duel), fact_duel[es_duelo_ganado] = 1)
```
Formato: `0`

##### `Duelos Def por 90`
```dax
DIVIDE([Duelos Defensivos Ganados] * 90, [Minutos Jugados])
```

##### `Conducciones Hacia Centro`
```dax
CALCULATE(
    COUNTROWS(fact_carry),
    OR(
        AND(fact_carry[location_y] < 30, fact_carry[carry_end_y] > fact_carry[location_y]),
        AND(fact_carry[location_y] > 50, fact_carry[carry_end_y] < fact_carry[location_y])
    )
)
```
Formato: `0`

##### `Conducciones Centro por 90`
```dax
DIVIDE([Conducciones Hacia Centro] * 90, [Minutos Jugados])
```

##### `Pases Hacia Adentro`
```dax
CALCULATE(
    COUNTROWS(fact_pass),
    fact_pass[es_pase_completo] = 1,
    OR(
        AND(fact_pass[location_y] < 25, fact_pass[pass_end_y] > fact_pass[location_y] + 5),
        AND(fact_pass[location_y] > 55, fact_pass[pass_end_y] < fact_pass[location_y] - 5)
    )
)
```
Formato: `0`

##### `Pases Adentro por 90`
```dax
DIVIDE([Pases Hacia Adentro] * 90, [Minutos Jugados])
```

##### `Presiones En Banda`
```dax
CALCULATE(
    COUNTROWS(fact_pressure),
    OR(fact_pressure[location_y] < 20, fact_pressure[location_y] > 60)
)
```
Formato: `0`

##### `Presiones Banda por 90`
```dax
DIVIDE([Presiones En Banda] * 90, [Minutos Jugados])
```

##### `Score Lateral`
```dax
IF(
    [Minutos Jugados] < 450,
    BLANK(),
    VAR Total = CALCULATE(DISTINCTCOUNT(dim_jugador[player_id]), ALL(dim_jugador))
    VAR RankDuelos     = DIVIDE(RANKX(ALL(dim_jugador), [Duelos Def por 90],, ASC, Dense), Total)
    VAR RankCondCentro = DIVIDE(RANKX(ALL(dim_jugador), [Conducciones Centro por 90],, ASC, Dense), Total)
    VAR RankPasesAdent = DIVIDE(RANKX(ALL(dim_jugador), [Pases Adentro por 90],, ASC, Dense), Total)
    VAR RankPresiones  = DIVIDE(RANKX(ALL(dim_jugador), [Presiones Banda por 90],, ASC, Dense), Total)
    RETURN
        RankDuelos     * 0.30 +
        RankCondCentro * 0.30 +
        RankPasesAdent * 0.30 +
        RankPresiones  * 0.10
)
```

##### `Pct Duelos Def`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Lateral]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Duelos Def por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Conducciones Centro`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Lateral]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Conducciones Centro por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Pases Adentro`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Lateral]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Pases Adentro por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Pct Presiones Banda`
```dax
VAR Cohorte = FILTER(ALL(dim_jugador), NOT ISBLANK([Score Lateral]))
RETURN 100 * DIVIDE(RANKX(Cohorte, [Presiones Banda por 90],, ASC, Dense), COUNTROWS(Cohorte))
```

##### `Valor Dinámico Jugador Lat`
```dax
SWITCH(
    SELECTEDVALUE(dim_metricas_2[Laterales]),
    "Duelos Def p90",         [Pct Duelos Def],
    "Conducciones Centro p90",[Pct Conducciones Centro],
    "Pases Adentro p90",      [Pct Pases Adentro],
    "Presiones Banda p90",    [Pct Presiones Banda]
)
```

#### Consultas M / Power Query

**Partición:** `medidas_lat` (tipo: `m`)
```powerquery
let
    Origen = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i44FAA==", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [Columna1 = _t]),
    #"Tipo cambiado" = Table.TransformColumnTypes(Origen,{{"Columna1", type text}}),
    #"Columnas quitadas" = Table.RemoveColumns(#"Tipo cambiado",{"Columna1"})
in
    #"Columnas quitadas"
```

### dim_jugador

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| player_id | int64 |  |  | 0 |
| player | string |  |  |  |
| country | string |  |  |  |
| tm_player_id | int64 |  |  | 0 |
| tm_name | string |  |  |  |
| date_of_birth | dateTime |  |  | General Date |
| country_of_citizenship | string |  |  |  |
| sub_position | string |  |  |  |
| foot | string |  |  |  |
| height_in_cm | int64 |  |  | 0 |
| market_value_in_eur | int64 |  |  | 0 |
| fuzzy_score | double |  |  |  |
| metodo_match | string |  |  |  |
| equipo_habitual | string |  |  |  |
| posicion_habitual | string |  |  |  |
| Edad en 2020 | int64 | ✓ |  | 0 |

**Expresión de `Edad en 2020`:**
```dax
IF(
    ISBLANK(dim_jugador[date_of_birth]),
    BLANK(),
    2020 - YEAR(dim_jugador[date_of_birth])
)
```

#### Consultas M / Power Query

**Partición:** `dim_jugador` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\dim_jugador.csv"),[Delimiter=";", Columns=15, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"player_id", Int64.Type}, {"player", type text}, {"country", type text}, {"tm_player_id", Int64.Type}, {"tm_name", type text}, {"date_of_birth", type datetime}, {"country_of_citizenship", type text}, {"sub_position", type text}, {"foot", type text}, {"height_in_cm", Int64.Type}, {"market_value_in_eur", Int64.Type}, {"fuzzy_score", type number}, {"metodo_match", type text}, {"equipo_habitual", type text}, {"posicion_habitual", type text}})
in
    #"Tipo cambiado"
```

### DateTableTemplate_d9a2e886-9150-4f60-97bf-8674314b2d71 _oculta_

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Date | dateTime |  | ✓ | General Date |
| Año | int64 | ✓ | ✓ | 0 |
| NroMes | int64 | ✓ | ✓ | 0 |
| Mes | string | ✓ | ✓ |  |
| NroTrimestre | int64 | ✓ | ✓ | 0 |
| Trimestre | string | ✓ | ✓ |  |
| Día | int64 | ✓ | ✓ | 0 |

**Expresión de `Año`:**
```dax
YEAR([Date])
```

**Expresión de `NroMes`:**
```dax
MONTH([Date])
```

**Expresión de `Mes`:**
```dax
FORMAT([Date], "MMMM")
```

**Expresión de `NroTrimestre`:**
```dax
INT(([NroMes] + 2) / 3)
```

**Expresión de `Trimestre`:**
```dax
"Trim. " & [NroTrimestre]
```

**Expresión de `Día`:**
```dax
DAY([Date])
```

#### Consultas M / Power Query

**Partición:** `DateTableTemplate_d9a2e886-9150-4f60-97bf-8674314b2d71` (tipo: `calculated`)
```powerquery
Calendar(Date(2015,1,1), Date(2015,1,1))
```

**Jerarquías:** Jerarquía de fechas

### LocalDateTable_e5597772-8bef-42e2-9c8a-3477167d46e7 _oculta_

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Date | dateTime |  | ✓ | General Date |
| Año | int64 | ✓ | ✓ | 0 |
| NroMes | int64 | ✓ | ✓ | 0 |
| Mes | string | ✓ | ✓ |  |
| NroTrimestre | int64 | ✓ | ✓ | 0 |
| Trimestre | string | ✓ | ✓ |  |
| Día | int64 | ✓ | ✓ | 0 |

**Expresión de `Año`:**
```dax
YEAR([Date])
```

**Expresión de `NroMes`:**
```dax
MONTH([Date])
```

**Expresión de `Mes`:**
```dax
FORMAT([Date], "MMMM")
```

**Expresión de `NroTrimestre`:**
```dax
INT(([NroMes] + 2) / 3)
```

**Expresión de `Trimestre`:**
```dax
"Trim. " & [NroTrimestre]
```

**Expresión de `Día`:**
```dax
DAY([Date])
```

#### Consultas M / Power Query

**Partición:** `LocalDateTable_e5597772-8bef-42e2-9c8a-3477167d46e7` (tipo: `calculated`)
```powerquery
Calendar(Date(Year(MIN('dim_jugador'[date_of_birth])), 1, 1), Date(Year(MAX('dim_jugador'[date_of_birth])), 12, 31))
```

**Jerarquías:** Jerarquía de fechas

### dim_partido

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| competition_id | int64 |  |  | 0 |
| competition | string |  |  |  |
| season_id | int64 |  |  | 0 |
| season | string |  |  |  |
| match_date | dateTime |  |  | Long Date |
| kick_off | dateTime |  |  | Long Time |
| match_week | int64 |  |  | 0 |
| home_team_id | int64 |  |  | 0 |
| home_team | string |  |  |  |
| away_team_id | int64 |  |  | 0 |
| away_team | string |  |  |  |
| home_score | int64 |  |  | 0 |
| away_score | int64 |  |  | 0 |
| stadium | string |  |  |  |
| referee | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `dim_partido` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\dim_partido.csv"),[Delimiter=";", Columns=16, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"competition_id", Int64.Type}, {"competition", type text}, {"season_id", Int64.Type}, {"season", type text}, {"match_date", type date}, {"kick_off", type time}, {"match_week", Int64.Type}, {"home_team_id", Int64.Type}, {"home_team", type text}, {"away_team_id", Int64.Type}, {"away_team", type text}, {"home_score", Int64.Type}, {"away_score", Int64.Type}, {"stadium", type text}, {"referee", type text}})
in
    #"Tipo cambiado"
```

### dim_calendario

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Date | dateTime |  |  | Long Date |
| Anio | int64 |  |  | 0 |
| Mes_Numero | int64 |  |  | 0 |
| Mes_Nombre | string |  |  |  |
| Trimestre | string |  |  |  |
| Semana_Anio | int64 |  |  | 0 |
| Dia_Semana_Numero | int64 |  |  | 0 |
| Dia_Semana_Nombre | string |  |  |  |
| Es_Fin_De_Semana | int64 |  |  | 0 |
| Temporada | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `dim_calendario` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\dim_calendario.csv"),[Delimiter=";", Columns=10, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"Date", type date}, {"Anio", Int64.Type}, {"Mes_Numero", Int64.Type}, {"Mes_Nombre", type text}, {"Trimestre", type text}, {"Semana_Anio", Int64.Type}, {"Dia_Semana_Numero", Int64.Type}, {"Dia_Semana_Nombre", type text}, {"Es_Fin_De_Semana", Int64.Type}, {"Temporada", type text}})
in
    #"Tipo cambiado"
```

### LocalDateTable_fcd02b01-57ff-4ce4-a0ad-62efabac574f _oculta_

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Date | dateTime |  | ✓ | General Date |
| Año | int64 | ✓ | ✓ | 0 |
| NroMes | int64 | ✓ | ✓ | 0 |
| Mes | string | ✓ | ✓ |  |
| NroTrimestre | int64 | ✓ | ✓ | 0 |
| Trimestre | string | ✓ | ✓ |  |
| Día | int64 | ✓ | ✓ | 0 |

**Expresión de `Año`:**
```dax
YEAR([Date])
```

**Expresión de `NroMes`:**
```dax
MONTH([Date])
```

**Expresión de `Mes`:**
```dax
FORMAT([Date], "MMMM")
```

**Expresión de `NroTrimestre`:**
```dax
INT(([NroMes] + 2) / 3)
```

**Expresión de `Trimestre`:**
```dax
"Trim. " & [NroTrimestre]
```

**Expresión de `Día`:**
```dax
DAY([Date])
```

#### Consultas M / Power Query

**Partición:** `LocalDateTable_fcd02b01-57ff-4ce4-a0ad-62efabac574f` (tipo: `calculated`)
```powerquery
Calendar(Date(Year(MIN('dim_calendario'[Date])), 1, 1), Date(Year(MAX('dim_calendario'[Date])), 12, 31))
```

**Jerarquías:** Jerarquía de fechas

### dim_valoracion

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| player_id | int64 |  |  | 0 |
| tm_player_id | int64 |  |  | 0 |
| date | dateTime |  |  | Long Date |
| market_value_in_eur | int64 |  |  | 0 |
| current_club_name | string |  |  |  |
| player_club_domestic_competition_id | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `dim_valoracion` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\dim_valoracion.csv"),[Delimiter=";", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"player_id", Int64.Type}, {"tm_player_id", Int64.Type}, {"date", type date}, {"market_value_in_eur", Int64.Type}, {"current_club_name", type text}, {"player_club_domestic_competition_id", type text}})
in
    #"Tipo cambiado"
```

### LocalDateTable_9e71e827-f16c-403a-be2e-af34f14031b3 _oculta_

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Date | dateTime |  | ✓ | General Date |
| Año | int64 | ✓ | ✓ | 0 |
| NroMes | int64 | ✓ | ✓ | 0 |
| Mes | string | ✓ | ✓ |  |
| NroTrimestre | int64 | ✓ | ✓ | 0 |
| Trimestre | string | ✓ | ✓ |  |
| Día | int64 | ✓ | ✓ | 0 |

**Expresión de `Año`:**
```dax
YEAR([Date])
```

**Expresión de `NroMes`:**
```dax
MONTH([Date])
```

**Expresión de `Mes`:**
```dax
FORMAT([Date], "MMMM")
```

**Expresión de `NroTrimestre`:**
```dax
INT(([NroMes] + 2) / 3)
```

**Expresión de `Trimestre`:**
```dax
"Trim. " & [NroTrimestre]
```

**Expresión de `Día`:**
```dax
DAY([Date])
```

#### Consultas M / Power Query

**Partición:** `LocalDateTable_9e71e827-f16c-403a-be2e-af34f14031b3` (tipo: `calculated`)
```powerquery
Calendar(Date(Year(MIN('dim_valoracion'[date])), 1, 1), Date(Year(MAX('dim_valoracion'[date])), 12, 31))
```

**Jerarquías:** Jerarquía de fechas

### fact_ball_receipt

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| es_recepcion_exitosa | int64 |  |  | 0 |

#### Consultas M / Power Query

**Partición:** `fact_ball_receipt` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_ball_receipt.csv"),[Delimiter=";", Columns=9, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"es_recepcion_exitosa", Int64.Type}})
in
    #"Tipo cambiado"
```

### fact_carry

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| carry_end_x | double |  |  |  |
| carry_end_y | double |  |  |  |
| carry_distancia | double |  |  |  |

#### Consultas M / Power Query

**Partición:** `fact_carry` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_carry.csv"),[Delimiter=";", Columns=11, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"carry_end_x", type number}, {"carry_end_y", type number}, {"carry_distancia", type number}})
in
    #"Tipo cambiado"
```

### fact_dribble

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| es_dribble_exitoso | int64 |  |  | 0 |

#### Consultas M / Power Query

**Partición:** `fact_dribble` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_dribble.csv"),[Delimiter=";", Columns=9, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"es_dribble_exitoso", Int64.Type}})
in
    #"Tipo cambiado"
```

### fact_duel

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| duel_type | string |  |  |  |
| es_duelo_ganado | int64 |  |  | 0 |

#### Consultas M / Power Query

**Partición:** `fact_duel` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_duel.csv"),[Delimiter=";", Columns=10, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"duel_type", type text}, {"es_duelo_ganado", Int64.Type}})
in
    #"Tipo cambiado"
```

### fact_interception

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| es_intercepcion_exitosa | int64 |  |  | 0 |

#### Consultas M / Power Query

**Partición:** `fact_interception` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_interception.csv"),[Delimiter=";", Columns=9, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"es_intercepcion_exitosa", Int64.Type}})
in
    #"Tipo cambiado"
```

### fact_minutes

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minuto_entrada | int64 |  |  | 0 |
| minuto_salida | int64 |  |  | 0 |
| minutos_jugados | int64 |  |  | 0 |
| es_titular | int64 |  |  | 0 |
| fue_sustituido | int64 |  |  | 0 |

#### Consultas M / Power Query

**Partición:** `fact_minutes` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_minutes.csv"),[Delimiter=";", Columns=8, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minuto_entrada", Int64.Type}, {"minuto_salida", Int64.Type}, {"minutos_jugados", Int64.Type}, {"es_titular", Int64.Type}, {"fue_sustituido", Int64.Type}})
in
    #"Tipo cambiado"
```

### fact_miscontrol

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `fact_miscontrol` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_miscontrol.csv"),[Delimiter=";", Columns=8, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}})
in
    #"Tipo cambiado"
```

### fact_pass

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| pass_end_x | double |  |  |  |
| pass_end_y | double |  |  |  |
| pass_recipient | string |  |  |  |
| pass_shot_assist | int64 |  |  | 0 |
| pass_goal_assist | int64 |  |  | 0 |
| pass_cross | int64 |  |  | 0 |
| pass_switch | int64 |  |  | 0 |
| pass_through_ball | int64 |  |  | 0 |
| es_pase_completo | int64 |  |  | 0 |
| es_asistencia_gol | int64 |  |  | 0 |
| es_asistencia_tiro | int64 |  |  | 0 |
| es_desmarque_ruptura | boolean | ✓ |  | "TRUE";"TRUE";"FALSE" |

**Expresión de `es_desmarque_ruptura`:**
```dax
fact_pass[es_pase_completo] = 1
    && fact_pass[pass_end_x] > 80
    && (
        fact_pass[pass_through_ball] = 1
        || (fact_pass[pass_end_x] - fact_pass[location_x]) >= 15
    )
```

#### Consultas M / Power Query

**Partición:** `fact_pass` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_pass.csv"),[Delimiter=";", Columns=19, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"pass_end_x", type number}, {"pass_end_y", type number}, {"pass_recipient", type text}, {"pass_shot_assist", Int64.Type}, {"pass_goal_assist", Int64.Type}, {"pass_cross", Int64.Type}, {"pass_switch", Int64.Type}, {"pass_through_ball", Int64.Type}, {"es_pase_completo", Int64.Type}, {"es_asistencia_gol", Int64.Type}, {"es_asistencia_tiro", Int64.Type}})
in
    #"Tipo cambiado"
```

### fact_pressure

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `fact_pressure` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_pressure.csv"),[Delimiter=";", Columns=8, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}})
in
    #"Tipo cambiado"
```

### fact_shot

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| match_id | int64 |  |  | 0 |
| player_id | int64 |  |  | 0 |
| team_id | int64 |  |  | 0 |
| minute | int64 |  |  | 0 |
| location_x | double |  |  |  |
| location_y | double |  |  |  |
| under_pressure | int64 |  |  | 0 |
| position | string |  |  |  |
| shot_statsbomb_xg | double |  |  |  |
| shot_type | string |  |  |  |
| es_gol | int64 |  |  | 0 |
| es_al_arco | int64 |  |  | 0 |

#### Consultas M / Power Query

**Partición:** `fact_shot` (tipo: `m`)
```powerquery
let
    Origen = Csv.Document(File.Contents("D:\proyectos\scouting-futbol\output\scouting_v12_output\fact_shot.csv"),[Delimiter=";", Columns=12, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"Encabezados promovidos" = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    #"Tipo cambiado" = Table.TransformColumnTypes(#"Encabezados promovidos",{{"match_id", Int64.Type}, {"player_id", Int64.Type}, {"team_id", Int64.Type}, {"minute", Int64.Type}, {"location_x", type number}, {"location_y", type number}, {"under_pressure", Int64.Type}, {"position", type text}, {"shot_statsbomb_xg", type number}, {"shot_type", type text}, {"es_gol", Int64.Type}, {"es_al_arco", Int64.Type}})
in
    #"Tipo cambiado"
```

### dim_metricas_1

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Delanteros | string |  |  |  |
| Mediocampo | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `dim_metricas_1` (tipo: `calculated`)
```powerquery
DATATABLE(
    "Generales", STRING,
    "Mediocampo", STRING,
    {
        {"Desmarques p90",   "Pases Prog p90"},
        {"Presiones p90",    "Ratio Pases Prog"},
        {"xG Sin Penal p90", "Conducciones Prog p90"},
        {"Recepciones p90",  "Pases Bajo Presion p90"},
        {"Dribbles p90",     "Perdidas p90"}
    }
)
```

### dim_metricas_2

**Modo de almacenamiento:** `import`

#### Columnas

| Nombre | Tipo | Calculada | Oculta | Formato |
| --- | --- | --- | --- | --- |
| RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61 | int64 |  | ✓ |  |
| Defensivos | string |  |  |  |
| Laterales | string |  |  |  |

#### Consultas M / Power Query

**Partición:** `dim_metricas_2` (tipo: `calculated`)
```powerquery
DATATABLE(
    "Defensivos", STRING,
    "Laterales", STRING,
    {
        {"Duelos Zona Alta p90",  "Duelos Def p90"},
        {"Intercepciones CR p90", "Conducciones Centro p90"},
        {"Pases Prog Atras p90",  "Pases Adentro p90"},
        {"Carrys Zona Media p90", "Presiones Banda p90"}
    }
)
```

## Relaciones entre tablas

| Tabla origen | Columna origen | → | Tabla destino | Columna destino | Filtro cruzado | Activa |
| --- | --- | --- | --- | --- | --- | --- |
| dim_jugador | date_of_birth | → | LocalDateTable_e5597772-8bef-42e2-9c8a-3477167d46e7 | Date | datePartOnly | ✓ |
| dim_calendario | Date | → | LocalDateTable_fcd02b01-57ff-4ce4-a0ad-62efabac574f | Date | datePartOnly | ✓ |
| dim_valoracion | date | → | LocalDateTable_9e71e827-f16c-403a-be2e-af34f14031b3 | Date | datePartOnly | ✓ |
| dim_valoracion | player_id | → | dim_jugador | player_id | bothDirections | ✓ |
| fact_ball_receipt | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_carry | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_dribble | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_duel | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_interception | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_minutes | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_miscontrol | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_pass | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_pressure | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_shot | player_id | → | dim_jugador | player_id | singleDirection | ✓ |
| fact_ball_receipt | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_carry | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_dribble | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_duel | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_interception | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_minutes | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_miscontrol | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_pass | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_pressure | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| fact_shot | match_id | → | dim_partido | match_id | singleDirection | ✓ |
| dim_partido | match_date | → | dim_calendario | Date | singleDirection | ✓ |
| fact_heatmap_jugador | player_id | → | dim_jugador | player_id | singleDirection | ✓ |

## Páginas del reporte

### jugadores

Dimensiones: 1280 × 720 px | 7 visuales

| Tipo | Título | Tamaño | Campos |
| --- | --- | --- | --- |
| Forma | _(sin título)_ | 1280×74 |  |
| Cuadro de texto | _(sin título)_ | 955×74 |  |
| Botón de acción | Detalles | 94×74 |  |
| Segmentador | _(sin título)_ | 904×146 | dim_posicion.posicion |
| Segmentador | selector de valor de mercado | 189×146 | dim_jugador.market_value_in_eur |
| Segmentador | selector de edad | 187×146 | dim_jugador.Edad en 2020 |
| Tabla | _(sin título)_ | 1280×500 | dim_jugador.player, medidas.Score Unificado, medidas.Score Unificado por Millon, Sum(dim_jugador.Edad en 2020), dim_jugador.posicion_habitual (+2) |

### detalle

Dimensiones: 1280 × 720 px | 17 visuales

**Filtros de página:**
- `{"name": "87fcd898b701d40a802d", "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_jugador"}}, "Property": "player"}}, "filter": {`

| Tipo | Título | Tamaño | Campos |
| --- | --- | --- | --- |
| Botón de acción | _(sin título)_ | 100×40 |  |
| Forma | _(sin título)_ | 482×77 |  |
| cardVisual | _(sin título)_ | 749×77 | Min(dim_jugador.player) |
| Cuadro de texto | _(sin título)_ | 467×66 |  |
| cardVisual | _(sin título)_ | 482×87 | Min(dim_posicion.posicion) |
| cardVisual | _(sin título)_ | 256×87 | Min(dim_jugador.country) |
| cardVisual | _(sin título)_ | 493×87 | Min(dim_valoracion.current_club_name) |
| cardVisual | _(sin título)_ | 139×105 | medidas.Metrica Card 4 |
| cardVisual | altura (cm) | 114×102 | Sum(dim_jugador.height_in_cm) |
| cardVisual | edad | 95×102 | Sum(dim_jugador.Edad en 2017) |
| cardVisual | minutos jugados | 136×102 | medidas.Minutos Jugados |
| cardVisual | _(sin título)_ | 138×103 | medidas.Metrica Card 1 |
| cardVisual | _(sin título)_ | 138×103 | medidas.Metrica Card 2 |
| cardVisual | _(sin título)_ | 138×103 | medidas.Metrica Card 3 |
| cardVisual | _(sin título)_ | 131×103 | medidas.Metrica Card 5 |
| Python | _(sin título)_ | 546×493 | medidas.Valor Dinámico Radar, medidas.Posicion Seleccionada Texto, medidas.Valor Dinámico Mediana, dim_metricas.metrica |
| Python | _(sin título)_ | 666×394 | Sum(fact_heatmap_jugador.location_x), Sum(fact_heatmap_jugador.location_y), fact_heatmap_jugador.tipo |

### evolución valor

Dimensiones: 1280 × 720 px | 7 visuales

**Filtros de página:**
- `{"name": "caf3fa51a6708a5d1270", "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_jugador"}}, "Property": "player"}}, "filter": {`

| Tipo | Título | Tamaño | Campos |
| --- | --- | --- | --- |
| Forma | _(sin título)_ | 1280×87 |  |
| Botón de acción | _(sin título)_ | 100×40 |  |
| cardVisual | _(sin título)_ | 749×77 | Min(dim_jugador.player) |
| Cuadro de texto | _(sin título)_ | 467×65 |  |
| Línea | Valor Mercado por Año | 1280×202 | medidas.Valor Mercado por Temporada, dim_calendario.Anio |
| Línea | minutos jugados por temporada | 1280×202 | medidas.Minutos Jugados, dim_calendario.Anio |
| Tabla | _(sin título)_ | 265×202 | dim_valoracion.current_club_name, dim_calendario.Date.Variación.Jerarquía de fechas.Año |

## Uso de campos en el reporte

| Campo / Medida | Páginas donde se usa |
| --- | --- |
| Min(dim_jugador.country) | detalle |
| Min(dim_jugador.player) | detalle, evolución valor |
| Min(dim_posicion.posicion) | detalle |
| Min(dim_valoracion.current_club_name) | detalle |
| Sum(dim_jugador.Edad en 2017) | detalle |
| Sum(dim_jugador.Edad en 2020) | jugadores |
| Sum(dim_jugador.height_in_cm) | detalle |
| Sum(fact_heatmap_jugador.location_x) | detalle |
| Sum(fact_heatmap_jugador.location_y) | detalle |
| dim_calendario.Anio | evolución valor |
| dim_calendario.Date.Variación.Jerarquía de fechas.Año | evolución valor |
| dim_jugador.Edad en 2020 | jugadores |
| dim_jugador.market_value_in_eur | jugadores |
| dim_jugador.player | jugadores |
| dim_jugador.player_id | jugadores |
| dim_jugador.posicion_habitual | jugadores |
| dim_metricas.metrica | detalle |
| dim_posicion.posicion | jugadores |
| dim_valoracion.current_club_name | evolución valor |
| fact_heatmap_jugador.tipo | detalle |
| medidas.Metrica Card 1 | detalle |
| medidas.Metrica Card 2 | detalle |
| medidas.Metrica Card 3 | detalle |
| medidas.Metrica Card 4 | detalle |
| medidas.Metrica Card 5 | detalle |
| medidas.Minutos Jugados | detalle, evolución valor |
| medidas.Posicion Seleccionada Texto | detalle |
| medidas.Score Unificado | jugadores |
| medidas.Score Unificado por Millon | jugadores |
| medidas.Valor Dinámico Mediana | detalle |
| medidas.Valor Dinámico Radar | detalle |
| medidas.Valor Mercado por Temporada | evolución valor |
| medidas.Valor de Mercado Actual | jugadores |

### Medidas definidas pero no usadas en el reporte

- `medidas.Total Pases`
- `medidas.score_d por millón de eur`
- `medidas.score_def por millón de eur`
- `medidas.score_lat por millón de eur`
- `medidas.score_m por millón de eur`
- `medidas_def.Carrys Progresivos Zona Media`
- `medidas_def.Carrys Zona Media por 90`
- `medidas_def.Duelos Zona Alta`
- `medidas_def.Duelos Zona Alta por 90`
- `medidas_def.Intercepciones CR por 90`
- `medidas_def.Intercepciones Campo Rival`
- `medidas_def.Pases Prog Atras por 90`
- `medidas_def.Pases Prog Desde Atras`
- `medidas_def.Pct Carrys Zona Media`
- `medidas_def.Pct Duelos Zona Alta`
- `medidas_def.Pct Intercepciones CR`
- `medidas_def.Pct Pases Prog Atras`
- `medidas_def.Score Defensor`
- `medidas_def.Valor Dinámico Jugador Def`
- `medidas_del.Desmarques por 90`
- `medidas_del.Dribbles`
- `medidas_del.Dribbles por 90`
- `medidas_del.Pct Desmarques`
- `medidas_del.Pct Dribbles`
- `medidas_del.Pct Presiones`
- `medidas_del.Pct Recepciones`
- `medidas_del.Pct xG`
- `medidas_del.Presiones Ultimo Tercio`
- `medidas_del.Presiones por 90`
- `medidas_del.Recepciones Campo Rival`
- `medidas_del.Recepciones por 90`
- `medidas_del.Score Delantero`
- `medidas_del.Total Desmarques Ruptura`
- `medidas_del.Valor Dinámico Jugador`
- `medidas_del.xG Sin Penal`
- `medidas_del.xG Sin Penal por 90`
- `medidas_lat.Conducciones Centro por 90`
- `medidas_lat.Conducciones Hacia Centro`
- `medidas_lat.Duelos Def por 90`
- `medidas_lat.Duelos Defensivos Ganados`
- `medidas_lat.Pases Adentro por 90`
- `medidas_lat.Pases Hacia Adentro`
- `medidas_lat.Pct Conducciones Centro`
- `medidas_lat.Pct Duelos Def`
- `medidas_lat.Pct Pases Adentro`
- `medidas_lat.Pct Presiones Banda`
- `medidas_lat.Presiones Banda por 90`
- `medidas_lat.Presiones En Banda`
- `medidas_lat.Score Lateral`
- `medidas_lat.Valor Dinámico Jugador Lat`
- `medidas_mid.Conducciones Prog por 90`
- `medidas_mid.Conducciones Progresivas`
- `medidas_mid.Pases Bajo Presion por 90`
- `medidas_mid.Pases Exitosos Bajo Presion`
- `medidas_mid.Pases Prog por 90`
- `medidas_mid.Pases Progresivos`
- `medidas_mid.Pct Conducciones Prog`
- `medidas_mid.Pct Pases Bajo Presion`
- `medidas_mid.Pct Pases Prog`
- `medidas_mid.Pct Perdidas`
- `medidas_mid.Pct Ratio Pases Prog`
- `medidas_mid.Perdidas de Balon`
- `medidas_mid.Perdidas por 90`
- `medidas_mid.Ratio Pases Prog`
- `medidas_mid.Score Mediocampista`
- `medidas_mid.Valor Dinámico Jugador Mid`

## Seguridad a nivel de fila (RLS)

_No se encontraron roles de seguridad._

## Metadatos del archivo

| Campo | Valor |
| --- | --- |
| Archivo | scouting_dashboard_v12.pbix |
| Versión PBIX | ? |
| Creado | ? |
| Modificado | ? |

### Archivos internos del .pbix

- `DataModel`
- `DiagramLayout`
- `Metadata`
- `Report/Layout`
- `Report/LinguisticSchema`
- `Report/StaticResources/SharedResources/BaseThemes/CY26SU05.json`
- `Report/StaticResources/SharedResources/BuiltInThemes/AccessibleNeutral.json`
- `SecurityBindings`
- `Settings`
- `Version`
- `[Content_Types].xml`

---
_Generado por pbix-reader v0.2.0 · 19/06/2026 15:58_