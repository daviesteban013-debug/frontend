from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np

app = FastAPI(title="Motor Quant Alpha", version="11.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def estado_servidor():
    return {"mensaje": "Servidor Quant con Gestión de Riesgo en línea."}

@app.get("/api/backtest")
def ejecutar_estrategia_en_vivo(
    ticker: str = Query("QQQ"),
    sma_rapida: int = Query(10),
    sma_lenta: int = Query(30),
    sl: float = Query(5.0, description="Stop-Loss %"),
    tp: float = Query(10.0, description="Take-Profit %"),
    capital_inicial: float = Query(10000.0, description="Capital en USD"),
    slippage: float = Query(0.0005, description="Slippage del 0.05%")
):
    print(f"Auditando {ticker} con ${capital_inicial} USD | Slippage: {slippage}")
    
    datos = yf.download(ticker, period="2y", interval="1d")
    if len(datos) == 0: return {"error": f"No se encontraron datos para {ticker}."}
    if isinstance(datos.columns, pd.MultiIndex): datos.columns = datos.columns.get_level_values(0)

    # 1. Filtros Técnicos Base
    datos['SMA_Rapida'] = datos['Close'].squeeze().rolling(window=sma_rapida).mean()
    datos['SMA_Lenta'] = datos['Close'].squeeze().rolling(window=sma_lenta).mean()

    # 2. Señales de Trading (Cruce de Medias)
    datos['Senal_Tecnica'] = 0
    datos.loc[datos['SMA_Rapida'] > datos['SMA_Lenta'], 'Senal_Tecnica'] = 1
    datos.loc[datos['SMA_Rapida'] < datos['SMA_Lenta'], 'Senal_Tecnica'] = -1

    # --- 🛡️ MOTOR DE RIESGO INSTITUCIONAL (CAPITAL Y SLIPPAGE) ---
    posicion_actual = 0
    precio_entrada = 0
    
    efectivo = capital_inicial
    acciones = 0
    historial_capital = []
    senales_finales = []

    for i in range(len(datos)):
        precio_actual = float(datos['Close'].iloc[i])
        senal_tec = float(datos['Senal_Tecnica'].iloc[i])
        
        # 1. Evaluar Freno de Emergencia (Stop-Loss) o Toma de Ganancias (Take-Profit)
        if posicion_actual == 1:
            rendimiento = ((precio_actual - precio_entrada) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0  
                # VENTA REAL con Slippage
                precio_ejecucion = precio_actual * (1 - slippage) 
                efectivo = acciones * precio_ejecucion
                acciones = 0  
                
        elif posicion_actual == -1:
            rendimiento = ((precio_entrada - precio_actual) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0 

        # 2. Leer la estrategia técnica si estamos fuera del mercado (Cash)
        if posicion_actual == 0 and senal_tec != 0:
            posicion_actual = senal_tec
            if posicion_actual == 1:  
                # COMPRA REAL con Slippage
                precio_ejecucion = precio_actual * (1 + slippage)
                acciones = efectivo / precio_ejecucion 
                efectivo = 0 
            precio_entrada = precio_actual
            
        senales_finales.append(posicion_actual)
        
        # 3. Auditoría diaria bancaria
        capital_hoy = efectivo + (acciones * precio_actual)
        historial_capital.append(capital_hoy)

    # Inyectamos los datos a Pandas
    datos['Senal'] = senales_finales
    datos['Capital_Total'] = historial_capital
    
    # --- Cálculo de retornos para las tarjetas de React ---
    datos['Retorno_Mercado'] = datos['Close'].squeeze().pct_change().fillna(0)
    # Calculamos el % de ganancia del bot basándonos en la mutación del dinero real
    datos['Retorno_Neto'] = pd.Series(historial_capital).pct_change().fillna(0).values

    # 4. Empaquetado OHLC para React
    datos = datos.fillna(0)
    datos.reset_index(inplace=True)
    datos['Date'] = datos['Date'].dt.strftime('%Y-%m-%d')

    paquete_json = []
    for i in range(len(datos)):
        paquete_json.append({
            "Date": str(datos['Date'].iloc[i]), "Open": float(datos['Open'].iloc[i]),
            "High": float(datos['High'].iloc[i]), "Low": float(datos['Low'].iloc[i]),
            "Close": float(datos['Close'].iloc[i]), "SMA_Rapida": float(datos['SMA_Rapida'].iloc[i]),
            "SMA_Lenta": float(datos['SMA_Lenta'].iloc[i]), "Senal": float(datos['Senal'].iloc[i]),
            "Retorno_Neto": float(datos['Retorno_Neto'].iloc[i]), 
            "Retorno_Mercado": float(datos['Retorno_Mercado'].iloc[i]),
            "Capital": float(datos['Capital_Total'].iloc[i]),
            "Volume": int(datos['Volume'].iloc[i]) 
        })

    return paquete_json