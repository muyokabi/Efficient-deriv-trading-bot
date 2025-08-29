
Deriv Trading Bot (Martingale Strategy)

This project contains a self-contained, automated trading bot for the Deriv Volatility 100 Index. The bot is designed to trade "DIGIT EVEN" and "DIGIT ODD" contracts using a Martingale-based strategy.

Core Functionality
WebSocket Connection: The bot establishes a real-time WebSocket connection to the Deriv API to receive live price ticks.

Martingale Strategy: The bot implements a Martingale money management system.

It starts with an initial stake of $0.35.

After each loss, the stake is multiplied by a factor of 1.2, up to a maximum of 4 consecutive losses.

Upon a win or reaching the maximum loss level, the stake is reset to the initial amount.

Trading Logic: The bot's trading decisions are based on a custom predictive logic that analyzes candlestick patterns and market trends from a historical buffer of 200 ticks. It specifically looks for patterns like "Bullish Engulfing," "Hammer," "Bearish Engulfing," or "Shooting Star" to generate a signal.

Risk Management: It includes built-in risk management with a stop-loss and a profit target, configured at $2.00 for both.

Logging: All bot activity, including connection status, trade placements, and results, is logged to the console.

How It Works
Connection: The bot connects to the Deriv WebSocket API using an APP_ID and API_TOKEN.

Data Collection: It subscribes to a stream of ticks and stores the most recent 200 ticks in a history buffer.

Signal Generation: Once the history buffer is full, the bot's internal logic continuously analyzes the price data to identify patterns and generate a trade signal ("even" or "odd").

Trade Execution: If a signal is generated, the bot places a trade with the calculated stake.

Outcome Management: The bot waits for the outcome of the trade (win or loss) to adjust its stake based on the Martingale strategy and update its total profit.

Looping: The process of data collection, signal generation, and trading continues until the predefined profit target or stop-loss is reached, at which point the bot will shut down.
