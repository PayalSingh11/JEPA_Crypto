"""
Portfolio Management & Risk Management for Crypto Trading Pipeline.

PortfolioManager: Tracks positions, capital, PnL, equity curve, and trade history.
RiskManager: Enforces stop-loss, take-profit, circuit breaker, and cooldown rules.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Tracks portfolio state: capital, position, PnL, equity curve, and trade history.
    Filters invalid actions (e.g., can't sell with no position).
    """

    def __init__(self, initial_capital: float = 10000.0, position_size_pct: float = 0.25,
                 trading_fee_pct: float = 0.001):
        """
        Args:
            initial_capital: Starting capital in USDT.
            position_size_pct: Fraction of capital to allocate per trade (0.25 = 25%).
            trading_fee_pct: Trading fee as a fraction (0.001 = 0.1% per trade, typical for Binance).
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position_size_pct = position_size_pct
        self.trading_fee_pct = trading_fee_pct

        # Current position
        self.position = 0.0          # Quantity of asset held (e.g., BTC)
        self.entry_price = 0.0       # Average entry price
        self.entry_time = None       # When the position was opened

        # PnL tracking
        self.realized_pnl = 0.0
        self.peak_equity = initial_capital

        # History
        self.trade_history: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self._pending_trade: Optional[Dict[str, Any]] = None

    @property
    def has_position(self) -> bool:
        return self.position > 1e-8

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL based on current price."""
        if not self.has_position:
            return 0.0
        return self.position * (current_price - self.entry_price)

    def get_total_equity(self, current_price: float) -> float:
        """Total portfolio value = capital + position value."""
        return self.capital + (self.position * current_price)

    def execute_action(self, raw_action: int, price: float, timestamp,
                       exit_reason: str = "signal") -> int:
        """
        Execute a trading action, filtering invalid ones.

        Args:
            raw_action: 0=hold, 1=buy, 2=sell (from MPC)
            price: Current asset price
            timestamp: Current timestamp
            exit_reason: Why the trade is happening ('signal', 'stop_loss', 'take_profit')

        Returns:
            actual_action: The action that was actually executed (may differ from raw_action)
        """
        actual_action = 0  # Default to hold

        if raw_action == 1:  # BUY
            if not self.has_position:
                actual_action = self._open_position(price, timestamp)
            else:
                logger.debug("BUY signal ignored — already in position")

        elif raw_action == 2:  # SELL
            if self.has_position:
                actual_action = self._close_position(price, timestamp, exit_reason)
            else:
                logger.debug("SELL signal ignored — no position to close")

        # Record equity curve
        equity = self.get_total_equity(price)
        self.peak_equity = max(self.peak_equity, equity)
        ts_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        self.equity_curve.append({
            'timestamp': ts_str,
            'equity': round(equity, 2),
            'capital': round(self.capital, 2),
            'position_value': round(self.position * price, 2),
            'drawdown_pct': round((1 - equity / self.peak_equity) * 100, 2) if self.peak_equity > 0 else 0
        })
        # Keep last 2000 entries
        if len(self.equity_curve) > 2000:
            self.equity_curve.pop(0)

        return actual_action

    def _open_position(self, price: float, timestamp) -> int:
        """Open a new long position."""
        spend_amount = self.capital * self.position_size_pct
        fee = spend_amount * self.trading_fee_pct
        net_spend = spend_amount - fee
        quantity = net_spend / price

        if quantity < 1e-8:
            logger.warning("Insufficient capital to open position")
            return 0

        self.capital -= spend_amount
        self.position = quantity
        self.entry_price = price
        self.entry_time = timestamp

        self._pending_trade = {
            'entry_time': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
            'entry_price': round(price, 2),
            'quantity': round(quantity, 8),
            'cost': round(spend_amount, 2),
            'entry_fee': round(fee, 2),
        }

        logger.info(f"OPENED position: {quantity:.6f} @ ${price:.2f} "
                     f"(spent ${spend_amount:.2f}, fee ${fee:.2f})")
        return 1

    def _close_position(self, price: float, timestamp, exit_reason: str = "signal") -> int:
        """Close the current position."""
        proceeds = self.position * price
        fee = proceeds * self.trading_fee_pct
        net_proceeds = proceeds - fee

        pnl = net_proceeds - (self.position * self.entry_price)
        pnl_pct = ((price / self.entry_price) - 1) * 100 if self.entry_price > 0 else 0

        self.capital += net_proceeds
        self.realized_pnl += pnl

        # Record completed trade
        if self._pending_trade:
            self._pending_trade.update({
                'exit_time': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                'exit_price': round(price, 2),
                'proceeds': round(net_proceeds, 2),
                'exit_fee': round(fee, 2),
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'exit_reason': exit_reason,
            })
            # Calculate duration
            if self.entry_time:
                try:
                    if hasattr(timestamp, 'total_seconds'):
                        duration = timestamp - self.entry_time
                    else:
                        duration = timestamp - self.entry_time
                    self._pending_trade['duration_minutes'] = round(
                        duration.total_seconds() / 60, 1)
                except Exception:
                    self._pending_trade['duration_minutes'] = 0

            self.trade_history.append(self._pending_trade)
            self._pending_trade = None

        logger.info(f"CLOSED position: {self.position:.6f} @ ${price:.2f} "
                     f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}%, reason: {exit_reason})")

        self.position = 0.0
        self.entry_price = 0.0
        self.entry_time = None
        return 2

    def force_close(self, price: float, timestamp, reason: str = "stop_loss") -> int:
        """Force close a position (called by risk manager)."""
        if self.has_position:
            return self._close_position(price, timestamp, exit_reason=reason)
        return 0

    def get_portfolio_state(self, current_price: float = 0.0) -> Dict[str, Any]:
        """Get serializable portfolio state for dashboard."""
        unrealized = self.get_unrealized_pnl(current_price)
        equity = self.get_total_equity(current_price)
        total_return = ((equity / self.initial_capital) - 1) * 100

        return {
            'initial_capital': round(self.initial_capital, 2),
            'capital': round(self.capital, 2),
            'position': round(self.position, 8),
            'entry_price': round(self.entry_price, 2),
            'has_position': self.has_position,
            'unrealized_pnl': round(unrealized, 2),
            'realized_pnl': round(self.realized_pnl, 2),
            'total_equity': round(equity, 2),
            'total_return_pct': round(total_return, 2),
            'peak_equity': round(self.peak_equity, 2),
            'current_drawdown_pct': round((1 - equity / self.peak_equity) * 100, 2) if self.peak_equity > 0 else 0,
            'total_trades': len(self.trade_history),
            'equity_curve': self.equity_curve[-200:],  # Last 200 points for dashboard
            'trade_history': self.trade_history[-50:],  # Last 50 trades for dashboard
        }

    def reset(self):
        """Reset portfolio to initial state."""
        self.__init__(self.initial_capital, self.position_size_pct, self.trading_fee_pct)


