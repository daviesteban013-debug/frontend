from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np

app = FastAPI(title="Motor Quant Alpha", version="12.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def estado_servidor():
    return {"mensaje": "Servidor Quant de Grado Institucional en línea."}

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

    # 1. Filtros Técnicos
    datos['SMA_Rapida'] = datos['Close'].squeeze().rolling(window=sma_rapida).mean()
    datos['SMA_Lenta'] = datos['Close'].squeeze().rolling(window=sma_lenta).mean()

    # 2. Señales de Trading Bi-Direccionales
    datos['Senal_Tecnica'] = 0
    datos.loc[datos['SMA_Rapida'] > datos['SMA_Lenta'], 'Senal_Tecnica'] = 1  # LONG
    datos.loc[datos['SMA_Rapida'] < datos['SMA_Lenta'], 'Senal_Tecnica'] = -1 # SHORT

    # --- 🛡️ MOTOR DE RIESGO: PREDADOR BAJISTA ---
    posicion_actual = 0
    precio_entrada = 0
    
    efectivo = capital_inicial
    acciones = 0
    historial_capital = []
    senales_finales = []

    for i in range(len(datos)):
        precio_actual = float(datos['Close'].iloc[i])
        senal_tec = float(datos['Senal_Tecnica'].iloc[i])
        
        # 1. Evaluar Freno de Emergencia o Toma de Ganancias
        if posicion_actual == 1: # Si estamos LONG
            rendimiento = ((precio_actual - precio_entrada) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0  
                precio_ejecucion = precio_actual * (1 - slippage) 
                efectivo = acciones * precio_ejecucion
                acciones = 0  
                
        elif posicion_actual == -1: # Si estamos SHORT
            # En Short, ganamos si el precio cae
            rendimiento = ((precio_entrada - precio_actual) / precio_entrada) * 100
            if rendimiento <= -sl or rendimiento >= tp:
                posicion_actual = 0 
                precio_ejecucion = precio_actual * (1 + slippage)
                # Ganancia = (Precio Venta Inicial - Precio Compra Final) * acciones prestadas
                ganancia_perdida = (precio_entrada - precio_ejecucion) * acciones
                efectivo = efectivo + ganancia_perdida
                acciones = 0

        # 2. Entrar al Mercado
        if posicion_actual == 0 and senal_tec != 0:
            posicion_actual = senal_tec
            if posicion_actual == 1:  # LONG ENTRY
                precio_ejecucion = precio_actual * (1 + slippage)
                acciones = efectivo / precio_ejecucion 
                precio_entrada = precio_ejecucion
                efectivo = 0 
            elif posicion_actual == -1: # SHORT ENTRY
                precio_ejecucion = precio_actual * (1 - slippage)
                acciones = efectivo / precio_ejecucion # Pedimos prestado este número de acciones
                precio_entrada = precio_ejecucion
                # El efectivo se queda como garantía (Collateral)
            
        senales_finales.append(posicion_actual)
        
        # 3. Auditoría diaria del Capital
        if posicion_actual == 1:
            capital_hoy = efectivo + (acciones * precio_actual)
        elif posicion_actual == -1:
            # Capital Short = Garantía + Ganancia/Pérdida Flotante
            ganancia_perdida_flotante = (precio_entrada - precio_actual) * acciones
            capital_hoy = efectivo + ganancia_perdida_flotante
        else:
            capital_hoy = efectivo

        historial_capital.append(capital_hoy)

    # Inyectamos los datos al DataFrame
    datos['Senal'] = senales_finales
    datos['Capital_Total'] = historial_capital
    datos['Retorno_Mercado'] = datos['Close'].squeeze().pct_change().fillna(0)
    datos['Retorno_Neto'] = pd.Series(historial_capital).pct_change().fillna(0).values

    # --- 📐 AUDITORÍA SHARPE RATIO ---
    desviacion_diaria = datos['Retorno_Neto'].std()
    # Asumimos Tasa Libre de Riesgo de 0% para simplificar el cálculo puro del bot
    sharpe_ratio = 0.0
    if desviacion_diaria > 0:
        # Multiplicamos por la raíz de 252 (días bursátiles del año) para anualizarlo
        sharpe_ratio = (datos['Retorno_Neto'].mean() / desviacion_diaria) * np.sqrt(252)

    # 4. Empaquetado
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
            "Capital": float(datos['Capital_Total'].iloc[i]), "Volume": int(datos['Volume'].iloc[i]),
            "Sharpe": float(sharpe_ratio) # Inyectamos el Sharpe al Frontend
        })

    return paquete_json