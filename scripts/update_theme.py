import os

html_content = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JEPA Crypto Trading Terminal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: { sans: ['Inter', 'sans-serif'] },
                    colors: {
                        theme: {
                            bg: 'var(--bg-color)',
                            card: 'var(--card-bg)',
                            border: 'var(--border-color)',
                            text: 'var(--text-main)',
                            muted: 'var(--text-muted)',
                            hover: 'var(--hover-bg)'
                        }
                    },
                    animation: { 'fadeIn': 'fadeIn 0.4s ease-out forwards' },
                    keyframes: {
                        fadeIn: {
                            '0%': { opacity: '0', transform: 'translateY(10px)' },
                            '100%': { opacity: '1', transform: 'translateY(0)' },
                        }
                    }
                }
            }
        }
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.2/d3.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.21.2/babel.min.js"></script>
    <style>
        :root {
            --bg-color: #F8FAFC;
            --card-bg: #FFFFFF;
            --border-color: #E2E8F0;
            --text-main: #0F172A;
            --text-muted: #64748B;
            --hover-bg: #F1F5F9;
            --chart-grid: rgba(148, 163, 184, 0.3);
            --chart-tooltip-bg: rgba(255, 255, 255, 0.95);
            --chart-tooltip-border: #E2E8F0;
        }
        .dark {
            --bg-color: #111827;
            --card-bg: #1F2937;
            --border-color: #374151;
            --text-main: #F9FAFB;
            --text-muted: #9CA3AF;
            --hover-bg: rgba(31, 41, 55, 0.8);
            --chart-grid: rgba(55, 65, 81, 0.4);
            --chart-tooltip-bg: rgba(17, 24, 39, 0.95);
            --chart-tooltip-border: #374151;
        }
        
        body { background-color: var(--bg-color); color: var(--text-main); font-family: 'Inter', sans-serif; transition: background-color 0.3s ease, color 0.3s ease; }
        
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            border-radius: 1rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background-color 0.3s ease;
        }
        .card:hover {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
            border-color: #3B82F6;
            transform: translateY(-2px);
        }
        .chart-container { position: relative; height: 320px; width: 100%; }
        .tooltip { position: absolute; padding: 16px; background: var(--chart-tooltip-bg); color: var(--text-main); border: 1px solid var(--chart-tooltip-border); border-radius: 12px; pointer-events: none; z-index: 1000; font-size: 13px; backdrop-filter: blur(8px); box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); transition: background-color 0.3s, color 0.3s, border-color 0.3s; }
        .status-dot { animation: pulse 2s infinite; }
        @keyframes pulse { 0%{transform:scale(1);opacity:1;box-shadow:0 0 0 0 rgba(16,185,129,0.7)} 70%{transform:scale(1);opacity:0.8;box-shadow:0 0 0 6px rgba(16,185,129,0)} 100%{transform:scale(1);opacity:1;box-shadow:0 0 0 0 rgba(16,185,129,0)} }
        .status-dot.error { animation: pulse-error 2s infinite; }
        @keyframes pulse-error { 0%{transform:scale(1);opacity:1;box-shadow:0 0 0 0 rgba(239,68,68,0.7)} 70%{transform:scale(1);opacity:0.8;box-shadow:0 0 0 6px rgba(239,68,68,0)} 100%{transform:scale(1);opacity:1;box-shadow:0 0 0 0 rgba(239,68,68,0)} }
        .rsi-value { display:inline-block; padding:0.25rem 0.6rem; margin:0.25rem; border-radius:0.375rem; background:var(--card-bg); border: 1px solid var(--border-color); font-family:monospace; font-size: 0.875rem; transition: all 0.2s; cursor: default; }
        .rsi-value:hover { transform: scale(1.05); border-color: #3B82F6; }
        .rsi-value.overbought { background:rgba(239,68,68,0.1); color:#EF4444; border-color: rgba(239,68,68,0.3); }
        .rsi-value.oversold { background:rgba(16,185,129,0.1); color:#10B981; border-color: rgba(16,185,129,0.3); }
        .stat-value { font-size:1.75rem; font-weight:700; letter-spacing:-0.025em; font-family: 'Inter', sans-serif; color: var(--text-main); } 
        .stat-label { font-size:0.75rem; color:var(--text-muted); margin-bottom:0.25rem; font-weight:600; text-transform: uppercase; letter-spacing: 0.05em; }
        .risk-badge { display:inline-block; padding:2px 10px; border-radius:9999px; font-size:0.7rem; font-weight:700; letter-spacing:0.05em; }
        .risk-badge.active { background:rgba(239,68,68,0.15); color:#EF4444; border: 1px solid rgba(239,68,68,0.3); } 
        .risk-badge.ok { background:rgba(16,185,129,0.15); color:#10B981; border: 1px solid rgba(16,185,129,0.3); }
        
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
        
        .tab-btn { position: relative; transition: all 0.3s ease; }
        .tab-btn::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 0%; height: 2px; background-color: #3B82F6; transition: width 0.3s ease; }
        .tab-btn.active { color: #3B82F6; }
        .tab-btn.active::after { width: 100%; }
        
        table th { position: sticky; top: 0; background: var(--bg-color); z-index: 10; box-shadow: 0 1px 0 var(--border-color); }
        
        .chart-grid line { stroke: var(--chart-grid); stroke-dasharray: 4,4; }
        .chart-axis text { fill: var(--text-muted); font-family: 'Inter', sans-serif; font-size: 11px; }
        .chart-axis path, .chart-axis line { stroke: transparent; }
    </style>
</head>
<body class="antialiased selection:bg-blue-500/30 selection:text-blue-500">
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect, useRef } = React;

        const App = () => {
            const [priceData, setPriceData] = useState([]);
            const [tradingActions, setTradingActions] = useState([]);
            const [predictions, setPredictions] = useState(null);
            const [indicators, setIndicators] = useState({});
            const [portfolio, setPortfolio] = useState(null);
            const [riskState, setRiskState] = useState(null);
            const [symbol, setSymbol] = useState("BTCUSDT");
            const [connected, setConnected] = useState(false);
            const [currentPrice, setCurrentPrice] = useState(null);
            const [activeTab, setActiveTab] = useState('overview');
            const [isDark, setIsDark] = useState(true);
            const wsRef = useRef(null);
            const tooltipRef = useRef(null);
            const actionsEndRef = useRef(null);

            useEffect(() => {
                if (isDark) {
                    document.documentElement.classList.add('dark');
                } else {
                    document.documentElement.classList.remove('dark');
                }
            }, [isDark]);

            useEffect(() => {
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.close();
                }

                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;
                wsRef.current = new WebSocket(wsUrl);

                wsRef.current.onopen = () => setConnected(true);
                wsRef.current.onclose = () => setConnected(false);
                wsRef.current.onerror = (error) => setConnected(false);

                wsRef.current.onmessage = (event) => {
                    let data = {};
                    try { data = JSON.parse(event.data); } catch (err) { return; }

                    if (data.price_history) {
                        setPriceData(data.price_history);
                        if (data.price_history.length > 0) setCurrentPrice(data.price_history[data.price_history.length - 1].price);
                    }
                    if (data.trading_actions) setTradingActions(data.trading_actions);
                    if (data.model_predictions) setPredictions(data.model_predictions);
                    if (data.indicators) setIndicators(data.indicators);
                    if (data.portfolio) setPortfolio(data.portfolio);
                    if (data.risk) setRiskState(data.risk);
                };

                return () => { if (wsRef.current) wsRef.current.close(); };
            }, [symbol]);

            useEffect(() => {
                if (activeTab === 'history' && actionsEndRef.current) {
                    actionsEndRef.current.scrollIntoView({ behavior: "smooth" });
                }
            }, [tradingActions, activeTab]);

            const handleSymbolChange = (e) => {
                const newSymbol = e.target.value.toUpperCase();
                setSymbol(newSymbol);
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({ action: 'change_symbol', symbol: newSymbol }));
                }
            };
            
            const toggleTheme = () => setIsDark(!isDark);

            const PriceChart = ({ priceData, tradingActions, isDark }) => {
                const svgRef = useRef();

                useEffect(() => {
                    if (!priceData.length) return;
                    const width = svgRef.current.parentElement.clientWidth;
                    const height = 320;
                    const margin = { top: 20, right: 20, bottom: 30, left: 60 };
                    const innerWidth = width - margin.left - margin.right;
                    const innerHeight = height - margin.top - margin.bottom;

                    d3.select(svgRef.current).selectAll("*").remove();
                    const xScale = d3.scaleTime()
                        .domain(d3.extent(priceData, d => new Date(d.timestamp)))
                        .range([0, innerWidth]);

                    const yScale = d3.scaleLinear()
                        .domain([d3.min(priceData, d => d.price) * 0.995, d3.max(priceData, d => d.price) * 1.005])
                        .range([innerHeight, 0]);

                    const svg = d3.select(svgRef.current).attr("width", width).attr("height", height);
                    
                    const defs = svg.append("defs");
                    const gradient = defs.append("linearGradient")
                        .attr("id", "price-gradient")
                        .attr("x1", "0%").attr("y1", "0%")
                        .attr("x2", "0%").attr("y2", "100%");
                    gradient.append("stop").attr("offset", "0%").attr("stop-color", "#3B82F6").attr("stop-opacity", 0.3);
                    gradient.append("stop").attr("offset", "100%").attr("stop-color", "#3B82F6").attr("stop-opacity", 0.0);

                    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

                    g.append("g").attr("transform", `translate(0,${innerHeight})`)
                     .attr("class", "chart-axis")
                     .call(d3.axisBottom(xScale).ticks(5));
                     
                    g.append("g")
                     .attr("class", "chart-axis")
                     .call(d3.axisLeft(yScale).tickFormat(d => `$${d.toLocaleString()}`));

                    g.append("g").attr("class", "chart-grid")
                        .call(d3.axisLeft(yScale).tickSize(-innerWidth).tickFormat(""));

                    const area = d3.area()
                        .x(d => xScale(new Date(d.timestamp)))
                        .y0(innerHeight)
                        .y1(d => yScale(d.price));
                        
                    g.append("path")
                        .datum(priceData)
                        .attr("fill", "url(#price-gradient)")
                        .attr("d", area);

                    const line = d3.line()
                        .x(d => xScale(new Date(d.timestamp)))
                        .y(d => yScale(d.price));

                    g.append("path")
                        .datum(priceData)
                        .attr("fill", "none")
                        .attr("stroke", "#3B82F6")
                        .attr("stroke-width", 2.5)
                        .attr("d", line);

                    const actionColor = { 'buy': '#10B981', 'sell': '#EF4444', 'hold': '#F59E0B' };
                    const pointStrokeColor = isDark ? '#1F2937' : '#FFFFFF';
                    
                    g.selectAll(".action-point")
                        .data(tradingActions)
                        .enter()
                        .append("circle")
                        .attr("class", "action-point cursor-pointer")
                        .attr("cx", d => xScale(new Date(d.timestamp)))
                        .attr("cy", d => yScale(d.price))
                        .attr("r", 5) 
                        .attr("fill", d => actionColor[d.action])
                        .attr("stroke", pointStrokeColor)
                        .attr("stroke-width", 2)
                        .on("mouseover", (event, d) => {
                            d3.select(event.currentTarget).attr("r", 7).attr("stroke", "#3B82F6");
                            tooltipRef.current
                                .style("opacity", 1)
                                .html(`
                                    <div class='space-y-1.5'>
                                        <div class='flex items-center gap-2 mb-3'>
                                            <span class='w-2.5 h-2.5 rounded-full' style='background:${actionColor[d.action]}'></span>
                                            <strong class='uppercase tracking-widest text-[var(--text-main)] text-xs font-semibold'>${d.action} SIGNAL</strong>
                                        </div>
                                        <div class='flex justify-between gap-6'><span class='text-[var(--text-muted)]'>Execution Price</span> <strong class='text-[var(--text-main)] font-mono'>$${parseFloat(d.price).toFixed(2)}</strong></div>
                                        <div class='flex justify-between gap-6'><span class='text-[var(--text-muted)]'>Timestamp</span> <strong class='text-[var(--text-main)] font-mono'>${new Date(d.timestamp).toLocaleTimeString()}</strong></div>
                                        <div class='mt-3 pt-3 border-t border-[var(--border-color)] text-[var(--text-muted)] text-xs italic leading-relaxed'>${d.reason}</div>
                                    </div>
                                `)
                                .style("left", `${event.pageX + 20}px`)
                                .style("top", `${event.pageY - 50}px`);
                        })
                        .on("mouseout", (event) => {
                            d3.select(event.currentTarget).attr("r", 5).attr("stroke", pointStrokeColor);
                            tooltipRef.current.style("opacity", 0);
                        });
                }, [priceData, tradingActions, isDark]);

                return (
                    <div className="chart-container">
                        <svg ref={svgRef}></svg>
                        <div className="tooltip" ref={el => tooltipRef.current = d3.select(el)} style={{opacity: 0}}></div>
                    </div>
                );
            };

            const EquityCurve = ({ portfolio, isDark }) => {
                const svgRef = useRef();
                useEffect(() => {
                    if (!portfolio || !portfolio.equity_curve || portfolio.equity_curve.length < 2) return;
                    const data = portfolio.equity_curve;
                    const width = svgRef.current.parentElement.clientWidth;
                    const height = 320;
                    const margin = { top: 20, right: 20, bottom: 30, left: 60 };
                    const iW = width - margin.left - margin.right;
                    const iH = height - margin.top - margin.bottom;
                    
                    d3.select(svgRef.current).selectAll('*').remove();
                    const xScale = d3.scaleTime().domain(d3.extent(data, d => new Date(d.timestamp))).range([0, iW]);
                    const yScale = d3.scaleLinear().domain([d3.min(data, d => d.equity) * 0.998, d3.max(data, d => d.equity) * 1.002]).range([iH, 0]);
                    const svg = d3.select(svgRef.current).attr('width', width).attr('height', height);
                    
                    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
                    
                    g.append('g').attr('transform', `translate(0,${iH})`).attr("class", "chart-axis").call(d3.axisBottom(xScale).ticks(5));
                    g.append('g').attr("class", "chart-axis").call(d3.axisLeft(yScale).ticks(5).tickFormat(d => `$${d.toLocaleString()}`));
                    
                    g.append("g").attr("class", "chart-grid")
                        .call(d3.axisLeft(yScale).tickSize(-iW).tickFormat(""));

                    const baseline = portfolio.initial_capital;
                    g.append('line').attr('x1',0).attr('x2',iW).attr('y1',yScale(baseline)).attr('y2',yScale(baseline)).attr('stroke','var(--border-color)').attr('stroke-dasharray','4,4').attr('stroke-width',1.5);
                    
                    const area = d3.area().x(d => xScale(new Date(d.timestamp))).y0(iH).y1(d => yScale(d.equity));
                    const lastEq = data[data.length-1].equity;
                    const color = lastEq >= baseline ? '#10B981' : '#EF4444';
                    
                    const defs = svg.append("defs");
                    const gradient = defs.append("linearGradient")
                        .attr("id", "equity-gradient")
                        .attr("x1", "0%").attr("y1", "0%")
                        .attr("x2", "0%").attr("y2", "100%");
                    gradient.append("stop").attr("offset", "0%").attr("stop-color", color).attr("stop-opacity", 0.3);
                    gradient.append("stop").attr("offset", "100%").attr("stop-color", color).attr("stop-opacity", 0.0);

                    g.append('path').datum(data).attr('fill', 'url(#equity-gradient)').attr('d', area);
                    
                    const line = d3.line().x(d => xScale(new Date(d.timestamp))).y(d => yScale(d.equity));
                    g.append('path').datum(data).attr('fill','none').attr('stroke', color).attr('stroke-width',2.5).attr('d', line);
                    
                }, [portfolio, isDark]);
                
                if (!portfolio || !portfolio.equity_curve || portfolio.equity_curve.length < 2) return <div className="text-theme-muted text-center py-20 flex flex-col items-center justify-center h-full"><svg className="w-10 h-10 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg><p>Equity curve will populate after trades execute</p></div>;
                return <div className="chart-container"><svg ref={svgRef}></svg></div>;
            };

            const PortfolioSummary = ({ portfolio, riskState }) => {
                if (!portfolio) return <div className="text-theme-muted text-center py-10 animate-pulse">Synchronizing portfolio data...</div>;
                const p = portfolio;
                const isProfit = p.total_return_pct >= 0;
                return (
                    <div>
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Total Equity</div>
                                <div className={`stat-value ${isProfit ? 'text-emerald-500' : 'text-red-500'}`}>${p.total_equity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                            </div>
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Total Return</div>
                                <div className={`stat-value ${isProfit ? 'text-emerald-500' : 'text-red-500'}`}>{isProfit ? '+' : ''}{p.total_return_pct.toFixed(2)}%</div>
                            </div>
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Realized PnL</div>
                                <div className={`stat-value ${p.realized_pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>${p.realized_pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                            </div>
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Unrealized PnL</div>
                                <div className={`stat-value ${p.unrealized_pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>${p.unrealized_pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Available Capital</div>
                                <div className="stat-value text-theme-text">${p.capital.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                            </div>
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Current Position</div>
                                <div className="stat-value text-theme-text">{p.position > 0 ? p.position.toFixed(6) : 'None'}</div>
                            </div>
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors">
                                <div className="stat-label">Total Trades</div>
                                <div className="stat-value text-theme-text">{p.total_trades}</div>
                            </div>
                            <div className="bg-theme-bg/50 rounded-xl p-5 border border-theme-border hover:bg-theme-hover transition-colors relative overflow-hidden">
                                <div className="stat-label flex items-center justify-between">
                                    <span>Max Drawdown</span>
                                    {riskState && <span className={`risk-badge ${riskState.circuit_breaker_active ? 'active' : 'ok'}`}>{riskState.circuit_breaker_active ? 'HALTED' : 'ACTIVE'}</span>}
                                </div>
                                <div className="stat-value text-theme-text">{p.current_drawdown_pct.toFixed(2)}%</div>
                            </div>
                        </div>
                    </div>
                );
            };

            const TradingActionsList = ({ actions }) => {
                if (!actions.length) return <div className="text-theme-muted text-center py-12 flex flex-col items-center"><svg className="w-12 h-12 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>Awaiting trading signals...</div>;
                const reversedActions = [...actions].reverse();
                return (
                    <div className="overflow-y-auto max-h-[500px]">
                        <table className="min-w-full divide-y divide-theme-border">
                            <thead className="sticky top-0 z-10">
                                <tr>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-theme-muted uppercase tracking-wider">Time</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-theme-muted uppercase tracking-wider">Action</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-theme-muted uppercase tracking-wider">Price</th>
                                    <th className="px-6 py-4 text-left text-xs font-semibold text-theme-muted uppercase tracking-wider">RSI</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-theme-border bg-transparent">
                                {reversedActions.map((action, i) => (
                                    <tr key={i} className="hover:bg-theme-hover transition-colors">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-theme-muted font-mono">{new Date(action.timestamp).toLocaleTimeString()}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                                            <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold border tracking-wider
                                                ${action.action === 'buy' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 
                                                  action.action === 'sell' ? 'bg-red-500/10 text-red-500 border-red-500/20' : 
                                                  'bg-amber-500/10 text-amber-500 border-amber-500/20'}`}>
                                                {action.action.toUpperCase()}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-theme-text font-mono font-medium">${parseFloat(action.price).toFixed(2)}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-theme-muted font-mono">{parseFloat(action.rsi).toFixed(1)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        <div ref={actionsEndRef} />
                    </div>
                );
            };

            const TradeHistoryTable = ({ portfolio }) => {
                if (!portfolio || !portfolio.trade_history || !portfolio.trade_history.length) return <div className="text-theme-muted text-center py-12 flex flex-col items-center"><svg className="w-12 h-12 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>No completed trades yet.</div>;
                const trades = [...portfolio.trade_history].reverse();
                return (
                    <div className="overflow-y-auto max-h-[500px]">
                        <table className="min-w-full divide-y divide-theme-border">
                            <thead className="sticky top-0 z-10"><tr>
                                <th className="px-6 py-4 text-left text-xs font-semibold text-theme-muted uppercase tracking-wider">Entry / Exit</th>
                                <th className="px-6 py-4 text-right text-xs font-semibold text-theme-muted uppercase tracking-wider">Net PnL</th>
                                <th className="px-6 py-4 text-right text-xs font-semibold text-theme-muted uppercase tracking-wider">Return %</th>
                                <th className="px-6 py-4 text-left text-xs font-semibold text-theme-muted uppercase tracking-wider">Rationale</th>
                            </tr></thead>
                            <tbody className="divide-y divide-theme-border bg-transparent">
                                {trades.map((t, i) => (
                                    <tr key={i} className="hover:bg-theme-hover transition-colors">
                                        <td className="px-6 py-4 text-sm text-theme-muted font-mono">
                                            <div className="flex flex-col gap-1">
                                                <span className="text-theme-muted">IN: ${t.entry_price}</span>
                                                <span className="text-theme-text font-medium">OUT: ${t.exit_price}</span>
                                            </div>
                                        </td>
                                        <td className={`px-6 py-4 text-sm font-bold text-right font-mono ${t.pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                            {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}
                                        </td>
                                        <td className={`px-6 py-4 text-sm font-bold text-right font-mono ${t.pnl_pct >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                            <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-bold ${t.pnl_pct >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                                                {t.pnl_pct >= 0 ? '↑' : '↓'} {Math.abs(t.pnl_pct).toFixed(2)}%
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-xs text-theme-muted leading-relaxed max-w-[200px] truncate" title={t.exit_reason}>{t.exit_reason}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                );
            };

            const RSIIndicator = ({ rsiData }) => {
                if (!rsiData || !rsiData.length) {
                    return <div className="text-theme-muted text-center py-10">No RSI data available yet.</div>;
                }
                const currentRsi = parseFloat(rsiData[rsiData.length - 1]);
                return (
                    <div>
                        <div className="flex items-end justify-between mb-8">
                            <div>
                                <div className="text-sm font-semibold text-theme-muted mb-2 uppercase tracking-widest">Current Index</div>
                                <div className={`text-5xl font-bold tracking-tighter ${currentRsi >= 70 ? 'text-red-500' : currentRsi <= 30 ? 'text-emerald-500' : 'text-theme-text'}`}>
                                    {currentRsi.toFixed(1)}
                                </div>
                            </div>
                            <div className="text-right pb-1">
                                <span className={`text-xs px-3 py-1.5 rounded-md font-bold tracking-wider border ${currentRsi >= 70 ? 'bg-red-500/10 text-red-500 border-red-500/20' : currentRsi <= 30 ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-theme-bg text-theme-text border-theme-border'}`}>
                                    {currentRsi >= 70 ? 'OVERBOUGHT ZONE' : currentRsi <= 30 ? 'OVERSOLD ZONE' : 'NEUTRAL TREND'}
                                </span>
                            </div>
                        </div>
                        
                        <div className="mb-10 relative pt-4">
                            <div className="h-4 w-full bg-theme-bg rounded-full overflow-hidden border border-theme-border shadow-inner">
                                <div 
                                    className={`h-full rounded-full transition-all duration-700 ease-out ${currentRsi >= 70 ? 'bg-red-500' : currentRsi <= 30 ? 'bg-emerald-500' : 'bg-blue-500'}`} 
                                    style={{ width: `${Math.min(100, Math.max(0, currentRsi))}%` }}
                                ></div>
                            </div>
                            
                            <div className="absolute top-0 bottom-0 left-[30%] w-[2px] bg-emerald-500/30 border-r border-dashed border-emerald-500/50 z-10 h-full"></div>
                            <div className="absolute top-0 bottom-0 left-[70%] w-[2px] bg-red-500/30 border-r border-dashed border-red-500/50 z-10 h-full"></div>
                            
                            <div className="flex justify-between text-xs text-theme-muted mt-3 font-semibold uppercase tracking-wider">
                                <span>0</span>
                                <span className="text-emerald-500 -ml-8">Oversold (30)</span>
                                <span className="text-red-500 -mr-8">Overbought (70)</span>
                                <span>100</span>
                            </div>
                        </div>
                        
                        <div className="bg-theme-bg/50 rounded-xl p-4 border border-theme-border">
                            <h4 className="text-xs font-semibold text-theme-muted mb-3 uppercase tracking-wider">Historical Values (T-12)</h4>
                            <div className="flex flex-wrap gap-2">
                                {rsiData.slice(-12).map((value, index) => {
                                    const rsiValue = parseFloat(value);
                                    let valueClass = "rsi-value";
                                    if (rsiValue >= 70) valueClass += " overbought";
                                    if (rsiValue <= 30) valueClass += " oversold";
                                    
                                    return (
                                        <div key={index} className={valueClass}>
                                            {rsiValue.toFixed(1)}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                );
            };

            const ModelPredictions = ({ predictions }) => {
                if (!predictions) return <div className="text-theme-muted text-center py-10">No predictions available yet.</div>;
                const currentPrice = predictions.current_price;
                return (
                    <div>
                        <div className="flex justify-between items-center bg-theme-bg/50 rounded-xl p-5 border border-theme-border mb-8 hover:bg-theme-hover transition-colors">
                            <div>
                                <p className="text-theme-muted text-xs font-semibold uppercase tracking-wider">Current Reference Price</p>
                                <p className="text-3xl font-bold text-theme-text mt-1 font-mono">${parseFloat(currentPrice).toFixed(2)}</p>
                            </div>
                            <div className="text-right">
                                <p className="text-theme-muted text-xs font-semibold uppercase tracking-wider">Forecast Timestamp</p>
                                <p className="text-blue-500 text-sm mt-1 font-mono">{new Date(predictions.timestamp).toLocaleTimeString()}</p>
                            </div>
                        </div>
                        
                        <h3 className="text-sm font-semibold text-theme-muted mb-4 uppercase tracking-wider flex items-center gap-2">
                            <svg className="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                            JEPA Trajectory Forecast (T+1 to T+5)
                        </h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                            {predictions.predicted_prices.map((price, index) => {
                                const priceDiff = price - currentPrice;
                                const percentChange = (priceDiff / currentPrice) * 100;
                                const isPositive = priceDiff > 0;
                                return (
                                    <div key={index} className="bg-theme-bg/50 p-4 rounded-xl border border-theme-border hover:border-blue-500/50 hover:bg-theme-hover transition-all flex flex-col items-center justify-center group relative overflow-hidden">
                                        {isPositive ? 
                                            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500/0 via-emerald-500 to-emerald-500/0 opacity-50"></div> : 
                                            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-500/0 via-red-500 to-red-500/0 opacity-50"></div>}
                                        <div className="text-xs text-theme-muted mb-3 font-semibold uppercase tracking-widest bg-theme-bg px-3 py-1 rounded-full border border-theme-border">STEP {index + 1}</div>
                                        <div className="font-bold text-theme-text mb-2 text-lg font-mono group-hover:scale-110 transition-transform">${parseFloat(price).toFixed(2)}</div>
                                        <div className={`text-xs font-bold flex items-center gap-1 px-2.5 py-1 rounded-md ${isPositive ? 'text-emerald-500 bg-emerald-500/10' : 'text-red-500 bg-red-500/10'}`}>
                                            {isPositive ? 
                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 10l7-7m0 0l7 7m-7-7v18"></path></svg> : 
                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M19 14l-7 7m0 0l-7-7m7 7V3"></path></svg>}
                                            {Math.abs(percentChange).toFixed(2)}%
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        
                        <div className="mt-8 p-4 bg-blue-500/5 border border-blue-500/20 rounded-xl flex items-start gap-3">
                            <div className="p-2 bg-blue-500/10 rounded-lg shrink-0">
                                <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-theme-text mb-1">Architecture Insights</h4>
                                <p className="text-xs text-theme-muted leading-relaxed">Forecasts are generated by the core JEPA model utilizing causal attention masking and EMA target encoding for robust representation learning over the current market state.</p>
                            </div>
                        </div>
                    </div>
                );
            };

            return (
                <div className="container mx-auto px-4 py-8 max-w-[1400px] flex flex-col min-h-screen">
                    <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 card p-6">
                        <div>
                            <div className="flex items-center gap-4">
                                <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-3 rounded-xl shadow-lg shadow-blue-500/20 border border-blue-400/30 relative overflow-hidden">
                                    <div className="absolute inset-0 bg-white/20 transform -skew-x-12 translate-x-full group-hover:translate-x-0 transition-transform"></div>
                                    <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                                </div>
                                <div>
                                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 tracking-tight">
                                        JEPA Terminal
                                    </h1>
                                    <p className="text-xs font-semibold text-theme-muted uppercase tracking-widest mt-1">Autonomous Trading System</p>
                                </div>
                            </div>
                        </div>
                        
                        <div className="flex flex-wrap items-center gap-4">
                            {currentPrice && (
                                <div className="hidden lg:flex flex-col items-end mr-6 pr-6 border-r border-theme-border">
                                    <span className="text-theme-muted text-xs font-semibold uppercase tracking-wider mb-1">{symbol} Price</span>
                                    <span className="text-2xl font-bold text-theme-text tracking-tight font-mono">${parseFloat(currentPrice).toFixed(2)}</span>
                                </div>
                            )}
                            
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                    <svg className="w-4 h-4 text-theme-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                                </div>
                                <select 
                                    value={symbol} 
                                    onChange={handleSymbolChange} 
                                    className="bg-theme-bg border border-theme-border text-theme-text text-sm font-semibold rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 block pl-10 pr-8 py-2.5 outline-none transition-all cursor-pointer appearance-none shadow-sm"
                                >
                                    <option value="BTCUSDT">BTC/USDT</option>
                                    <option value="ETHUSDT">ETH/USDT</option>
                                    <option value="BNBUSDT">BNB/USDT</option>
                                    <option value="ADAUSDT">ADA/USDT</option>
                                    <option value="XRPUSDT">XRP/USDT</option>
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                                    <svg className="w-4 h-4 text-theme-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                                </div>
                            </div>
                            
                            <div className="flex items-center px-4 py-2.5 bg-theme-bg rounded-xl border border-theme-border shadow-sm">
                                <div className={`status-dot w-2.5 h-2.5 rounded-full mr-3 ${connected ? 'bg-emerald-500' : 'bg-red-500 error'}`}></div>
                                <span className="text-xs font-bold tracking-widest text-theme-text uppercase">{connected ? 'System Live' : 'Offline'}</span>
                            </div>
                            
                            <button 
                                onClick={toggleTheme}
                                className="p-2.5 bg-theme-bg rounded-xl border border-theme-border text-theme-muted hover:text-theme-text transition-colors shadow-sm ml-2"
                                aria-label="Toggle theme"
                            >
                                {isDark ? (
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                                ) : (
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
                                )}
                            </button>
                        </div>
                    </header>

                    <div className="flex space-x-8 border-b border-theme-border mb-8 px-4">
                        <button 
                            className={`tab-btn pb-4 text-sm font-bold tracking-wide uppercase ${activeTab === 'overview' ? 'active text-blue-500' : 'text-theme-muted hover:text-theme-text'}`}
                            onClick={() => setActiveTab('overview')}
                        >
                            Market Overview
                        </button>
                        <button 
                            className={`tab-btn pb-4 text-sm font-bold tracking-wide uppercase ${activeTab === 'analytics' ? 'active text-blue-500' : 'text-theme-muted hover:text-theme-text'}`}
                            onClick={() => setActiveTab('analytics')}
                        >
                            AI Analytics
                        </button>
                        <button 
                            className={`tab-btn pb-4 text-sm font-bold tracking-wide uppercase ${activeTab === 'history' ? 'active text-blue-500' : 'text-theme-muted hover:text-theme-text'}`}
                            onClick={() => setActiveTab('history')}
                        >
                            Execution Log
                        </button>
                    </div>

                    <div className="flex-grow">
                        {activeTab === 'overview' && (
                            <div className="space-y-6 animate-fadeIn">
                                <div className="card p-6 lg:p-8">
                                    <div className="flex items-center justify-between mb-6">
                                        <h2 className="text-lg font-bold text-theme-text flex items-center gap-3 tracking-wide">
                                            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-500">
                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"></path></svg>
                                            </div>
                                            Portfolio Metrics
                                        </h2>
                                    </div>
                                    <PortfolioSummary portfolio={portfolio} riskState={riskState} />
                                </div>
                                
                                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                                    <div className="card p-6 lg:p-8">
                                        <h2 className="text-lg font-bold text-theme-text mb-6 flex items-center gap-3 tracking-wide">
                                            <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-500">
                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"></path></svg>
                                            </div>
                                            Live Price Action
                                        </h2>
                                        <PriceChart priceData={priceData} tradingActions={tradingActions} isDark={isDark} />
                                    </div>
                                    <div className="card p-6 lg:p-8">
                                        <h2 className="text-lg font-bold text-theme-text mb-6 flex items-center gap-3 tracking-wide">
                                            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-500">
                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                                            </div>
                                            Performance Curve
                                        </h2>
                                        <EquityCurve portfolio={portfolio} isDark={isDark} />
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'analytics' && (
                            <div className="space-y-6 animate-fadeIn">
                                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                                    <div className="card p-6 lg:p-8">
                                        <h2 className="text-lg font-bold text-theme-text mb-8 flex items-center gap-3 tracking-wide">
                                            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-500">
                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                                            </div>
                                            Momentum Oscillator (RSI)
                                        </h2>
                                        <RSIIndicator rsiData={indicators.rsi || []} />
                                    </div>
                                    <div className="card p-6 lg:p-8">
                                        <h2 className="text-lg font-bold text-theme-text mb-8 flex items-center gap-3 tracking-wide">
                                            <div className="p-2 bg-pink-500/10 rounded-lg text-pink-500">
                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                                            </div>
                                            Neural Forecasts
                                        </h2>
                                        <ModelPredictions predictions={predictions} />
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'history' && (
                            <div className="space-y-6 animate-fadeIn">
                                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                                    <div className="card p-0 overflow-hidden flex flex-col">
                                        <div className="p-6 border-b border-theme-border bg-theme-bg">
                                            <h2 className="text-lg font-bold text-theme-text flex items-center gap-3 tracking-wide">
                                                <div className="p-2 bg-cyan-500/10 rounded-lg text-cyan-500">
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                                </div>
                                                Recent Signals
                                            </h2>
                                        </div>
                                        <div className="p-0 flex-grow">
                                            <TradingActionsList actions={tradingActions} />
                                        </div>
                                    </div>
                                    <div className="card p-0 overflow-hidden flex flex-col">
                                        <div className="p-6 border-b border-theme-border bg-theme-bg">
                                            <h2 className="text-lg font-bold text-theme-text flex items-center gap-3 tracking-wide">
                                                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-500">
                                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                                                </div>
                                                Trade Ledger
                                            </h2>
                                        </div>
                                        <div className="p-0 flex-grow">
                                            <TradeHistoryTable portfolio={portfolio} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            );
        };

        ReactDOM.render(<App />, document.getElementById('root'));
    </script>
</body>
</html>
"""

with open('index.html', 'w') as f:
    f.write(html_content)
