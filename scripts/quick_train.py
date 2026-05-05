"""
Quick training script for the JEPA model.
Uses 7 days of data by default. Includes train/val split, early stopping, and LR scheduling.
"""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crypto_trading_pipeline import (
    compute_features_from_klines, FEATURE_COLS,
    JEPAModel, MarketDataset, train_jepa
)
from binance.client import Client
import pandas as pd
import numpy as np
import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
from sklearn.preprocessing import StandardScaler
import joblib
import pickle


def quick_train(symbol="BTCUSDT", days=7, epochs=30):
    """Train with fewer days & epochs. Includes train/val split and early stopping."""
    client = Client()

    klines_file = f"data/{symbol}_klines_{days}d.pkl"
    if os.path.exists(klines_file):
        logger.info(f"Loading cached klines from {klines_file}")
        with open(klines_file, 'rb') as f:
            klines = pickle.load(f)
    else:
        logger.info(f"Fetching {days} days of 1-minute klines for {symbol}...")
        klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1MINUTE, f"{days} days ago UTC")
        with open(klines_file, 'wb') as f:
            pickle.dump(klines, f)
        logger.info(f"Saved {len(klines)} klines to {klines_file}")

    klines_df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    klines_df['timestamp'] = pd.to_datetime(klines_df['timestamp'], unit='ms')
    klines_df.set_index('timestamp', inplace=True)
    klines_df = klines_df.astype(float)

    logger.info(f"Got {len(klines_df)} candles from {klines_df.index[0]} to {klines_df.index[-1]}")

    # Compute averages
    ADV_minute = klines_df['volume'].mean()
    ADVOL_minute = ((klines_df['high'] - klines_df['low']) / klines_df['close']).mean()
    logger.info(f"ADV_minute: {ADV_minute:.2f}, ADVOL_minute: {ADVOL_minute:.6f}")

    # Compute features using canonical FEATURE_COLS ordering
    feature_df = compute_features_from_klines(klines_df, ADV_minute, ADVOL_minute)
    feature_df = feature_df.dropna()
    logger.info(f"Feature matrix shape: {feature_df.shape}")
    logger.info(f"Feature columns: {list(feature_df.columns)}")

    # Scale
    scaler = StandardScaler()
    feature_df_normalized = pd.DataFrame(
        scaler.fit_transform(feature_df),
        columns=feature_df.columns,
        index=feature_df.index
    )
    joblib.dump(scaler, 'models/scaler.pkl')
    logger.info("Saved scaler.pkl")

    # Create dataset and split into train/val (80/20)
    seq_len = 60
    pred_steps = 5
    full_dataset = MarketDataset(feature_df_normalized, seq_len, pred_steps)
    n_total = len(full_dataset)
    n_train = int(n_total * 0.8)
    n_val = n_total - n_train

    train_dataset, val_dataset = torch.utils.data.random_split(full_dataset, [n_train, n_val])
    logger.info(f"Dataset: {n_total} total | {n_train} train | {n_val} val")

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, drop_last=False)

    # Build model
    input_dim = feature_df.shape[1]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    model = JEPAModel(input_dim, d_model=128, nhead=8, num_layers=6, pred_steps=pred_steps).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-5)
    scheduler = CosineAnnealingWarmRestarts(optimizer, T_0=10, T_mult=2, eta_min=1e-6)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Model params: {total_params:,} total | {trainable_params:,} trainable")

    # Train with validation and early stopping
    logger.info(f"Starting training for up to {epochs} epochs (early stopping patience=5)...")
    best_loss = train_jepa(
        model, train_loader, optimizer, device, epochs=epochs,
        val_loader=val_loader, scheduler=scheduler, patience=5
    )

    # Save
    torch.save(model.state_dict(), 'models/jepa_model.pth')
    logger.info(f"Saved jepa_model.pth (best val loss: {best_loss:.4f})")
    logger.info("Training complete! Run: source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --ws wsproto")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    epochs = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    quick_train(symbol, days, epochs)
