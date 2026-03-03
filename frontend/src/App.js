import React, { useState, useEffect } from 'react';
import Chart from 'react-apexcharts';

const Dashboard = () => {
  const [chartSeries, setChartSeries] = useState([]);
  const [metrics, setMetrics] = useState({ bot: "0.00", market: "0.00", drawdown: "0.00", winRate: "0.00", totalTrades: 0, sharpe: "0.00", capital: "10000.00" });
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  // ✨ VARIABLES DE ESTRATEGIA Y SCALPING
  const [ticker, setTicker] = useState("QQQ");
  const [intervalo, setIntervalo] = useState("5m"); // El microscopio de tiempo
  const [fastSma, setFastSma] = useState(10);
  const [slowSma, setSlowSma] = useState(30);
  const [stopLoss, setStopLoss] = useState(1.0); // Stop Loss bajo para Scalping
  const [takeProfit, setTakeProfit] = useState(2.0); // Take Profit rápido
  const [capitalInicial, setCapitalInicial] = useState(10000);

  const runBacktest = () => {
    setLoading(true);
    // ✨ ENLACE ACTUALIZADO CON LA FRECUENCIA (intervalo)
    const url = `https://first-api-ujhy.onrender.com/api/backtest?ticker=${ticker.toUpperCase()}&intervalo=${intervalo}&sma_rapida=${fastSma}&sma_lenta=${slowSma}&sl=${stopLoss}&tp=${takeProfit}&capital_inicial=${capitalInicial}`;
    
    fetch(url)
      .then(res => res.json())
      .then(datosApi => processData(datosApi))
      .catch(err => { console.error(err); setLoading(false); });
  };

  const processData = (datosApi) => {
        if (datosApi.error || !datosApi || datosApi.length === 0) return setLoading(false);

        const firstClose = datosApi[0].Close;
        const lastClose = datosApi[datosApi.length - 1].Close;
        const marketReturn = (((lastClose - firstClose) / firstClose) * 100).toFixed(2);

        let botMultiplier = 1; let peak = 1; let maxDrawdown = 0; 
        let currentPosition = 0; let entryPrice = 0; 
        let winningTrades = 0; let totalClosedTrades = 0;
        
        const tradeHistory = [];
        const candlestickData = []; const smaFastData = []; const smaSlowData = []; const volumeData = [];

        datosApi.forEach(row => {
            // Reconstruimos la fecha y HORA para el gráfico de Scalping
            const time = new Date(row.Date).getTime();
            candlestickData.push({ x: time, y: [row.Open, row.High, row.Low, row.Close] });
            smaFastData.push({ x: time, y: row.SMA_Rapida });
            smaSlowData.push({ x: time, y: row.SMA_Lenta });
            volumeData.push({ x: time, y: row.Volume || 0 }); 

            botMultiplier *= (1 + row.Retorno_Neto); 
            if (botMultiplier > peak) peak = botMultiplier;
            const currentDrawdown = (botMultiplier - peak) / peak;
            if (currentDrawdown < maxDrawdown) maxDrawdown = currentDrawdown;

            if (currentPosition !== 0 && row.Senal !== currentPosition) {
                totalClosedTrades++;
                let profitPercent = 0;

                if (currentPosition === 1) profitPercent = ((row.Close - entryPrice) / entryPrice) * 100;
                else if (currentPosition === -1) profitPercent = ((entryPrice - row.Close) / entryPrice) * 100;
                
                let tradeResult = ""; let tradeColor = "";
                if (profitPercent > 0) {
                    winningTrades++;
                    tradeResult = `+${profitPercent.toFixed(2)}%`; tradeColor = '#26a69a'; 
                } else {
                    tradeResult = `${profitPercent.toFixed(2)}%`; tradeColor = '#ef5350'; 
                }

                tradeHistory.push({
                    date: row.Date, type: row.Senal === 0 ? '🛑 SL/TP Ejecutado' : '🔄 Cierre/Reversión', 
                    price: row.Close, result: tradeResult, resultColor: tradeColor
                });
            }

            if (row.Senal !== currentPosition && row.Senal !== 0) {
                entryPrice = row.Close;
                tradeHistory.push({
                    date: row.Date,
                    type: row.Senal === 1 ? '🟢 BUY LONG' : '🔴 SELL SHORT',
                    price: row.Close, result: 'OPEN', resultColor: '#888'
                });
            }
            currentPosition = row.Senal;
        });

        const capitalFinal = datosApi[datosApi.length - 1].Capital || capitalInicial;
        const botReturn = (((capitalFinal - capitalInicial) / capitalInicial) * 100).toFixed(2);
        const sharpeFinal = datosApi[0].Sharpe !== undefined ? datosApi[0].Sharpe.toFixed(2) : "0.00";
        
        setMetrics({ 
            bot: botReturn, market: marketReturn, drawdown: (maxDrawdown * 100).toFixed(2), 
            winRate: totalClosedTrades > 0 ? ((winningTrades / totalClosedTrades) * 100).toFixed(2) : "0.00", 
            totalTrades: totalClosedTrades, 
            sharpe: sharpeFinal, 
            capital: capitalFinal.toFixed(2) 
        });

        // ✨ FILTRO ANTI-LAG: Solo dibujamos las últimas 300 velas para no explotar la RAM
        // El backtest matemático seguirá usando los miles de datos completos.
        const limiteVelas = -300; 

        setChartSeries([
            { name: 'Precio', type: 'candlestick', data: candlestickData.slice(limiteVelas) },
            { name: 'SMA Rápida', type: 'line', data: smaFastData.slice(limiteVelas) },
            { name: 'SMA Lenta', type: 'line', data: smaSlowData.slice(limiteVelas) },
            { name: 'Volumen', type: 'bar', data: volumeData.slice(limiteVelas) }
        ]);
        
        setTrades(tradeHistory.reverse()); setLoading(false);
  };

  useEffect(() => { runBacktest(); }, []);

// CONFIGURACIÓN DE GRÁFICA TIPO TRADINGVIEW
const chartOptions = {
  chart: { background: '#131722', toolbar: { show: true, tools: { download: false, selection: true, zoom: true, pan: true } }, animations: { enabled: false } },
  theme: { mode: 'dark' },
  colors: ['#26a69a', '#2962FF', '#FF6D00', '#2A2E39'], 
  stroke: { width: [1, 2, 2, 0], curve: 'smooth' },
  plotOptions: { candlestick: { colors: { upward: '#26a69a', downward: '#ef5350' }, wick: { useFillColor: true } }, bar: { columnWidth: '80%' } },
  xaxis: { type: 'datetime', tooltip: { enabled: true }, crosshairs: { show: true, stroke: { color: '#787B86', width: 1, dashArray: 4 } } },
  yaxis: [
    { seriesName: 'Precio', labels: { formatter: (val) => `$${val?.toFixed(2)}`, style: { colors: '#787B86' } }, tooltip: { enabled: true } },
    { seriesName: 'SMA Rápida', show: false }, 
    { seriesName: 'SMA Lenta', show: false },
    { seriesName: 'Volumen', opposite: true, labels: { formatter: (val) => `${(val / 1000000).toFixed(1)}M`, style: { colors: '#787B86' } } }
  ],
  grid: { borderColor: '#2A2E39', strokeDashArray: 3 }, dataLabels: { enabled: false }, legend: { position: 'top', horizontalAlign: 'left', labels: { colors: '#D1D4DC' } }
};

  return (
    <div style={{ backgroundColor: '#0B0E14', minHeight: '100vh', color: '#D1D4DC', fontFamily: 'Inter, system-ui, sans-serif', padding: '1.5vw 3vw' }}>
      
      {/* 🚀 HEADER */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid #2A2E39`, paddingBottom: '15px', marginBottom: '25px' }}>
        <div>
          <h1 style={{ fontSize: '24px', margin: 0, fontWeight: '800', color: '#FFF' }}>NEXUS QUANT <span style={{color: '#B388FF'}}>.HFT</span></h1>
          <p style={{ margin: '4px 0 0 0', color: '#787B86', fontSize: '13px' }}>Motor de Scalping de Alta Frecuencia</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(179, 136, 255, 0.1)', padding: '6px 14px', borderRadius: '4px', border: '1px solid rgba(179, 136, 255, 0.3)' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#B388FF', boxShadow: `0 0 8px #B388FF` }}></div>
          <span style={{ color: '#B388FF', fontSize: '12px', fontWeight: 'bold', letterSpacing: '1px' }}>HFT LIVE</span>
        </div>
      </header>

      {/* 🎛️ PANEL DE CONTROL HFT */}
      <div style={{ background: '#131722', borderRadius: '8px', border: '1px solid #2A2E39', padding: '15px 25px', display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'flex-end', marginBottom: '25px', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}><label style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>TICKER</label><input type="text" value={ticker} onChange={(e) => setTicker(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid #2A2E39', background: '#0B0E14', color: '#2962FF', fontWeight: 'bold', width: '80px', outline: 'none' }} /></div>
        
        {/* ✨ AQUÍ ESTÁ EL SELECTOR DE TIEMPO (TIMEFRAME) ✨ */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '11px', color: '#B388FF', fontWeight: 'bold' }}>TIMEFRAME</label>
            <select value={intervalo} onChange={(e) => setIntervalo(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid rgba(179, 136, 255, 0.5)', background: '#0B0E14', color: '#B388FF', fontWeight: 'bold', width: '70px', outline: 'none', cursor: 'pointer' }}>
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="1d">1d</option>
            </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}><label style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>FAST SMA</label><input type="number" value={fastSma} onChange={(e) => setFastSma(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid #2A2E39', background: '#0B0E14', color: '#FFF', width: '60px', outline: 'none' }} /></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}><label style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>SLOW SMA</label><input type="number" value={slowSma} onChange={(e) => setSlowSma(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid #2A2E39', background: '#0B0E14', color: '#FFF', width: '60px', outline: 'none' }} /></div>
        
        <div style={{ width: '1px', height: '35px', background: '#2A2E39', margin: '0 5px' }}></div> 

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}><label style={{ fontSize: '11px', color: '#ef5350', fontWeight: 'bold' }}>STOP-LOSS %</label><input type="number" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid rgba(239, 83, 80, 0.3)', background: '#0B0E14', color: '#FFF', width: '70px', outline: 'none' }} /></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}><label style={{ fontSize: '11px', color: '#26a69a', fontWeight: 'bold' }}>TAKE-PROFIT %</label><input type="number" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid rgba(38, 166, 154, 0.3)', background: '#0B0E14', color: '#FFF', width: '70px', outline: 'none' }} /></div>
        
        <div style={{ width: '1px', height: '35px', background: '#2A2E39', margin: '0 5px' }}></div> 

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '11px', color: '#FFD700', fontWeight: 'bold' }}>CAPITAL (USD)</label>
            <input type="number" value={capitalInicial} onChange={(e) => setCapitalInicial(e.target.value)} style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid rgba(255, 215, 0, 0.5)', background: '#0B0E14', color: '#FFD700', fontWeight: 'bold', width: '100px', outline: 'none' }} />
        </div>

        <button onClick={runBacktest} style={{ marginLeft: 'auto', padding: '10px 24px', borderRadius: '4px', background: '#B388FF', color: '#000', fontWeight: 'bold', border: 'none', cursor: 'pointer', transition: 'background 0.2s', fontSize: '13px' }} onMouseOver={(e) => e.target.style.background = '#8c5cf6'} onMouseOut={(e) => e.target.style.background = '#B388FF'}>
          EXECUTE SCALPING
        </button>
      </div>

      {loading ? ( <div style={{ height: '50vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}><div style={{ color: '#B388FF', fontSize: '18px', fontWeight: 'bold', letterSpacing: '2px' }}>SYNCING HIGH FREQUENCY DATA...</div></div> ) : (
        <>
          {/* 📊 MATRIZ SUPERIOR DE MÉTRICAS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '15px', marginBottom: '25px' }}>
            
            <div style={{ background: '#131722', padding: '20px', borderRadius: '8px', borderLeft: `4px solid #FFD700`, border: '1px solid #2A2E39' }}>
              <span style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>NET EQUITY (USD)</span>
              <h2 style={{ fontSize: '28px', margin: '8px 0 0 0', color: '#FFD700', fontFamily: 'monospace' }}>${metrics.capital}</h2>
            </div>

            <div style={{ background: '#131722', padding: '20px', borderRadius: '8px', borderLeft: `4px solid #26a69a`, border: '1px solid #2A2E39' }}>
              <span style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>BOT RETURN</span>
              <h2 style={{ fontSize: '28px', margin: '8px 0 0 0', color: '#26a69a', fontFamily: 'monospace' }}>{metrics.bot}%</h2>
            </div>
            
            <div style={{ background: 'linear-gradient(145deg, #131722 0%, #1a1e29 100%)', padding: '20px', borderRadius: '8px', borderLeft: `4px solid #E0E0E0`, border: '1px solid rgba(224, 224, 224, 0.2)', boxShadow: '0 0 15px rgba(224, 224, 224, 0.05)' }}>
              <span style={{ fontSize: '11px', color: '#E0E0E0', fontWeight: 'bold', letterSpacing: '1px' }}>SHARPE RATIO</span>
              <h2 style={{ fontSize: '28px', margin: '8px 0 0 0', color: '#FFF', fontFamily: 'monospace' }}>
                {metrics.sharpe} <span style={{fontSize: '14px', color: metrics.sharpe > 1 ? '#26a69a' : '#787B86'}}>{metrics.sharpe > 1 ? '🔥 ALPHA' : ''}</span>
              </h2>
            </div>
            
            <div style={{ background: '#131722', padding: '20px', borderRadius: '8px', borderLeft: `4px solid #ef5350`, border: '1px solid #2A2E39' }}>
              <span style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>MAX DRAWDOWN</span>
              <h2 style={{ fontSize: '28px', margin: '8px 0 0 0', color: '#ef5350', fontFamily: 'monospace' }}>{metrics.drawdown}%</h2>
            </div>
            
            <div style={{ background: '#131722', padding: '20px', borderRadius: '8px', borderLeft: `4px solid #B388FF`, border: '1px solid #2A2E39' }}>
              <span style={{ fontSize: '11px', color: '#787B86', fontWeight: 'bold' }}>WIN RATE</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '8px 0 0 0' }}>
                <h2 style={{ fontSize: '28px', margin: 0, color: '#B388FF', fontFamily: 'monospace' }}>{metrics.winRate}%</h2>
                <span style={{ color: '#787B86', fontSize: '12px' }}>/ {metrics.totalTrades}</span>
              </div>
            </div>

          </div>

          {/* 📈 WORKSPACE PRINCIPAL */}
          <div style={{ display: 'grid', gridTemplateColumns: '70% 28%', gap: '2%', alignItems: 'start' }}>
            
            <div style={{ background: '#131722', borderRadius: '8px', border: '1px solid #2A2E39', padding: '10px', height: '600px' }}>
               <Chart options={chartOptions} series={chartSeries} height="100%" />
            </div>

            <div style={{ background: '#131722', borderRadius: '8px', border: '1px solid #2A2E39', height: '600px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '15px', borderBottom: `1px solid #2A2E39`, background: '#1E222D' }}>
                <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 'bold', color: '#FFF', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '4px', height: '14px', background: '#B388FF', display: 'inline-block', borderRadius: '2px' }}></span>
                  HFT ORDER LOG
                </h3>
              </div>
              
              <div style={{ overflowY: 'auto', flex: 1, padding: '0 5px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px', fontFamily: 'monospace' }}>
                  <thead style={{ position: 'sticky', top: 0, background: '#131722', zIndex: 1 }}>
                    <tr>
                      <th style={{ padding: '10px 15px', color: '#787B86', fontWeight: 'normal', borderBottom: `1px solid #2A2E39` }}>Date / Type</th>
                      <th style={{ padding: '10px 15px', color: '#787B86', fontWeight: 'normal', borderBottom: `1px solid #2A2E39`, textAlign: 'right' }}>Price / PNL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.length > 0 ? trades.map((trade, index) => (
                      <tr key={index} style={{ borderBottom: `1px solid #1E222D`, transition: 'background 0.2s' }} onMouseOver={(e) => e.currentTarget.style.background = '#1E222D'} onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}>
                        <td style={{ padding: '10px 15px' }}>
                          <div style={{ color: trade.resultColor === '#888' ? '#FFF' : '#787B86', fontWeight: trade.resultColor === '#888' ? 'bold' : 'normal' }}>{trade.type}</div>
                          {/* ✨ AHORA VERÁS LA HORA EXACTA EN EL LIBRO DE ÓRDENES */}
                          <div style={{ color: '#787B86', marginTop: '2px' }}>{trade.date}</div> 
                        </td>
                        <td style={{ padding: '10px 15px', textAlign: 'right' }}>
                          <div style={{ color: '#FFF', fontWeight: 'bold' }}>${trade.price.toFixed(2)}</div>
                          <div style={{ color: trade.resultColor, marginTop: '2px', fontWeight: 'bold', background: trade.result !== 'OPEN' ? `${trade.resultColor}20` : 'transparent', padding: '2px 4px', borderRadius: '4px', display: 'inline-block' }}>{trade.result}</div>
                        </td>
                      </tr>
                    )) : null}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </>
      )}
    </div>
  );
};

export default Dashboard;