#!/usr/bin/env python3
"""
Polymarket Arbitrage Bot - Multi-Market Runner

Runs the Flash Crash Strategy on multiple markets simultaneously.
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path
from typing import List

# Suppress noisy logs
logging.getLogger("src.websocket_client").setLevel(logging.WARNING)
logging.getLogger("src.bot").setLevel(logging.WARNING)

# Auto-load .env file
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.terminal_utils import Colors
from src.bot import TradingBot
from src.config import Config
from apps.flash_crash_strategy import FlashCrashStrategy, FlashCrashConfig


async def run_strategies(bot: TradingBot, strategies: List[FlashCrashStrategy]):
    """Run multiple strategies concurrently."""
    tasks = [asyncio.create_task(s.run()) for s in strategies]
    
    # Simple status loop
    print(f"{Colors.BOLD}Multi-Market Strategy Running...{Colors.RESET}")
    print(f"Monitoring: {', '.join(s.config.coin for s in strategies)}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # Print status summary every 5 seconds
            # Clear previous lines if you want, or just append
            print(f"\n{Colors.BOLD}--- Status Update ---{Colors.RESET}")
            for s in strategies:
                market_status = "Waiting..."
                if s.market.current_market:
                    mins, secs = s.market.current_market.get_countdown()
                    market_status = f"{mins:02d}:{secs:02d}"
                
                stats = s.positions.get_stats()
                pnl_color = Colors.GREEN if stats['total_pnl'] >= 0 else Colors.RED
                
                print(
                    f"{Colors.CYAN}[{s.config.coin}]{Colors.RESET} "
                    f"Time: {market_status} | "
                    f"Trades: {stats['trades_closed']} | "
                    f"PnL: {pnl_color}${stats['total_pnl']:+.2f}{Colors.RESET}"
                )
            await asyncio.sleep(5)
            
            # Check if any strategy failed
            for t in tasks:
                if t.done():
                    try:
                        t.result()
                    except Exception as e:
                        print(f"{Colors.RED}Strategy failed: {e}{Colors.RESET}")
    finally:
        # Cancel all
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Flash Crash Strategy on multiple markets"
    )
    parser.add_argument(
        "--coins",
        type=str,
        default="BTC,ETH,SOL,XRP",
        help="Comma-separated list of coins (default: BTC,ETH,SOL,XRP)"
    )
    parser.add_argument(
        "--size",
        type=float,
        default=5.0,
        help="Trade size in USDC (default: 5.0)"
    )
    parser.add_argument(
        "--drop",
        type=float,
        default=0.30,
        help="Drop threshold (default: 0.30)"
    )
    
    args = parser.parse_args()
    
    coins = [c.strip().upper() for c in args.coins.split(",")]

    # Check environment
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    safe_address = os.environ.get("POLY_PROXY_WALLET")

    if not private_key or not safe_address:
        print(f"{Colors.RED}Error: POLY_PRIVATE_KEY and POLY_PROXY_WALLET must be set{Colors.RESET}")
        print("Set them in .env file or export as environment variables")
        sys.exit(1)

    # Create bot
    config = Config.from_env()
    bot = TradingBot(config=config, private_key=private_key)

    if not bot.is_initialized():
        print(f"{Colors.RED}Error: Failed to initialize bot{Colors.RESET}")
        sys.exit(1)

    print(f"Bot initialized. Address: {bot.signer.address}")
    if config.use_gasless:
        print("Gasless mode: ENABLED")

    # Create strategies
    strategies = []
    for coin in coins:
        strategy_config = FlashCrashConfig(
            coin=coin,
            size=args.size,
            drop_threshold=args.drop,
            render_enabled=False  # vital!
        )
        strategy = FlashCrashStrategy(bot=bot, config=strategy_config)
        strategies.append(strategy)

    try:
        asyncio.run(run_strategies(bot, strategies))
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
