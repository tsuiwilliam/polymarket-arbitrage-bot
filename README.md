# Polymarket Arbitrage Bot - Enhanced Edition

Production-ready Python trading bot for Polymarket with gasless transactions, real-time WebSocket orderbook streaming, and advanced multi-market capabilities.

> **This is an enhanced fork** with significant improvements to authentication, multi-market trading, position management, and developer tools.

## 🚀 Key Features

### Core Trading
- **Gasless Trading** - Full Builder Program integration with automatic proxy wallet setup
- **Multi-Market Support** - Run strategies across BTC, ETH, SOL, and XRP simultaneously
- **Real-time WebSocket** - Live orderbook updates with automatic reconnection
- **15-Minute Markets** - Built-in support for high-frequency 15-minute prediction markets
- **Position Management** - Automated take-profit and stop-loss with PnL tracking

### Strategy Framework
- **Base Strategy Class** - Extensible framework for building custom strategies
- **Flash Crash Strategy** - Pre-built volatility trading strategy with configurable parameters
- **Market Manager** - Automatic market discovery and switching when markets expire
- **Price Tracker** - Real-time price history and pattern detection
- **Position Manager** - Multi-position tracking with TP/SL automation

### Developer Tools
- **Debug Suite** - 12+ debug scripts for testing authentication, orders, balances, and API keys
- **Interactive Setup** - Guided credential configuration with validation
- **Terminal UI** - Rich terminal interface with color-coded status updates
- **Comprehensive Logging** - Structured logging with configurable levels

## 📦 Installation

```bash
git clone https://github.com/tsuiwilliam/polymarket-algo-bot.git
cd polymarket-algo-bot
pip install -r requirements.txt
```

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required: Your wallet credentials
POLY_PRIVATE_KEY=your_private_key_here
POLY_SAFE_ADDRESS=0xYourPolymarketProxyWallet

# Required for Gasless Trading: Builder Program credentials
POLY_BUILDER_API_KEY=your_api_key
POLY_BUILDER_API_SECRET=your_api_secret
POLY_BUILDER_API_PASSPHRASE=your_passphrase
```

> **Finding Your Proxy Wallet**: Visit [polymarket.com/settings](https://polymarket.com/settings) → General → Wallet Address

> **Builder Program**: Apply at [polymarket.com/settings?tab=builder](https://polymarket.com/settings?tab=builder) for gasless trading

### Configuration File (Optional)

Create `config.yaml` for advanced settings:

```yaml
safe_address: "0xYourAddress"
rpc_url: "https://polygon-rpc.com"

clob:
  host: "https://clob.polymarket.com"
  chain_id: 137
  signature_type: 2  # Gnosis Safe

builder:
  api_key: "your_key"
  api_secret: "your_secret"
  api_passphrase: "your_passphrase"

default_size: 5.0
log_level: "INFO"
```

## 🎯 Quick Start

### 1. Orderbook Viewer (Read-Only)

View real-time orderbook data without trading:

```bash
# View ETH market orderbook
python apps/orderbook_viewer.py --coin ETH

# View BTC market
python apps/orderbook_viewer.py --coin BTC
```

**Features:**
- Real-time price updates
- Bid/ask spread visualization
- Market countdown timer
- No credentials required

### 2. Single Market Trading

Run the flash crash strategy on a single market:

```bash
# Run with default settings (ETH, $5 size, 30% drop threshold)
python apps/flash_crash_runner.py --coin ETH

# Customize parameters
python apps/flash_crash_runner.py \
  --coin BTC \
  --size 10.0 \
  --drop 0.25 \
  --take-profit 0.15 \
  --stop-loss 0.08
```

### 3. Multi-Market Trading (NEW!)

Run strategies across multiple markets simultaneously:

```bash
# Trade all major coins with default settings
python apps/run_multi.py --coins BTC,ETH,SOL,XRP

# Customize for specific coins with custom parameters
python apps/run_multi.py \
  --coins BTC,ETH \
  --size 10.0 \
  --drop 0.20 \
  --take-profit 0.12 \
  --stop-loss 0.06
