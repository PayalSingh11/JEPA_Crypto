"""
Backtesting Engine for Crypto Trading Pipeline.

Replays historical kline data through the full pipeline:
feature engineering → JEPA model → MPC → portfolio + risk manager → metrics.

Usage:
    python backtester.py --symbol BTCUSDT --days 7 --capital 10000
"""

import argparse
import logging
import os
import sys
import pickle
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
import torch
import joblib

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crypto_trading_pipeline import (
    compute_features_from_klines,
    JEPAModel, MPCModule, RealTimeFeatureBuffer
)
from src.portfolio import PortfolioManager, RiskManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress excessive logging during backtesting
logging.getLogger('crypto_trading_pipeline').setLevel(logging.WARNING)


class BacktestMetrics:
    """Compute standard trading performance metrics."""

    @staticmethod
    def compute(trade_history: List[Dict], equity_curve: List[Dict],
                initial_capital: float) -> Dict[str, Any]:
        """
        Compute all performance metrics from trade history and equity curve.

        Returns dict with all metrics.
        """
        metrics = {}

        # -- Equity curve metrics --
        if equity_curve:
            equities = [e['equity'] for e in equity_curve]
            start_equity = equities[0]
            end_equity = equities[-1]

            metrics['start_equity'] = round(start_equity, 2)
            metrics['end_equity'] = round(end_equity, 2)
            metrics['total_return_pct'] = round(
                ((end_equity / initial_capital) - 1) * 100, 2)

            # Max drawdown
            peak = equities[0]
            max_dd = 0
            for eq in equities:
                peak = max(peak, eq)
                dd = (peak - eq) / peak
                max_dd = max(max_dd, dd)
            metrics['max_drawdown_pct'] = round(max_dd * 100, 2)

            # Sharpe ratio (annualized, assuming 1-minute bars → 525600 minutes/year)
            if len(equities) > 1:
                equity_series = pd.Series(equities)
                returns = equity_series.pct_change().dropna()
                if len(returns) > 1 and returns.std() > 0:
                    minutes_per_year = 525600
                    sharpe = (returns.mean() / returns.std()) * np.sqrt(minutes_per_year)
                    metrics['sharpe_ratio'] = round(sharpe, 3)
                else:
                    metrics['sharpe_ratio'] = 0.0
            else:
                metrics['sharpe_ratio'] = 0.0

            # Calmar ratio
            annual_return = metrics['total_return_pct']  # Simplified
            if metrics['max_drawdown_pct'] > 0:
                metrics['calmar_ratio'] = round(
                    annual_return / metrics['max_drawdown_pct'], 3)
            else:
                metrics['calmar_ratio'] = 0.0
        else:
            metrics['start_equity'] = initial_capital
            metrics['end_equity'] = initial_capital
            metrics['total_return_pct'] = 0.0
            metrics['max_drawdown_pct'] = 0.0
            metrics['sharpe_ratio'] = 0.0
            metrics['calmar_ratio'] = 0.0

        # -- Trade metrics --
        metrics['total_trades'] = len(trade_history)

        if trade_history:
            pnls = [t['pnl'] for t in trade_history]
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p <= 0]

            metrics['winning_trades'] = len(winning)
            metrics['losing_trades'] = len(losing)
            metrics['win_rate_pct'] = round(
                len(winning) / len(pnls) * 100, 1) if pnls else 0.0

            gross_profit = sum(winning) if winning else 0
            gross_loss = abs(sum(losing)) if losing else 0
            metrics['gross_profit'] = round(gross_profit, 2)
            metrics['gross_loss'] = round(gross_loss, 2)
            metrics['profit_factor'] = round(
                gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf')

            metrics['avg_pnl'] = round(np.mean(pnls), 2)
            metrics['avg_win'] = round(np.mean(winning), 2) if winning else 0.0
            metrics['avg_loss'] = round(np.mean(losing), 2) if losing else 0.0
            metrics['largest_win'] = round(max(pnls), 2)
            metrics['largest_loss'] = round(min(pnls), 2)

            durations = [t.get('duration_minutes', 0) for t in trade_history]
            metrics['avg_duration_min'] = round(np.mean(durations), 1) if durations else 0

            # Count exit reasons
            exit_reasons = {}
            for t in trade_history:
                reason = t.get('exit_reason', 'signal')
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
            metrics['exit_reasons'] = exit_reasons
        else:
            metrics['winning_trades'] = 0
            metrics['losing_trades'] = 0
            metrics['win_rate_pct'] = 0.0
            metrics['gross_profit'] = 0.0
            metrics['gross_loss'] = 0.0
            metrics['profit_factor'] = 0.0
            metrics['avg_pnl'] = 0.0
            metrics['avg_win'] = 0.0
            metrics['avg_loss'] = 0.0
            metrics['largest_win'] = 0.0
            metrics['largest_loss'] = 0.0
            metrics['avg_duration_min'] = 0
            metrics['exit_reasons'] = {}

        return metrics


class BuyAndHoldBenchmark:
    """Simple buy-and-hold benchmark for comparison."""

    @staticmethod
    def compute(prices: pd.Series, initial_capital: float) -> Dict[str, Any]:
        """Compute buy-and-hold metrics."""
        if prices.empty:
            return {'total_return_pct': 0.0, 'max_drawdown_pct': 0.0}

        start_price = prices.iloc[0]
        end_price = prices.iloc[-1]
        total_return = ((end_price / start_price) - 1) * 100

        # Max drawdown
        cummax = prices.cummax()
        drawdowns = (cummax - prices) / cummax
        max_dd = drawdowns.max() * 100

        # Sharpe
        returns = prices.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(525600)
        else:
            sharpe = 0.0

        return {
            'total_return_pct': round(total_return, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'sharpe_ratio': round(sharpe, 3),
            'start_price': round(start_price, 2),
            'end_price': round(end_price, 2),
        }


class BacktestEngine:
    """
    Replay historical data through the full JEPA + MPC + Portfolio pipeline.
    """

    def __init__(self, symbol: str = "BTCUSDT", initial_capital: float = 10000.0,
                 stop_loss_pct: float = 0.02, take_profit_pct: float = 0.03,
                 position_size_pct: float = 0.25):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.position_size_pct = position_size_pct

    def run(self, days: int = 7) -> Dict[str, Any]:
        """
        Run backtest on historical data.

        Args:
            days: Number of days of historical data to use.

        Returns:
            Dict with metrics, trade history, equity curve, and benchmark.
        """
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Running backtest: {self.symbol}, {days} days, ${self.initial_capital} capital")
        logger.info(f"Risk params: SL={self.stop_loss_pct*100}%, TP={self.take_profit_pct*100}%, "
                     f"Position={self.position_size_pct*100}%")

        # -- Load model and scaler --
        model_file = 'models/jepa_model.pth'
        scaler_file = 'models/scaler.pkl'
        if not os.path.exists(model_file) or not os.path.exists(scaler_file):
            raise FileNotFoundError(
                "Model files not found. Run quick_train.py first.")

        input_dim = 11
        seq_len = 60
        pred_steps = 5

        model = JEPAModel(input_dim, d_model=128, nhead=8, num_layers=6,
                          pred_steps=pred_steps).to(device)
        model.load_state_dict(torch.load(model_file, map_location=device), strict=False)
        model.eval()

        scaler = joblib.load(scaler_file)

        # -- Load historical data --
        klines_file = f"data/{self.symbol}_klines_{days}d.pkl"
        if os.path.exists(klines_file):
            logger.info(f"Loading cached klines from {klines_file}")
            with open(klines_file, 'rb') as f:
                klines = pickle.load(f)
        else:
            logger.info(f"Fetching {days} days of klines from Binance...")
            from binance.client import Client
            client = Client()
            klines = client.get_historical_klines(
                self.symbol, Client.KLINE_INTERVAL_1MINUTE,
                f"{days} days ago UTC")
            with open(klines_file, 'wb') as f:
                pickle.dump(klines, f)

        klines_df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        klines_df['timestamp'] = pd.to_datetime(klines_df['timestamp'], unit='ms')
        klines_df.set_index('timestamp', inplace=True)
        klines_df = klines_df.astype(float)

        logger.info(f"Loaded {len(klines_df)} candles: "
                     f"{klines_df.index[0]} → {klines_df.index[-1]}")

        # -- Compute features --
        ADV_minute = klines_df['volume'].mean()
        ADVOL_minute = ((klines_df['high'] - klines_df['low']) / klines_df['close']).mean()

        feature_df = compute_features_from_klines(klines_df, ADV_minute, ADVOL_minute)
        feature_df = feature_df.dropna()

        # Normalize using trained scaler
        feature_cols = feature_df.columns.tolist()
        normalized = scaler.transform(feature_df)
        feature_normalized = pd.DataFrame(normalized, columns=feature_cols,
                                           index=feature_df.index)

        logger.info(f"Feature matrix: {feature_normalized.shape}")

        # -- Initialize components --
        portfolio = PortfolioManager(
            initial_capital=self.initial_capital,
            position_size_pct=self.position_size_pct)
        risk_mgr = RiskManager(
            stop_loss_pct=self.stop_loss_pct,
            take_profit_pct=self.take_profit_pct)

        cost_weights = {'transaction': 0.5, 'risk': 1.0, 'return': 3.0}
        mpc = MPCModule(model, horizon=30, action_space=[0, 1, 2],
                        cost_weights=cost_weights)

        # Use explicit feature ordering (not sorted dict keys)
        feature_buffer = RealTimeFeatureBuffer(seq_len)

        # -- Replay loop --
        data = feature_normalized.values
        timestamps = feature_normalized.index
        close_prices = klines_df.loc[feature_normalized.index, 'close']

        total_steps = len(data)
        actions_taken = {'hold': 0, 'buy': 0, 'sell': 0}
        action_map = {0: 'hold', 1: 'buy', 2: 'sell'}

        logger.info(f"Starting replay over {total_steps} steps...")
        start_time = time.time()

        for i in range(total_steps):
            timestamp = timestamps[i]
            price = close_prices.iloc[i]
            feature_vector = data[i].tolist()

            # Add to buffer
            feature_buffer.buffer.append(feature_vector)
            if len(feature_buffer.buffer) > seq_len:
                feature_buffer.buffer.pop(0)

            # Need full buffer to predict
            if len(feature_buffer.buffer) < seq_len:
                # Still record equity
                portfolio.execute_action(0, price, timestamp)
                continue

            # 1. Check risk exit conditions on existing position
            if portfolio.has_position:
                exit_cond = risk_mgr.check_exit_conditions(
                    portfolio.entry_price, price)
                if exit_cond:
                    portfolio.force_close(price, timestamp, reason=exit_cond)
                    if exit_cond == 'stop_loss':
                        risk_mgr.on_stop_loss_triggered(timestamp)
                    actions_taken['sell'] += 1
                    continue

            # 2. Get model prediction via MPC
            state = torch.tensor(feature_buffer.buffer, dtype=torch.float32)
            raw_action = mpc.optimize_action(state.to(device))

            # 3. Check if trading is allowed (circuit breaker / cooldown)
            portfolio_state = portfolio.get_portfolio_state(price)
            allowed, reason = risk_mgr.is_trading_allowed(
                portfolio_state, timestamp)

            if not allowed and raw_action != 0:
                raw_action = 0  # Force hold

            # 4. Execute through portfolio (filters invalid actions)
            actual_action = portfolio.execute_action(raw_action, price, timestamp)
            actions_taken[action_map[actual_action]] += 1

            # Progress logging
            if (i + 1) % 500 == 0 or i == total_steps - 1:
                pct = (i + 1) / total_steps * 100
                equity = portfolio.get_total_equity(price)
                elapsed = time.time() - start_time
                logger.info(f"Progress: {pct:.1f}% ({i+1}/{total_steps}) | "
                             f"Equity: ${equity:.2f} | "
                             f"Trades: {len(portfolio.trade_history)} | "
                             f"Time: {elapsed:.1f}s")

        # -- Force close any remaining position --
        if portfolio.has_position:
            final_price = close_prices.iloc[-1]
            portfolio.force_close(final_price, timestamps[-1], reason='backtest_end')

        elapsed = time.time() - start_time
        logger.info(f"Backtest completed in {elapsed:.1f}s")

        # -- Compute metrics --
        metrics = BacktestMetrics.compute(
            portfolio.trade_history, portfolio.equity_curve,
            self.initial_capital)

        # -- Benchmark: buy and hold --
        benchmark = BuyAndHoldBenchmark.compute(close_prices, self.initial_capital)

        # -- Action distribution --
        metrics['action_distribution'] = actions_taken
        metrics['backtest_duration_seconds'] = round(elapsed, 1)
        metrics['data_points'] = total_steps
        metrics['symbol'] = self.symbol
        metrics['days'] = days

        return {
            'metrics': metrics,
            'benchmark': benchmark,
            'trade_history': portfolio.trade_history,
            'equity_curve': portfolio.equity_curve,
            'risk_events': risk_mgr.risk_events,
        }


def print_report(results: Dict[str, Any]):
    """Print a formatted backtest report to the terminal."""
    m = results['metrics']
    b = results['benchmark']

    print("\n" + "=" * 70)
    print(f"  BACKTEST REPORT — {m['symbol']}  ({m['days']} days)")
    print("=" * 70)

    print(f"\n{'PORTFOLIO PERFORMANCE':-^50}")
    print(f"  Initial Capital:      ${m['start_equity']:>12,.2f}")
    print(f"  Final Equity:         ${m['end_equity']:>12,.2f}")
    print(f"  Total Return:         {m['total_return_pct']:>12.2f}%")
    print(f"  Max Drawdown:         {m['max_drawdown_pct']:>12.2f}%")
    print(f"  Sharpe Ratio:         {m['sharpe_ratio']:>12.3f}")
    print(f"  Calmar Ratio:         {m['calmar_ratio']:>12.3f}")

    print(f"\n{'TRADE STATISTICS':-^50}")
    print(f"  Total Trades:         {m['total_trades']:>12d}")
    print(f"  Winning Trades:       {m['winning_trades']:>12d}")
    print(f"  Losing Trades:        {m['losing_trades']:>12d}")
    print(f"  Win Rate:             {m['win_rate_pct']:>12.1f}%")
    print(f"  Profit Factor:        {m['profit_factor']:>12.2f}")
    print(f"  Avg PnL/Trade:        ${m['avg_pnl']:>12.2f}")
    print(f"  Avg Win:              ${m['avg_win']:>12.2f}")
    print(f"  Avg Loss:             ${m['avg_loss']:>12.2f}")
    print(f"  Largest Win:          ${m['largest_win']:>12.2f}")
    print(f"  Largest Loss:         ${m['largest_loss']:>12.2f}")
    print(f"  Avg Duration:         {m['avg_duration_min']:>12.1f} min")

    if m.get('exit_reasons'):
        print(f"\n{'EXIT REASONS':-^50}")
        for reason, count in m['exit_reasons'].items():
            print(f"  {reason:<20s}  {count:>12d}")

    print(f"\n{'ACTION DISTRIBUTION':-^50}")
    dist = m.get('action_distribution', {})
    for action, count in dist.items():
        print(f"  {action:<20s}  {count:>12d}")

    print(f"\n{'BUY & HOLD BENCHMARK':-^50}")
    print(f"  Start Price:          ${b['start_price']:>12.2f}")
    print(f"  End Price:            ${b['end_price']:>12.2f}")
    print(f"  B&H Return:           {b['total_return_pct']:>12.2f}%")
    print(f"  B&H Max Drawdown:     {b['max_drawdown_pct']:>12.2f}%")
    print(f"  B&H Sharpe:           {b['sharpe_ratio']:>12.3f}")

    # Comparison
    alpha = m['total_return_pct'] - b['total_return_pct']
    print(f"\n{'COMPARISON':-^50}")
    print(f"  Alpha (vs B&H):      {alpha:>12.2f}%")
    beat = "✅ OUTPERFORMED" if alpha > 0 else "❌ UNDERPERFORMED"
    print(f"  Result:               {beat}")

    print("\n" + "=" * 70)

    # Risk events
    if results.get('risk_events'):
        print(f"\n{'RISK EVENTS':-^50}")
        for event in results['risk_events'][-10:]:
            print(f"  [{event['type']}] {event['timestamp']}: {event['description']}")

    print()


def save_results(results: Dict[str, Any], output_dir: str = "."):
    """Save backtest results to CSV files."""
    # Trade history
    if results['trade_history']:
        trades_df = pd.DataFrame(results['trade_history'])
        trades_file = os.path.join(output_dir, 'backtest_trades.csv')
        trades_df.to_csv(trades_file, index=False)
        logger.info(f"Trade history saved to {trades_file}")

    # Equity curve
    if results['equity_curve']:
        equity_df = pd.DataFrame(results['equity_curve'])
        equity_file = os.path.join(output_dir, 'backtest_equity.csv')
        equity_df.to_csv(equity_file, index=False)
        logger.info(f"Equity curve saved to {equity_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Backtest the JEPA + MPC crypto trading strategy")
    parser.add_argument('--symbol', type=str, default='BTCUSDT',
                        help='Trading pair (default: BTCUSDT)')
    parser.add_argument('--days', type=int, default=7,
                        help='Days of historical data (default: 7)')
    parser.add_argument('--capital', type=float, default=10000.0,
                        help='Initial capital in USDT (default: 10000)')
    parser.add_argument('--stop-loss', type=float, default=0.02,
                        help='Stop-loss percentage (default: 0.02 = 2%%)')
    parser.add_argument('--take-profit', type=float, default=0.03,
                        help='Take-profit percentage (default: 0.03 = 3%%)')
    parser.add_argument('--position-size', type=float, default=0.25,
                        help='Position size as fraction of capital (default: 0.25)')
    parser.add_argument('--save', action='store_true',
                        help='Save results to CSV files')
    args = parser.parse_args()

    engine = BacktestEngine(
        symbol=args.symbol,
        initial_capital=args.capital,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        position_size_pct=args.position_size)

    results = engine.run(days=args.days)

    print_report(results)

    if args.save:
        save_results(results)


if __name__ == "__main__":
    main()
