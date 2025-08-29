import asyncio
import json
import websockets
from collections import deque
import logging
import time

# --- Configuration ---
# Replace with real your API_TOKEN 
API_TOKEN = "YUa7FW6kqwyW" 
APP_ID = 85473
WEBSOCKET_ENDPOINT = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
SYMBOL = "R_100"
TRADE_TYPE = "DIGITEVEN" # Or "DIGITODD" depending on signal

# --- Martingale Parameters from test_1.xml ---
MARTINGALE_INIT_STAKE = 0.35
MARTINGALE_FACTOR = 1.2
MARTINGALE_LEVEL = 4
TARGET_PROFIT = 2.0
STOP_LOSS = 2.0

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("DerivBot")

class DerivBot:
    """A self-evolving, probabilistic trading bot for the Deriv Volatility 100 Index with enhanced predictive capabilities."""

    def __init__(self):
        self.history = deque(maxlen=200) # Deque to store historical and live ticks
        self.stake = MARTINGALE_INIT_STAKE
        self.loss_count = 0
        self.total_profit = 0.0
        self.trade_in_progress = False
        self.awaiting_outcome = False
        self.last_trade_action = None

    async def run(self):
        """Main loop to connect and process ticks."""
        while True:
            try:
                logger.info("Connecting to WebSocket...")
                async with websockets.connect(WEBSOCKET_ENDPOINT) as websocket:
                    logger.info("✅ Connection established. Subscribing to ticks history.")
                    await self._send_auth_and_subscribe(websocket)
                    
                    async for message in websocket:
                        data = json.loads(message)
                        msg_type = data.get('msg_type')

                        if msg_type == 'history':
                            await self._on_history(websocket, data)
                        elif msg_type == 'tick':
                            await self._on_tick(websocket, data)
                        elif msg_type == 'buy':
                            contract_id = data['buy']['contract_id']
                            longcode = data['buy']['longcode']
                            logger.info(f"✅ Trade placed. Contract ID: {contract_id}")
                            # No longer set trade_in_progress to False here, wait for outcome
                        elif msg_type == 'proposal_open':
                            # This message seems redundant based on your specific requirements
                            pass
                        elif msg_type == "ping":
                            await websocket.send(json.dumps({"pong": 1}))
            except websockets.exceptions.ConnectionClosed as e:
                logger.error("❌ WebSocket connection closed: %s. Reconnecting in 10s...", e)
                await asyncio.sleep(10)
            except Exception as e:
                logger.critical("Connection failed or a critical error occurred: %s. Retrying in 10s...", e)
                await asyncio.sleep(10)

    async def _send_auth_and_subscribe(self, websocket):
        """Authenticates and subscribes to market history and live ticks."""
        await websocket.send(json.dumps({
            "authorize": API_TOKEN
        }))
        await websocket.recv()
        await websocket.send(json.dumps({
            "ticks_history": SYMBOL,
            "end": "latest",
            "count": 200,
            "subscribe": 1
        }))
    
    async def _on_history(self, websocket, data):
        """Handles the historical ticks from the initial subscription."""
        candles = data['history']['times']
        
        for tick_time in candles:
            self.history.append({
                'time': int(tick_time),
                'price': float(data['history']['prices'][candles.index(tick_time)])
            })

        logger.info(f"Historical data loaded. Ticks collected: {len(self.history)}")
        logger.info("--- Waiting for live ticks to form a prediction... ---")

    async def _on_tick(self, websocket, data):
        """Handles new ticks, appends to history, and makes trading decisions."""
        current_price = float(data['tick']['quote'])
        tick_time = int(data['tick']['epoch'])
        
        # Check for the outcome of a recent trade
        if self.awaiting_outcome:
            last_digit = int(str(current_price)[-1])
            is_even = last_digit % 2 == 0
            
            outcome = "even" if is_even else "odd"
            is_win = (self.last_trade_action == "even" and is_even) or \
                     (self.last_trade_action == "odd" and not is_even)

            self._on_trade_outcome(is_win)
            self.awaiting_outcome = False
            self.trade_in_progress = False
            return
            
        self.history.append({'time': tick_time, 'price': current_price})

        if not self.trade_in_progress and len(self.history) >= 200:
            trade_signal = self._get_trade_signal()

            if trade_signal:
                logger.info(f"💡 Trade Signal received: {trade_signal}")
                self.last_trade_action = trade_signal
                # Wrap the trade call in a try/except for added robustness
                try:
                    await self._trade(websocket, trade_signal)
                    self.trade_in_progress = True
                    self.awaiting_outcome = True
                except Exception as e:
                    logger.error("❌ Failed to place trade: %s", e)
                    # Don't drop connection, just move on to next tick
                    self.trade_in_progress = False
                    self.awaiting_outcome = False

    async def _trade(self, websocket, action):
        """Places a trade with the current calculated stake."""
        payload = {
            "buy": 1,
            "price": self.stake,
            "parameters": {
                "amount": self.stake,
                "basis": "stake",
                "contract_type": "DIGITEVEN" if action == "even" else "DIGITODD",
                "currency": "USD",
                "duration": 1,
                "duration_unit": "t",
                "symbol": SYMBOL,
            }
        }
        await websocket.send(json.dumps(payload))
        logger.info(f"📈 Placed trade: {action} with stake ${self.stake:.2f}")

    def _get_trade_signal(self):
        """
        Predictive logic based on candlestick patterns and market trend.
        This is your custom logic from the original file, adapted to the new data structure.
        """
        if len(self.history) < 200:
            return None
        
        prices = [tick['price'] for tick in list(self.history)[-100:]]
        times = [tick['time'] for tick in list(self.history)[-100:]]
        
        if not prices or not times:
            return None

        virtual_candle = {
            'open': prices[0],
            'close': prices[-1],
            'high': max(prices),
            'low': min(prices),
            'epoch': times[-1]
        }
        
        details = self._get_candle_details(virtual_candle)
        patterns = self._recognize_patterns(virtual_candle)

        if not patterns:
            return None

        if "Bullish Engulfing" in patterns or "Hammer" in patterns:
            return "even"
        if "Bearish Engulfing" in patterns or "Shooting Star" in patterns:
            return "odd"
        
        last_digit = int(str(virtual_candle['close'])[-1])
        if last_digit % 2 == 0:
            return "even"
        if last_digit % 2 != 0:
            return "odd"

        return None

    def _get_candle_details(self, candle):
        """Extracts and calculates key details from a single candle."""
        open_price = float(candle["open"])
        close_price = float(candle["close"])
        high = float(candle["high"])
        low = float(candle["low"])
        body_size = abs(close_price - open_price)
        total_range = high - low
        
        details = {
            "is_bullish": close_price > open_price,
            "is_bearish": close_price < open_price,
            "body_size": body_size,
            "total_range": total_range,
            "open": open_price,
            "close": close_price,
            "high": high,
            "low": low,
            "upper_wick": high - max(open_price, close_price) if total_range > 0 else 0,
            "lower_wick": min(open_price, close_price) - low if total_range > 0 else 0
        }

        if total_range == 0 or (body_size / total_range) < 0.10:
            details["type"] = "Indecision"
        else:
            details["type"] = "Green" if details["is_bullish"] else "Red"
        
        return details

    def _is_uptrend(self, history_data, lookback_period=5):
        """Checks for an uptrend based on the last 'lookback_period' candles."""
        if len(history_data) < lookback_period:
            return False
        closes = [float(c['close']) for c in list(history_data)[-lookback_period:]]
        is_up = sum(closes) / len(closes) < closes[-1]
        return is_up

    def _is_downtrend(self, history_data, lookback_period=5):
        """Checks for a downtrend based on the last 'lookback_period' candles."""
        if len(history_data) < lookback_period:
            return False
        closes = [float(c['close']) for c in list(history_data)[-lookback_period:]]
        is_down = sum(closes) / len(closes) > closes[-1]
        return is_down

    def _recognize_patterns(self, candle):
        """Identifies and returns a set of recognized candlestick patterns."""
        patterns = set()
        
        details = self._get_candle_details(candle)
        
        # Single candle patterns
        if details['body_size'] < 0.0001:
            patterns.add("Doji")
        if details['total_range'] > 0:
            if (details['body_size'] / details['total_range']) < 0.3:
                patterns.add("Spinning Top")
            if (details['body_size'] / details['total_range']) > 0.9:
                patterns.add("Marubozu")
        return patterns

    def _on_trade_outcome(self, is_win):
        """Handles the outcome of a trade and updates the stake."""
        # Calculate profit/loss for logging
        payout_rate = 0.95 # This is a common rate for these types of contracts
        profit = self.stake * payout_rate
        
        if is_win:
            self.total_profit += profit
            self.stake = MARTINGALE_INIT_STAKE
            self.loss_count = 0
            logger.info("✅ WIN! Resetting stake to initial: $%s", round(self.stake, 2))
        else:
            self.total_profit -= self.stake
            self.loss_count += 1
            if self.loss_count <= MARTINGALE_LEVEL:
                self.stake *= MARTINGALE_FACTOR
                logger.warning("❌ LOSS. New stake due to Martingale: $%s. Loss streak: %s/%s", round(self.stake, 2), self.loss_count, MARTINGALE_LEVEL)
            else:
                logger.critical("‼️ Maximum Martingale level reached. Resetting stake to initial: $%s", round(self.stake, 2))
                self.stake = MARTINGALE_INIT_STAKE
                self.loss_count = 0
                
        # Check for profit target or stop loss
        if self.total_profit >= TARGET_PROFIT:
            logger.info("🎉 TARGET PROFIT REACHED! Total Profit: $%s. Shutting down bot.", round(self.total_profit, 2))
            exit()
        if self.total_profit <= -abs(STOP_LOSS):
            logger.info("🛑 STOP LOSS REACHED! Total Loss: $%s. Shutting down bot.", round(self.total_profit, 2))
            exit()
        
        logger.info("Current Total Profit: $%s", round(self.total_profit, 2))
        logger.info("--- Waiting for next signal... ---")


if __name__ == "__main__":
    bot = DerivBot()
    asyncio.run(bot.run())