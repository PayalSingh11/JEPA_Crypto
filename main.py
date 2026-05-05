from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
import pandas as pd
import os
import logging
import numpy as np
import torch
import joblib
from datetime import datetime
import math
from typing import List, Dict, Any

from src.crypto_trading_pipeline import (
    compute_rsi, compute_macd, compute_bollinger_width, compute_rolling_volatility,
    BinanceWebSocketClient, RealTimeProcessor, JEPAModel, MPCModule, RealTimeFeatureBuffer,
    TradingActionLogger
)
from src.portfolio import PortfolioManager, RiskManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

connected_clients = []
symbol = "BTCUSDT"
processor = None
binance_client = None
mpc = None
feature_buffer = None
action_logger = None
model = None
device = None
portfolio_manager = None
risk_manager = None
price_history = []
trading_actions = []
model_predictions = []
initialized = False

MODEL_FILE = 'models/jepa_model.pth'
SCALER_FILE = 'models/scaler.pkl'


def sanitize_for_json(data):
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    else:
        return data


def initialize_trading_system(selected_symbol: str = "BTCUSDT"):
    global symbol, processor, binance_client, mpc, feature_buffer, action_logger
    global model, device, portfolio_manager, risk_manager, initialized
    try:
        symbol = selected_symbol
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")

        if not os.path.exists(MODEL_FILE) or not os.path.exists(SCALER_FILE):
            logger.error("Model files not found. Please run crypto_trading_pipeline.py first to train the model.")
            return False

        input_dim = 11
        seq_len = 60
        pred_steps = 5

        model = JEPAModel(input_dim, d_model=128, nhead=8, num_layers=6, pred_steps=pred_steps).to(device)
        model.load_state_dict(torch.load(MODEL_FILE, map_location=device), strict=False)
        model.eval()

        scaler = joblib.load(SCALER_FILE)

        ADV_minute = 100.0
        ADVOL_minute = 0.01

        cost_weights = {'transaction': 0.5, 'risk': 1.0, 'return': 3.0}
        mpc = MPCModule(model, horizon=30, action_space=[0, 1, 2], cost_weights=cost_weights)

        feature_buffer = RealTimeFeatureBuffer(seq_len)
        action_logger = TradingActionLogger()

        # Initialize portfolio and risk management
        portfolio_manager = PortfolioManager(
            initial_capital=10000.0, position_size_pct=0.25, trading_fee_pct=0.001)
        risk_manager = RiskManager(
            stop_loss_pct=0.02, take_profit_pct=0.03,
            max_drawdown_pct=0.10, cooldown_minutes=5)

        def on_new_features(features):
            feature_buffer.add_feature(features)
            current_state = feature_buffer.get_current_state()
            current_price = features['close_price']
            timestamp = features['timestamp']

            price_history.append({
                'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                'price': current_price
            })
            if len(price_history) > 1000:
                price_history.pop(0)

            if current_state is not None:
                # 1. Risk manager: check forced exit conditions
                actual_action = 0
                exit_reason = 'signal'

                if portfolio_manager.has_position:
                    exit_cond = risk_manager.check_exit_conditions(
                        portfolio_manager.entry_price, current_price)
                    if exit_cond:
                        actual_action = portfolio_manager.force_close(
                            current_price, timestamp, reason=exit_cond)
                        if exit_cond == 'stop_loss':
                            risk_manager.on_stop_loss_triggered(timestamp)
                        exit_reason = exit_cond
                        action_desc = {0: 'hold', 1: 'buy', 2: 'sell'}[actual_action]
                        trading_actions.append({
                            'timestamp': timestamp.isoformat(),
                            'action': action_desc,
                            'price': current_price,
                            'rsi': features['rsi'] * 100,
                            'macd': features['macd'],
                            'reason': f'Risk exit: {exit_cond}'
                        })
                        if len(trading_actions) > 100:
                            trading_actions.pop(0)
                        return

                # 2. MPC recommends action
                raw_action = mpc.optimize_action(current_state.to(device))

                # 3. Risk manager: check if trading is allowed
                portfolio_state = portfolio_manager.get_portfolio_state(current_price)
                allowed, reason = risk_manager.is_trading_allowed(
                    portfolio_state, timestamp)
                if not allowed and raw_action != 0:
                    logger.info(f"Trading blocked by risk manager: {reason}")
                    raw_action = 0

                # 4. Portfolio manager filters and executes
                actual_action = portfolio_manager.execute_action(
                    raw_action, current_price, timestamp)

                action_desc = {0: 'hold', 1: 'buy', 2: 'sell'}[actual_action]
                action_logger.log_action(actual_action, features, timestamp)

                trading_actions.append({
                    'timestamp': timestamp.isoformat(),
                    'action': action_desc,
                    'price': current_price,
                    'rsi': features['rsi'] * 100,
                    'macd': features['macd'],
                    'reason': action_logger.get_reason(actual_action, features)
                })
                if len(trading_actions) > 100:
                    trading_actions.pop(0)

                with torch.no_grad():
                    _, future_pred, _ = model(current_state.unsqueeze(0).to(device))
                    future_prices = [float(current_price)]
                    for i in range(pred_steps):
                        log_return = future_pred[0, i, 0].item()
                        # Constrain log return to ±0.01 per minute for realistic price changes
                        log_return = max(min(log_return, 0.01), -0.01)
                        future_prices.append(future_prices[-1] * np.exp(log_return))

                    model_predictions.append({
                        'timestamp': timestamp.isoformat(),
                        'current_price': current_price,
                        'predicted_prices': future_prices[1:]
                    })
                    if len(model_predictions) > 100:
                        model_predictions.pop(0)

        processor = RealTimeProcessor(symbol, ADV_minute, ADVOL_minute, scaler, callback=on_new_features)
        binance_client = BinanceWebSocketClient(symbol, processor)
        binance_client.connect()

        initialized = True
        logger.info(f"Trading system initialized for {symbol}")
        return True

    except Exception as e:
        logger.error(f"Error initializing trading system: {str(e)}")
        return False