```

**Multi-Market Features:**
- Consolidated dashboard showing all markets
- Individual PnL tracking per market
- Shared WebSocket connection for efficiency
- Real-time balance and position updates
- Automatic market switching when markets expire

## 📊 Trading Strategies

### Flash Crash Strategy

Monitors 15-minute markets for sudden probability drops and executes trades automatically.

**How It Works:**
1. Tracks price history over a lookback window
2. Detects sudden drops exceeding threshold
3. Places buy orders at favorable prices
4. Automatically exits at take-profit or stop-loss levels

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--coin` | ETH | Coin to trade (BTC, ETH, SOL, XRP) |
| `--size` | 5.0 | Trade size in USDC |
| `--drop` | 0.30 | Drop threshold (30% = 0.30) |
| `--lookback` | 10 | Detection window in seconds |
| `--take-profit` | 0.10 | Take profit in dollars |
| `--stop-loss` | 0.05 | Stop loss in dollars |

**Example:**
```bash
# Conservative strategy: larger drop threshold, tighter stops
python apps/flash_crash_runner.py \
  --coin ETH \
  --drop 0.40 \
  --take-profit 0.08 \
  --stop-loss 0.04

# Aggressive strategy: smaller drop threshold, wider stops
python apps/flash_crash_runner.py \
  --coin BTC \
  --drop 0.20 \
  --take-profit 0.20 \
  --stop-loss 0.10
```

## 🛠️ Developer Tools

### Debug Scripts

Located in `apps/`, these scripts help diagnose issues:

```bash
# Test authentication and API key binding
python apps/debug_auth.py
python apps/debug_api_key_binding.py

# Check balance and wallet info
python apps/debug_balance.py

# Test order placement
python apps/debug_order.py

# Verify gasless transactions
python apps/debug_gasless.py

# Test proxy wallet authentication
python apps/debug_proxy_auth.py
```

### Setup Wizard

Interactive credential setup:

```bash
python apps/run_setup.py
```

This will guide you through:
- Private key configuration
- Proxy wallet setup
- Builder Program credentials
- Validation of all settings

## 📚 API Reference

### TradingBot

Main bot interface for order execution:

```python
from src import TradingBot, Config

bot = TradingBot(config=Config.from_env(), private_key="0x...")

# Place orders
result = await bot.place_order(
    token_id="token_id",
    price=0.65,
    size=10.0,
    side="BUY"
)

# Get account info
balance = await bot.get_collateral_balance()
orders = await bot.get_open_orders()
trades = await bot.get_trades()

# Market data
orderbook = await bot.get_order_book(token_id)
price = await bot.get_market_price(token_id)
```

### MarketManager (NEW!)

Manages market discovery and WebSocket connections:

```python
from lib.market_manager import MarketManager

market = MarketManager(
    coin="BTC",
    market_check_interval=30.0,
    auto_switch_market=True
)

await market.start()

# Get market info
current = market.current_market
token_ids = market.token_ids

# Get orderbook data
orderbook = market.get_orderbook("up")
mid_price = market.get_mid_price("up")
spread = market.get_spread("up")

# Register callbacks
@market.on_book_update
async def handle_update(snapshot):
    print(f"Price: {snapshot.mid_price}")

@market.on_market_change
def handle_change(old_slug, new_slug):
    print(f"Market changed: {old_slug} -> {new_slug}")
```

### PositionManager (NEW!)

Tracks positions with automatic TP/SL:

```python
from lib.position_manager import PositionManager

positions = PositionManager(
    take_profit=0.10,
    stop_loss=0.05,
    max_positions=1
)

# Open position
pos = positions.open_position(
    side="up",
    token_id="token_id",
    entry_price=0.50,
    size=10.0
)

# Check exits
exits = positions.check_all_exits({"up": 0.55, "down": 0.45})
for position, exit_type, pnl in exits:
    if exit_type == "take_profit":
        print(f"Take profit triggered: ${pnl:.2f}")

# Get statistics
stats = positions.get_stats()
print(f"Win rate: {stats['win_rate']:.1f}%")
print(f"Total PnL: ${stats['total_pnl']:.2f}")
```

### PriceTracker (NEW!)

Real-time price tracking and pattern detection:

```python
from lib.price_tracker import PriceTracker

tracker = PriceTracker(
    lookback_seconds=10,
    max_history=100
)

# Record prices
tracker.record("up", 0.50)
tracker.record("up", 0.48)

# Get statistics
stats = tracker.get_stats("up")
print(f"Min: {stats['min']}, Max: {stats['max']}")
print(f"Drop: {stats['drop']:.2%}")

# Detect patterns
if tracker.detect_drop("up", threshold=0.30):
    print("Flash crash detected!")
```

