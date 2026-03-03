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
    # --- NUEVAS VARIABLES INSTITUCIONALES ---
    capital_inicial: float = Query(10000.0, description="Capital en USD"),
    slippage: float = Query(0.0005, description="Slippage del 0.05%")
):
    print(f"Auditando {ticker} con ${capital_inicial} USD | Slippage: {slippage}")
    
    # ... (el resto de tu código yf.download sigue igual por ahora) ...
    print(f"Auditando {ticker} con Stop-Loss del {sl}% y Take-Profit del {tp}%...")
    
    datos = yf.download(ticker, period="2y", interval="1d")
    if len(datos) == 0: return {"error": f"No se encontraron datos para {ticker}."}
    if isinstance(datos.columns, pd.MultiIndex): datos.columns = datos.columns.get_level_values(0)
        
    # 1. Filtros Técnicos Base
    datos['SMA_Rapida'] = datos['Close'].squeeze().rolling(window=sma_rapida).mean()
    datos['SMA_Lenta'] = datos['Close'].squeeze().rolling(window=sma_lenta).mean()
    
    delta = datos['Close'].squeeze().diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    datos['RSI'] = 100 - (100 / (1 + (ema_up / ema_down)))
    
    condicion_compra = (datos['SMA_Rapida'] > datos['SMA_Lenta']) & (datos['RSI'] > 50) & (datos['RSI'] < 75)
    datos['Senal_Tecnica'] = np.where(condicion_compra, 1.0, -1.0)
    
   # --- 🛡️ MOTOR DE RIESGO INSTITUCIONAL (CAPITAL Y SLIPPAGE) ---
    posicion_actual = 0
    precio_entrada = 0
    
    # Nuevas variables bancarias
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
                posicion_actual = 0  # El bot decide vender
                # VENTA REAL: El mercado nos paga un poco menos por el Slippage
                precio_ejecucion = precio_actual * (1 - slippage) 
                efectivo = acciones * precio_ejecucion
                acciones = 0  # Nos quedamos en dólares puros
                
        elif posicion_actual == -1:
            rendimiento = ((precio_entrada - precio_actual) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0 # El bot cierra el corto
                # (Simplificado por ahora para mantener el enfoque en Longs)

        # 2. Leer la estrategia técnica si estamos fuera del mercado (Cash)
        if posicion_actual == 0 and senal_tec != 0:
            posicion_actual = senal_tec
            if posicion_actual == 1:  # COMPRA LONG
                # COMPRA REAL: Pagamos un poco más caro por el Slippage
                precio_ejecucion = precio_actual * (1 + slippage)
                acciones = efectivo / precio_ejecucion # Compramos todas las acciones posibles
                efectivo = 0 # Nos quedamos sin dólares libres
            precio_entrada = precio_actual
            
        senales_finales.append(posicion_actual)
        
        # 3. Auditoría diaria: ¿Cuánto dinero tenemos HOY exactamente?
        capital_hoy = efectivo + (acciones * precio_actual)
        historial_capital.append(capital_hoy)

    # Inyectamos los nuevos datos a la tabla de Pandas
    datos['Senal'] = senales_finales
    datos['Capital_Total'] = historial_capital

    for i in range(len(datos)):
        precio_actual = float(datos['Close'].iloc[i])
        senal_tec = float(datos['Senal_Tecnica'].iloc[i])
        
        # Evaluar si el Freno de Emergencia o el Take-Profit deben saltar
        if posicion_actual == 1:
            rendimiento = ((precio_actual - precio_entrada) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0 # 🚨 El bot vende todo y se queda en dólares (Cash)
                
        elif posicion_actual == -1:
            rendimiento = ((precio_entrada - precio_actual) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0 # 🚨 El bot compra para cerrar el short y se queda en Cash

        # Si estamos fuera del mercado, leemos la estrategia técnica para volver a entrar
        if posicion_actual == 0 and senal_tec != 0:
            posicion_actual = senal_tec
            precio_entrada = precio_actual
            
        senales_finales.append(posicion_actual)

    datos['Senal'] = senales_finales
    
    # 3. Cálculo de Rendimientos con Comisiones
    datos['Cambio_Posicion'] = datos['Senal'].diff().abs()
    datos['Costo'] = np.where(datos['Cambio_Posicion'] > 0, 0.001, 0)
    
    datos['Retorno_Mercado'] = datos['Close'].squeeze().pct_change().fillna(0)
    datos['Retorno_Bruto'] = (datos['Retorno_Mercado'] * datos['Senal'].shift(1)).fillna(0)
    datos['Retorno_Neto'] = datos['Retorno_Bruto'] - datos['Costo']
    
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
            "Retorno_Neto": float(datos['Retorno_Neto'].iloc[i]), "Retorno_Mercado": float(datos['Retorno_Mercado'].iloc[i]),
            "Capital": float(datos['Capital_Total'].iloc[i]) # nuevo capital total 
        })
        
    return paquete_json