async def broadcast_updates():
    if not connected_clients:
        return

    current_price = price_history[-1]['price'] if price_history else 0

    data = {
        'price_history': price_history[-100:],
        'trading_actions': trading_actions[-20:],
        'model_predictions': model_predictions[-1] if model_predictions else None,
    }

    # Portfolio & risk state
    if portfolio_manager:
        data['portfolio'] = portfolio_manager.get_portfolio_state(current_price)
    if risk_manager:
        data['risk'] = risk_manager.get_risk_state()

    if price_history:
        prices = pd.Series([p['price'] for p in price_history[-100:]])
        data['indicators'] = {
            'rsi': compute_rsi(prices).tolist() if len(prices) >= 14 else [],
            'macd': compute_macd(prices).tolist() if len(prices) >= 26 else [],
            'bollinger_width': compute_bollinger_width(prices).tolist() if len(prices) >= 20 else [],
        }

    for client in connected_clients:
        try:
            await client.send_json(sanitize_for_json(data))
        except Exception as e:
            logger.error(f"Error sending data to client: {str(e)}")


async def periodic_broadcast_task():
    while True:
        await asyncio.sleep(60)  # 1-minute interval
        await broadcast_updates()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        if not initialized:
            initialize_trading_system()

        current_price = price_history[-1]['price'] if price_history else 0

        data = {
            'price_history': price_history[-100:],
            'trading_actions': trading_actions[-20:],
            'model_predictions': model_predictions[-1] if model_predictions else None,
            'initialized': initialized
        }

        # Portfolio & risk state
        if portfolio_manager:
            data['portfolio'] = portfolio_manager.get_portfolio_state(current_price)
        if risk_manager:
            data['risk'] = risk_manager.get_risk_state()

        if price_history:
            prices = pd.Series([p['price'] for p in price_history[-100:]])
            data['indicators'] = {
                'rsi': compute_rsi(prices).tolist() if len(prices) >= 14 else [],
                'macd': compute_macd(prices).tolist() if len(prices) >= 26 else [],
                'bollinger_width': compute_bollinger_width(prices).tolist() if len(prices) >= 20 else [],
            }

        await websocket.send_json(sanitize_for_json(data))

        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get('action') == 'change_symbol':
                new_symbol = data.get('symbol', symbol)
                logger.info(f"Changing symbol to {new_symbol}")
                if binance_client:
                    binance_client.stop()
                success = initialize_trading_system(new_symbol)
                await websocket.send_json({'action': 'symbol_changed', 'success': success, 'symbol': new_symbol})

    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open('frontend/index.html', 'r') as f:
        return HTMLResponse(content=f.read())


@app.on_event("startup")
async def startup_event():
    initialize_trading_system()
    asyncio.create_task(periodic_broadcast_task())


@app.on_event("shutdown")
async def shutdown_event():
    global binance_client
    if binance_client:
        binance_client.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)