### BaseStrategy (NEW!)

Abstract base class for building custom strategies:

```python
from apps.base_strategy import BaseStrategy, StrategyConfig
from src.websocket_client import OrderbookSnapshot

class MyStrategy(BaseStrategy):
    async def on_book_update(self, snapshot: OrderbookSnapshot):
        """Handle orderbook updates."""
        if snapshot.mid_price < 0.30:
            await self.execute_buy("up", snapshot.mid_price)
    
    async def on_tick(self, prices: dict):
        """Called each strategy tick."""
        # Check positions, update state, etc.
        pass
    
    def render_status(self, prices: dict):
        """Render terminal UI."""
        print(f"UP: {prices.get('up', 0):.3f}")

# Run strategy
config = StrategyConfig(coin="ETH", size=5.0)
strategy = MyStrategy(bot, config)
await strategy.run()
```

### WebSocket Client

Real-time market data streaming:

```python
from src.websocket_client import MarketWebSocket

ws = MarketWebSocket()

@ws.on_book
async def handle_book(snapshot):
    print(f"Price: {snapshot.mid_price:.4f}")
    print(f"Spread: {snapshot.spread:.4f}")

await ws.subscribe(["token_id_1", "token_id_2"])
await ws.run()
```

## 🏗️ Project Structure

```
polymarket-arbitrage-bot/
├── src/                          # Core library
│   ├── bot.py                    # Main TradingBot class
│   ├── client.py                 # CLOB API client
│   ├── websocket_client.py       # WebSocket streaming
│   ├── signer.py                 # Transaction signing
│   ├── config.py                 # Configuration management
│   ├── gamma_client.py           # Gamma API for market data
│   └── utils.py                  # Utility functions
│
├── lib/                          # Reusable components (NEW!)
│   ├── market_manager.py         # Market discovery & WebSocket management
│   ├── position_manager.py       # Position tracking with TP/SL
│   ├── price_tracker.py          # Price history and pattern detection
│   └── terminal_utils.py         # Terminal UI utilities
│
├── apps/                         # Application entry points
│   ├── run_multi.py              # Multi-market runner (NEW!)
│   ├── flash_crash_runner.py     # Single market runner
│   ├── flash_crash_strategy.py   # Flash crash strategy implementation
│   ├── base_strategy.py          # Base strategy class (NEW!)
│   ├── orderbook_viewer.py       # Real-time orderbook viewer
│   ├── run_setup.py              # Interactive setup wizard
│   ├── test_strategy_logic.py    # Strategy logic tests
│   └── debug_*.py                # Debug utilities (12 scripts)
│
├── config.example.yaml           # Example configuration file
├── .env.example                  # Example environment variables
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## 🔒 Security

### Private Key Protection

Private keys are encrypted using:
- **PBKDF2** with 480,000 iterations
- **Fernet** symmetric encryption
- Secure file permissions (0600)

### Best Practices

1. **Never commit `.env` files** - Add to `.gitignore`
2. **Use a dedicated trading wallet** - Don't use your main wallet
3. **Keep encrypted key files secure** - Set proper file permissions
4. **Rotate API keys regularly** - Especially Builder Program credentials
5. **Monitor your positions** - Set appropriate stop-losses
6. **Test with small amounts first** - Validate setup before scaling

### Environment Security

```bash
# Set proper permissions on .env file
chmod 600 .env

# Verify .env is in .gitignore
grep -q "^\.env$" .gitignore || echo ".env" >> .gitignore
```

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Missing credentials** | Set `POLY_PRIVATE_KEY` and `POLY_SAFE_ADDRESS` in `.env` |
| **Invalid private key** | Ensure 64 hex characters (0x prefix optional) |
| **Order failed** | Check sufficient USDC balance with `python apps/debug_balance.py` |
| **WebSocket errors** | Verify network/firewall settings, check internet connection |
| **Gasless not working** | Verify Builder credentials, run `python apps/debug_gasless.py` |
| **Authentication failed** | Run `python apps/debug_auth.py` to diagnose |
| **API key binding error** | Run `python apps/debug_api_key_binding.py` |
| **Market not found** | Ensure 15-minute market is active for the selected coin |

### Debug Workflow

1. **Test authentication**: `python apps/debug_auth.py`
2. **Check balance**: `python apps/debug_balance.py`
3. **Verify gasless**: `python apps/debug_gasless.py`
4. **Test orders**: `python apps/debug_order.py`
5. **View orderbook**: `python apps/orderbook_viewer.py --coin ETH`

### Enable Debug Logging

```bash
# Set environment variable for detailed logs
export POLY_DEBUG_LOG=1