class RiskManager:
    """
    Enforces risk controls: stop-loss, take-profit, circuit breaker, and cooldown.
    """

    def __init__(self, stop_loss_pct: float = 0.02, take_profit_pct: float = 0.03,
                 max_drawdown_pct: float = 0.10, cooldown_minutes: int = 5):
        """
        Args:
            stop_loss_pct: Exit if price drops this % from entry (0.02 = 2%).
            take_profit_pct: Exit if price rises this % from entry (0.03 = 3%).
            max_drawdown_pct: Halt trading if portfolio drops this % from peak (0.10 = 10%).
            cooldown_minutes: Don't re-enter for N minutes after a stop-loss.
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.cooldown_minutes = cooldown_minutes

        self.last_stop_loss_time = None
        self.circuit_breaker_active = False
        self.risk_events: List[Dict[str, Any]] = []

    def check_exit_conditions(self, entry_price: float, current_price: float) -> Optional[str]:
        """
        Check if the current position should be forcefully exited.

        Returns:
            'stop_loss', 'take_profit', or None
        """
        if entry_price <= 0:
            return None

        price_change_pct = (current_price - entry_price) / entry_price

        if price_change_pct <= -self.stop_loss_pct:
            return 'stop_loss'

        if price_change_pct >= self.take_profit_pct:
            return 'take_profit'

        return None

    def is_trading_allowed(self, portfolio_state: Dict[str, Any],
                           current_timestamp=None) -> tuple:
        """
        Check if new trades are allowed.

        Returns:
            (allowed: bool, reason: str)
        """
        # Check circuit breaker: max drawdown from peak
        current_drawdown = portfolio_state.get('current_drawdown_pct', 0) / 100
        if current_drawdown >= self.max_drawdown_pct:
            if not self.circuit_breaker_active:
                self.circuit_breaker_active = True
                self._log_risk_event('circuit_breaker', current_timestamp,
                                      f"Drawdown {current_drawdown*100:.1f}% exceeds max {self.max_drawdown_pct*100:.1f}%")
            return False, f"Circuit breaker: drawdown {current_drawdown*100:.1f}%"

        # Reset circuit breaker if drawdown recovers
        if self.circuit_breaker_active and current_drawdown < self.max_drawdown_pct * 0.5:
            self.circuit_breaker_active = False
            self._log_risk_event('circuit_breaker_reset', current_timestamp,
                                  "Drawdown recovered, trading resumed")

        # Check cooldown after stop-loss
        if self.last_stop_loss_time and current_timestamp:
            try:
                elapsed = current_timestamp - self.last_stop_loss_time
                if hasattr(elapsed, 'total_seconds'):
                    elapsed_minutes = elapsed.total_seconds() / 60
                else:
                    elapsed_minutes = float(elapsed) / 60
                if elapsed_minutes < self.cooldown_minutes:
                    remaining = self.cooldown_minutes - elapsed_minutes
                    return False, f"Cooldown: {remaining:.1f} min remaining after stop-loss"
            except Exception:
                pass

        return True, "OK"

    def on_stop_loss_triggered(self, timestamp):
        """Called when a stop-loss exit happens."""
        self.last_stop_loss_time = timestamp
        self._log_risk_event('stop_loss', timestamp, "Stop-loss triggered")

    def _log_risk_event(self, event_type: str, timestamp, description: str):
        """Log a risk event."""
        ts_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        event = {
            'type': event_type,
            'timestamp': ts_str,
            'description': description,
        }
        self.risk_events.append(event)
        logger.warning(f"RISK EVENT: [{event_type}] {description}")

    def get_risk_state(self) -> Dict[str, Any]:
        """Get serializable risk state for dashboard."""
        return {
            'stop_loss_pct': self.stop_loss_pct * 100,
            'take_profit_pct': self.take_profit_pct * 100,
            'max_drawdown_pct': self.max_drawdown_pct * 100,
            'cooldown_minutes': self.cooldown_minutes,
            'circuit_breaker_active': self.circuit_breaker_active,
            'recent_risk_events': self.risk_events[-10:],
        }
