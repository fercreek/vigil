import pandas as pd
import numpy as np

def calculate_pivot_points(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula los Pivot Points Clásicos basados en Velas Diarias (High, Low, Close).
    Los niveles calculados hoy aplican para las operaciones del día Siguiente.
    """
    df = df_daily.copy()
    
    # Asegurar que tenemos OHLVC
    req_cols = ['high', 'low', 'close']
    for col in req_cols:
        if col not in df.columns:
            raise ValueError(f"Falta la columna requerida: {col}")
            
    # Pivot (P) = (High + Low + Close) / 3
    df['pivot'] = (df['high'] + df['low'] + df['close']) / 3
    
    # Soportes y Resistencias Principales (S1/R1)
    df['r1'] = (df['pivot'] * 2) - df['low']
    df['s1'] = (df['pivot'] * 2) - df['high']
    
    # Soportes y Resistencias Secundarios (S2/R2)
    # R2 = P + (High - Low)
    # S2 = P - (High - Low)
    df['r2'] = df['pivot'] + (df['high'] - df['low'])
    df['s2'] = df['pivot'] - (df['high'] - df['low'])
    
    # Para scalping, los niveles macro nos importan. 
    # Mapearemos s1/s2 y r1/r2 para las zonas del plan
    return df

def aggregate_daily(df_hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte un DataFrame de histórico (1H o 15m) en velas Diarias 
    para extraer el High, Low, Close y aplicarles Pivot Points.
    """
    # Resamplear por Día ('1D') calculando max/min/last
    # OJO: Necesitamos calcular el pivote en el día D para aplicarlo en el día D+1
    df_daily = df_hourly.resample('1D').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    return df_daily

def map_levels_to_hourly(df_hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula los pivotes diarios y los "proyecta" (Shift+1) sobre 
    todas las velas intradiarias (1H/15m) correspondientes a ese día.
    """
    # 1. Agrupar la info macro diaria
    df_daily = aggregate_daily(df_hourly)
    
    # 2. Calcular pivotes diarios
    pivots_daily = calculate_pivot_points(df_daily)
    
    # 3. Mover los pivotes 1 día adelante (El pivot calculado el Martes rige el Miércoles)
    pivots_daily_shifted = pivots_daily[['pivot', 'r1', 's1', 'r2', 's2']].shift(1)
    
    # 4. Unir al dataset intradiario original basándose en la fecha del índice
    df = df_hourly.copy()
    df['date_only'] = df.index.normalize() # Extraer 00:00:00 para hacer el match
    
    # Hacemos merge (left) para que cada vela de 1H de hoy copie los PIVOTS_SHIFTED de hoy
    df_merged = df.merge(pivots_daily_shifted, left_on='date_only', right_index=True, how='left')
    
    # Limpiamos columna auxiliar y dropeamos NA (el día 1 no tendrá pivotes previos)
    df_merged = df_merged.drop(columns=['date_only']).dropna()
    
    return df_merged

if __name__ == "__main__":
    # Prueba local
    print("Módulo de Auto Niveles Dinámicos (Pivot Points) Listo.")
