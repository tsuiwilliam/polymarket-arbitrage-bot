"""
Strategy Logic Verification Test.
Mocks a flash crash and verifies the strategy triggers a buy.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock
from apps.flash_crash_strategy import FlashCrashStrategy, FlashCrashConfig
from src.bot import TradingBot
from src.websocket_client import OrderbookSnapshot
from lib.terminal_utils import Colors

async def test_logic():
    print("=" * 80)
    print("STRATEGY LOGIC VERIFICATION (MOCK TEST)")
    print("=" * 80)

    # 1. Setup Mock Bot
    bot = MagicMock(spec=TradingBot)
    bot.place_order = AsyncMock(return_value=MagicMock(success=True))
    bot.config = MagicMock()
    bot.config.clob.signature_type = 0
    bot.signer = MagicMock()
    bot.signer.address = "0xMockSigner"

    # 2. Setup Strategy
    config = FlashCrashConfig(
        coin="BTC",
        drop_threshold=0.20,  # 20% drop
        trade_size=1.0,
        lookback_seconds=10
    )
    strategy = FlashCrashStrategy(bot, config)
    
    # Mock market manager
    strategy.market = MagicMock()
    strategy.market.current_market.get_countdown.return_value = (5, 0)
    strategy.market.get_orderbook.return_value = None
    strategy.market.get_mid_price.return_value = 0.5

    print(f"\n- Strategy initialized with drop_threshold={config.drop_threshold}")

    # 3. Simulate high price history
    print("- Recording 5 seconds of stable high price (0.80)...")
    for i in range(5):
        strategy.prices.record("up", 0.80, timestamp=i)
    
    # Check detection (should be None)
    event = strategy.prices.detect_flash_crash()
    print(f"- Detection status (stable): {'CRASH!' if event else 'Normal'}")

    # 4. Simulate sudden crash
    print(f"- Simulating crash: 0.80 -> 0.50 (Drop: 0.30)...")
    # Record current price that is lower
    strategy.prices.record("up", 0.50, timestamp=10)
    
    # 5. Check detection
    event = strategy.prices.detect_flash_crash()
    if event:
        print(f"{Colors.GREEN}- Detection status (CRASH): SUCCESS! Drop: {event.drop:.2f}{Colors.RESET}")
    else:
        print(f"{Colors.RED}- Detection status (CRASH): FAILED! No event detected.{Colors.RESET}")

    # 6. Run on_tick to trigger buy
    print("- Running on_tick to trigger execution...")
    await strategy.on_tick({"up": 0.50, "down": 0.50})

    # 7. Verify buy call
    if bot.place_order.called:
        args, kwargs = bot.place_order.call_args
        print(f"{Colors.GREEN}- SUCCESS: bot.place_order was called for {args[0]} at {args[1]}{Colors.RESET}")
        print(f"  Order Details: Side={args[0]}, Price={args[1]}, Size={args[2]}")
    else:
        print(f"{Colors.RED}- FAILED: bot.place_order was NOT called!{Colors.RESET}")

    print("\n" + "=" * 80)
    if event and bot.place_order.called:
        print(f"{Colors.BOLD}{Colors.GREEN}VERIFICATION RESULT: PASSED{Colors.RESET}")
        print("Strategy conditions are intact and correctly trigger orders.")
    else:
        print(f"{Colors.BOLD}{Colors.RED}VERIFICATION RESULT: FAILED{Colors.RESET}")
        print("Strategy logic has a flaw.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_logic())
