from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np

app = FastAPI(title="Motor Quant Alpha", version="13.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def estado_servidor():
    return {"mensaje": "Servidor HFT Scalping en línea."}

@app.get("/api/backtest")
def ejecutar_estrategia_en_vivo(
    ticker: str = Query("QQQ"),
    intervalo: str = Query("5m", description="Temporalidad: 1m, 5m, 15m, 1h, 1d"), # ✨ NUEVO: Selector de tiempo
    sma_rapida: int = Query(10),
    sma_lenta: int = Query(30),
    sl: float = Query(1.0, description="Stop-Loss % (Bajo para Scalping)"),
    tp: float = Query(2.0, description="Take-Profit % (Bajo para Scalping)"),
    capital_inicial: float = Query(10000.0),
    # En Scalping el slippage debe ser microscópico o te come la cuenta
    slippage: float = Query(0.0001, description="Slippage Institucional 0.01%") 
):
    print(f"Scalping {ticker} en {intervalo} | Capital: ${capital_inicial}")
    
    # Lógica de Yahoo Finance: Datos de 1m solo permiten 7 días atrás. 5m permiten 60 días.
    if intervalo == "1m": period = "7d"
    elif intervalo in ["2m", "5m", "15m", "30m"]: period = "60d"
    else: period = "1y"

    datos = yf.download(ticker, period=period, interval=intervalo)
    if len(datos) == 0: return {"error": f"No se encontraron datos para {ticker} en {intervalo}."}
    if isinstance(datos.columns, pd.MultiIndex): datos.columns = datos.columns.get_level_values(0)

    datos['SMA_Rapida'] = datos['Close'].squeeze().rolling(window=sma_rapida).mean()
    datos['SMA_Lenta'] = datos['Close'].squeeze().rolling(window=sma_lenta).mean()

    datos['Senal_Tecnica'] = 0
    datos.loc[datos['SMA_Rapida'] > datos['SMA_Lenta'], 'Senal_Tecnica'] = 1  
    datos.loc[datos['SMA_Rapida'] < datos['SMA_Lenta'], 'Senal_Tecnica'] = -1 

    posicion_actual = 0
    precio_entrada = 0
    efectivo = capital_inicial
    acciones = 0
    historial_capital = []
    senales_finales = []

    for i in range(len(datos)):
        precio_actual = float(datos['Close'].iloc[i])
        senal_tec = float(datos['Senal_Tecnica'].iloc[i])
        
        if posicion_actual == 1: 
            rendimiento = ((precio_actual - precio_entrada) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0  
                precio_ejecucion = precio_actual * (1 - slippage) 
                efectivo = acciones * precio_ejecucion
                acciones = 0  
                
        elif posicion_actual == -1: 
            rendimiento = ((precio_entrada - precio_actual) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0 
                precio_ejecucion = precio_actual * (1 + slippage)
                ganancia_perdida = (precio_entrada - precio_ejecucion) * acciones
                efectivo = efectivo + ganancia_perdida
                acciones = 0

        if posicion_actual == 0 and senal_tec != 0:
            posicion_actual = senal_tec
            if posicion_actual == 1:  
                precio_ejecucion = precio_actual * (1 + slippage)
                acciones = efectivo / precio_ejecucion 
                precio_entrada = precio_ejecucion
                efectivo = 0 
            elif posicion_actual == -1: 
                precio_ejecucion = precio_actual * (1 - slippage)
                acciones = efectivo / precio_ejecucion 
                precio_entrada = precio_ejecucion
            
        senales_finales.append(posicion_actual)
        
        if posicion_actual == 1: capital_hoy = efectivo + (acciones * precio_actual)
        elif posicion_actual == -1: capital_hoy = efectivo + ((precio_entrada - precio_actual) * acciones)
        else: capital_hoy = efectivo

        historial_capital.append(capital_hoy)

    datos['Senal'] = senales_finales
    datos['Capital_Total'] = historial_capital
    datos['Retorno_Mercado'] = datos['Close'].squeeze().pct_change().fillna(0)
    datos['Retorno_Neto'] = pd.Series(historial_capital).pct_change().fillna(0).values

    desviacion = datos['Retorno_Neto'].std()
    sharpe_ratio = 0.0
    if desviacion > 0:
        sharpe_ratio = (datos['Retorno_Neto'].mean() / desviacion) * np.sqrt(252 * 78) # Ajustado para intradía

    datos = datos.fillna(0)
    datos.reset_index(inplace=True)
    
    # ✨ MAGIA DE SCALPING: Guardamos LA HORA EXACTA, no solo el día
    columna_fecha = datos.columns[0] 
    datos['Date'] = pd.to_datetime(datos[columna_fecha]).dt.strftime('%Y-%m-%d %H:%M:%S')

    paquete_json = []
    for i in range(len(datos)):
        paquete_json.append({
            "Date": str(datos['Date'].iloc[i]), "Open": float(datos['Open'].iloc[i]),
            "High": float(datos['High'].iloc[i]), "Low": float(datos['Low'].iloc[i]),
            "Close": float(datos['Close'].iloc[i]), "SMA_Rapida": float(datos['SMA_Rapida'].iloc[i]),
            "SMA_Lenta": float(datos['SMA_Lenta'].iloc[i]), "Senal": float(datos['Senal'].iloc[i]),
            "Retorno_Neto": float(datos['Retorno_Neto'].iloc[i]), "Retorno_Mercado": float(datos['Retorno_Mercado'].iloc[i]),
            "Capital": float(datos['Capital_Total'].iloc[i]), "Volume": int(datos['Volume'].iloc[i]),
            "Sharpe": float(sharpe_ratio) 
        })

    return paquete_json