# Run your script - logs will be written to bot_debug.log
python apps/run_multi.py --coins BTC,ETH
```

## 📈 Performance Tips

1. **Use gasless trading** - Eliminates gas fees and speeds up execution
2. **Multi-market mode** - Shares WebSocket connection for efficiency
3. **Adjust lookback window** - Shorter windows = faster detection but more noise
4. **Optimize order size** - Larger orders may have worse fills
5. **Monitor spreads** - Wide spreads reduce profitability

## 🔄 What's New in This Fork

### Major Enhancements

✅ **Multi-Market Support** - Trade multiple coins simultaneously with consolidated dashboard  
✅ **Base Strategy Framework** - Extensible architecture for building custom strategies  
✅ **Market Manager** - Automatic market discovery and switching  
✅ **Position Manager** - Automated TP/SL with comprehensive PnL tracking  
✅ **Price Tracker** - Real-time price history and pattern detection  
✅ **Debug Suite** - 12+ debug scripts for troubleshooting  
✅ **Interactive Setup** - Guided credential configuration wizard  
✅ **Enhanced Authentication** - Improved proxy wallet and gasless transaction handling  
✅ **Terminal UI** - Rich color-coded status updates  
✅ **Comprehensive Logging** - Structured logging with configurable levels  

### Bug Fixes

🔧 Fixed authentication issues with proxy wallets  
🔧 Improved order validation and error handling  
🔧 Enhanced WebSocket reconnection logic  
🔧 Better balance checking and display  
🔧 Resolved API key binding errors  

## 📝 Usage Examples

### Basic Trading Bot

```python
from src import create_bot_from_env
import asyncio

async def main():
    bot = create_bot_from_env()
    
    # Check balance
    balance = await bot.get_collateral_balance()
    print(f"Balance: ${balance:.2f}")
    
    # Get open orders
    orders = await bot.get_open_orders()
    print(f"Open orders: {len(orders)}")

asyncio.run(main())
```

### Custom Strategy

```python
from apps.base_strategy import BaseStrategy, StrategyConfig
from src import TradingBot, Config

class MeanReversionStrategy(BaseStrategy):
    async def on_book_update(self, snapshot):
        # Get current price
        price = snapshot.mid_price
        
        # Get price statistics
        stats = self.prices.get_stats(snapshot.asset_id)
        
        # Buy if price drops below mean
        if price < stats['mean'] - 0.05:
            await self.execute_buy("up", price)
    
    async def on_tick(self, prices):
        # Check for exits
        pass
    
    def render_status(self, prices):
        market = self.current_market
        print(f"Market: {market.question if market else 'N/A'}")
        print(f"UP: {prices.get('up', 0):.3f} | DOWN: {prices.get('down', 0):.3f}")

# Run strategy
bot = TradingBot(config=Config.from_env(), private_key="0x...")
config = StrategyConfig(coin="ETH", size=10.0)
strategy = MeanReversionStrategy(bot, config)
await strategy.run()
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Trading involves risk of loss. The developers are not responsible for any financial losses incurred while using this bot. Always test with small amounts first and never trade more than you can afford to lose.

## 🤝 Support

For questions, issues, or contributions:
- **GitHub Issues**: [Report bugs or request features](https://github.com/tsuiwilliam/polymarket-algo-bot/issues)
- **Original Author**: [@Vladmeer](https://t.me/vladmeer67) | [@Vladmeer](https://x.com/vladmeer67)

## 🙏 Acknowledgments

This is an enhanced fork of the original [Polymarket Arbitrage Bot](https://github.com/vladmeer/polymarket-arbitrage-bot) by [@Vladmeer](https://github.com/vladmeer). Major enhancements include multi-market support, strategy framework, and comprehensive developer tools.
