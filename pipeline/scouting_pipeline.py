# Primero clonamos el repositorio de StatsBomb (Datos en crudo si se necesitan)
# !git clone https://github.com/statsbomb/open-data.git

# !pip install statsbombpy
from statsbombpy import sb
import pandas as pd
import numpy as np

# ------------------------------------------------------------------------------
# 1. TRAER LA LISTA DE COMPETENCIAS Y FILTRAR OBJETIVOS
# ------------------------------------------------------------------------------
# España: 18/19 (ID 4), 19/20 (ID 42), 20/21 (ID 90), 21/22 (ID 108)
objetivos_scouting = [
    {"comp_id": 11, "seas_id": 4,  "liga_nombre": "La Liga 18/19"},
    {"comp_id": 11, "seas_id": 42, "liga_nombre": "La Liga 19/20"},
    {"comp_id": 11, "seas_id": 90, "liga_nombre": "La Liga 20/21"},
    {"comp_id": 11, "seas_id": 108, "liga_nombre": "La Liga 21/22"}
]

data_master_scouting = []

print("🚀 Iniciando proceso de extracción masiva multiliga...")

for objetivo in objetivos_scouting:
    c_id = objetivo["comp_id"]
    s_id = objetivo["seas_id"]
    nombre_torneo = objetivo["liga_nombre"]
    
    print(f"\n➔ Procesando: {nombre_torneo}...")
    
    # Traer partidos de esta combinación específica
    try:
        partidos = sb.matches(competition_id=c_id, season_id=s_id)
        lista_match_ids = partidos['match_id'].tolist()
        print(f"   Se encontraron {len(lista_match_ids)} partidos.")
    except Exception as e:
        print(f"   Error al traer partidos de {nombre_torneo}: {e}")
        continue
        
    # Recorrer cada partido de este torneo
    for i, m_id in enumerate(lista_match_ids):
        try:
            # Imprimir contador de progreso para monitorear la descarga
            print(f"   [Partido {i+1}/{len(lista_match_ids)}] Descargando ID: {m_id}...", end="\r")
            
            eventos_partido = sb.events(match_id=m_id)
            
            # Filtramos eventos indispensables de rendimiento técnico-táctico
            eventos_interes = eventos_partido[eventos_partido['type'].isin(['Pass', 'Shot', 'Duel', 'Interception', 'Clearance'])]
            
            # Columnas clave seleccionadas para el modelo táctico y de contexto
            columnas_filtro = [
                # Contexto básico del evento
                'match_id', 'period', 'minute', 'timestamp', 'team', 'player', 'position', 'type', 'under_pressure', 'counterpress',
                # Datos de Pases
                'pass_outcome', 'pass_length', 'pass_shot_assist', 'pass_recipient', 'pass_assisted_shot_id', 'pass_goal_assist',
                # Datos de Tiros (Scoring)
                'shot_statsbomb_xg', 'shot_outcome', 'shot_technique', 'shot_key_pass_id',
                # Datos de Duelos e Intercepciones
                'duel_type', 'duel_outcome', 'interception_outcome'
            ]
            
            columnas_validas = [col for col in columnas_filtro if col in eventos_interes.columns]
            df_filtrado = eventos_interes[columnas_validas].copy()
            
            # Agregamos etiquetas del torneo para poder segmentar en Power BI
            df_filtrado['liga_origen'] = nombre_torneo
            
            data_master_scouting.append(df_filtrado)
            
        except Exception as e:
            # Si un partido falla, el script continúa con el siguiente sin detenerse
            continue
            
    print(f"\n   ✔ {nombre_torneo} finalizado con éxito.")

# ------------------------------------------------------------------------------
# 2. UNIFICACIÓN DE FUENTES DE DATOS
# ------------------------------------------------------------------------------
print("\nUnificando todas las fuentes de datos en el DataFrame Master...")
df_final_scouting = pd.concat(data_master_scouting, ignore_index=True)

# ------------------------------------------------------------------------------
# 3. LIMPIEZA DE NULOS Y TRATAMIENTO DE MÉTRICAS (Mapeo Regional Power BI)
# ------------------------------------------------------------------------------
print("Ejecutando reglas de limpieza y transformaciones métricas...")

# Rellenar nulos categóricos para evitar problemas con DAX
df_final_scouting['pass_outcome'] = df_final_scouting['pass_outcome'].fillna('Complete')
df_final_scouting['duel_outcome'] = df_final_scouting['duel_outcome'].fillna('Success')
df_final_scouting['interception_outcome'] = df_final_scouting['interception_outcome'].fillna('Success')
df_final_scouting['shot_statsbomb_xg'] = df_final_scouting['shot_statsbomb_xg'].fillna(0)

# Métricas binarias (Flags para agilizar cálculos directos como SUM en Power BI)
df_final_scouting['es_gol'] = np.where(df_final_scouting['shot_outcome'] == 'Goal', 1, 0)
df_final_scouting['es_asistencia'] = np.where(df_final_scouting['pass_goal_assist'] == True, 1, 0)

# Tratamiento crítico de Distancia de Pases (Conversión de Yardas a Metros)
# NOTA: Se llenan nulos primero para asegurar consistencia del tipo de dato numérico float
df_final_scouting['pass_length'] = df_final_scouting['pass_length'].fillna(0)
df_final_scouting['pass_length'] = (df_final_scouting['pass_length'] * 0.9144).round(2)

# Tratamiento de Presión y Contrapresión (Evitar strings 'null' y fijar booleanos)
df_final_scouting['under_pressure'] = df_final_scouting['under_pressure'].fillna(False)
df_final_scouting['counterpress'] = df_final_scouting['counterpress'].fillna(False)

# ------------------------------------------------------------------------------
# 4. EXPORTACIÓN DEL DATASET CONSOLIDADO
# ------------------------------------------------------------------------------
archivo_salida = 'statsbomb_master_scouting_europa.csv'
df_final_scouting.to_csv(archivo_salida, index=False)

print(f"\n🎯 ¡Proceso completado con éxito!")
print(f"Filas totales consolidadas: {df_final_scouting.shape[0]}")
print(f"El archivo '{archivo_salida}' está listo para usar en tu tablero.")