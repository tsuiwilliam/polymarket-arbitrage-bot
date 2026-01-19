#!/usr/bin/env python3
"""
Polymarket Arbitrage Bot - Multi-Market Runner

Runs the Flash Crash Strategy on multiple markets simultaneously
with a condensed TUI dashboard.
"""

import os
import sys
import asyncio
import argparse
import logging
import time
from pathlib import Path
from typing import List

# Suppress noisy logs
logging.getLogger("src.websocket_client").setLevel(logging.INFO)
logging.getLogger("src.bot").setLevel(logging.INFO)

# Setup logging to file if requested
if os.environ.get("POLY_DEBUG_LOG"):
    file_handler = logging.FileHandler("bot_debug.log")
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    print(f"\n[DEBUG] Detailed logs being written to bot_debug.log\n")

# Auto-load .env file
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.terminal_utils import Colors
from lib.market_manager import MarketManager
from src.bot import TradingBot
from src.config import Config
from apps.flash_crash_strategy import FlashCrashStrategy, FlashCrashConfig

async def run_strategies(bot: TradingBot, strategies: List[FlashCrashStrategy]):
    """Run multiple strategies concurrently."""
    tasks = [asyncio.create_task(s.run()) for s in strategies]
    
    # Start shared WebSocket if available
    if bot.clob_client and bot.clob_client.ws:
        tasks.append(asyncio.create_task(bot.clob_client.ws.run_until_cancelled()))
    
    # Hide cursor
    print("\033[?25l", end="")

    try:
        while True:
            # Build TUI Buffer
            lines = []
            
            # Fetch balance
            balance = await bot.get_collateral_balance()
            
            # Get wallet info
            maker_address = bot.config.safe_address if bot.config.clob.signature_type == 2 else bot.signer.address
            sig_type_name = "Proxy" if bot.config.clob.signature_type == 2 else "EOA"
            
            lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
            lines.append(f"{Colors.BOLD} Multi-Market Bot | Balance: ${balance:.2f}{Colors.RESET}")
            lines.append(f"{Colors.CYAN} Wallet: {maker_address[:10]}...{maker_address[-8:]} ({sig_type_name}){Colors.RESET}")
            lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
            
            # Header
            lines.append(
                f"{'Coin':<6} | {'Price (Up/Down)':<16} | {'Spread':<8} | {'Time':<6} | {'Trades':<6} | {'PnL':<10}"
            )
            lines.append("-" * 80)
            
            total_pnl = 0.0
            
            for s in strategies:
                market = s.market.current_market
                time_str = "--:--"
                up_price = 0.0
                down_price = 0.0
                spread = 0.0
                
                if market:
                    mins, secs = market.get_countdown()
                    time_str = f"{mins:02d}:{secs:02d}"
                    up_price = s.market.get_mid_price("up")
                    down_price = s.market.get_mid_price("down")
                    
                    # Avg spread
                    spread = (s.market.get_spread("up") + s.market.get_spread("down")) / 2
                
                stats = s.positions.get_stats()
                pnl = stats['total_pnl']
                total_pnl += pnl
                pnl_color = Colors.GREEN if pnl >= 0 else Colors.RED
                
                # Prices color
                price_str = f"{up_price:.3f} / {down_price:.3f}"
                
                line = (
                    f"{Colors.CYAN}{s.config.coin:<6}{Colors.RESET} | "
                    f"{price_str:<16} | "
                    f"{spread:<8.4f} | "
                    f"{time_str:<6} | "
                    f"{stats['trades_closed']:<6} | "
                    f"{pnl_color}${pnl:<9.2f}{Colors.RESET}"
                )
                lines.append(line)
            
            lines.append("-" * 80)
            lines.append(f"Total Session PnL: {Colors.GREEN if total_pnl >= 0 else Colors.RED}${total_pnl:.2f}{Colors.RESET}")
            lines.append(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
            
            # Show recent logs from first strategy (primary log source)
            # or merge logs? Merging is better
            lines.append(f"{Colors.BOLD}Recent Activity:{Colors.RESET}")
            
            # Collect last 5 logs from all strategies
            recent_logs = []
            for s in strategies:
                 msgs = s._log_buffer.get_messages()
                 for m in msgs:
                     recent_logs.append(f"[{s.config.coin}] {m}")
            
            # Sort simplistic or just take last 5
            # Since they are strings, we can't easily sort by time without parsing
            # Just show last 5 added
            for msg in recent_logs[-5:]:
                lines.append(msg)

            # Move cursor up and print
            output = "\033[H\033[J" + "\n".join(lines)
            print(output, flush=True)
            
            await asyncio.sleep(0.5)
            
            # Check failures
            for t in tasks:
                 if t.done():
                     t.result() # Raise exception
                     
    finally:
        print("\033[?25h", end="") # Show cursor
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Multi-Market Runner")
    parser.add_argument("--coins", type=str, default="BTC,ETH,SOL,XRP")
    parser.add_argument("--size", type=float, default=5.0)
    parser.add_argument("--drop", type=float, default=0.30)
    parser.add_argument("--take-profit", type=float, default=0.10)
    parser.add_argument("--stop-loss", type=float, default=0.05)
    
    args = parser.parse_args()
    coins = [c.strip().upper() for c in args.coins.split(",")]

    private_key = os.environ.get("POLY_PRIVATE_KEY")
    if private_key:
        private_key = private_key.strip().replace('"', '').replace("'", "")
    
    if not private_key:
        print(f"{Colors.RED}Error: POLY_PRIVATE_KEY is missing in .env{Colors.RESET}")
        sys.exit(1)

    # --- RESET ENV WIZARD ---
    print(f"\n{Colors.CYAN}Current Configuration:{Colors.RESET}")
    print(f"  Wallet: {private_key[-6:]} (Private Key)")
    
    do_reset = input(f"{Colors.BOLD}Do you want to RESET/RECONFIGURE your environment credentials? (y/n): {Colors.RESET}").strip().lower()
    if do_reset in ('y', 'yes'):
        print(f"\n{Colors.YELLOW}--- RESETTING CREDENTIALS ---{Colors.RESET}")
        
        # 1. Private Key
        new_pk = input("Enter your Private Key: ").strip().replace('"', '').replace("'", "")
        if new_pk:
            private_key = new_pk
            os.environ["POLY_PRIVATE_KEY"] = new_pk
        
        # 2. Master Builder
        print(f"\n{Colors.BOLD}Do you want to set up Master Builder (Gasless) credentials? (y/n): {Colors.RESET}")
        do_mb = input().strip().lower()
        if do_mb in ('y', 'yes'):
            m_key = input("Builder API Key: ").strip()
            m_secret = input("Builder API Secret: ").strip()
            m_pass = input("Builder API Passphrase: ").strip()
            
            if m_key and m_secret and m_pass:
                os.environ["POLY_MASTER_BUILDER_KEY"] = m_key
                os.environ["POLY_MASTER_BUILDER_SECRET"] = m_secret
                os.environ["POLY_MASTER_BUILDER_PASSPHRASE"] = m_pass
                # Reset standard builder keys too just in case
                if os.environ.get("POLY_BUILDER_API_KEY"):
                    del os.environ["POLY_BUILDER_API_KEY"]
                print(f"{Colors.GREEN}✓ Master Builder credentials staged.{Colors.RESET}")
            else:
                print(f"{Colors.RED}✗ Invalid inputs. Skipping Builder setup.{Colors.RESET}")
        
        # Save to .env logic could go here, but for now we just update session env
        # A full .env writer would be better, but this solves the immediate "ask me" request
        print(f"{Colors.GREEN}✓ Session credentials updated.{Colors.RESET}\n")

    config = Config.from_env()

    # --- DEBUG START ---
    debug_msg = f"""
[DEBUG] Config State:
- Use Gasless: {config.use_gasless}
- Signature Type: {config.clob.signature_type}
- Builder Configured: {config.builder.is_configured()}
- Safe Address: {config.safe_address}
- Env Builder Key Present: {bool(os.environ.get('POLY_BUILDER_API_KEY'))}
- Env Master Key Present: {bool(os.environ.get('POLY_MASTER_BUILDER_KEY'))}
    """
    print(debug_msg)
    with open("config_debug.txt", "w") as f:
        f.write(debug_msg)
    # --- DEBUG END ---
    
    # Interactive Setup for Gasless Mode
    if not config.use_gasless:
        print(f"\n{Colors.YELLOW}Gasless transactions are NOT configured.{Colors.RESET}")
        print("To enable 'One-Click' automated setup (auto-proxy & gasless trades),")
        print("you need to provide Master Builder credentials (or your own Builder keys).")
        
        choice = input(f"\n{Colors.BOLD}Do you want to set them up now? (y/n): {Colors.RESET}").strip().lower()
        if choice in ('y', 'yes'):
            print(f"\n{Colors.CYAN}--- Master Builder Setup ---{Colors.RESET}")
            print("Enter the credentials. These will be used for this session.")
            m_key = input("API Key: ").strip()
            m_secret = input("API Secret: ").strip()
            m_pass = input("Passphrase: ").strip()
            
            if m_key and m_secret and m_pass:
                os.environ["POLY_MASTER_BUILDER_KEY"] = m_key
                os.environ["POLY_MASTER_BUILDER_SECRET"] = m_secret
                os.environ["POLY_MASTER_BUILDER_PASSPHRASE"] = m_pass
                # Reload config to pick up new env vars
                config = Config.from_env()
                print(f"{Colors.GREEN}✓ Credentials set. Gasless mode enabled.{Colors.RESET}\n")
            else:
                print(f"{Colors.RED}✗ Invalid credentials provided. Skipping.{Colors.RESET}\n")

    bot = TradingBot(config=config, private_key=private_key)

    if not bot.is_initialized():
        print(f"{Colors.RED}Failed to initialize bot. Check your private key.{Colors.RESET}")
        sys.exit(1)

    # Sanity check at startup
    if not asyncio.run(bot.verify_setup()):
        print(f"{Colors.RED}Startup checks failed. Please check your credentials and balance.{Colors.RESET}")
        # We don't necessarily want to exit if balance is low, 
        # but if we can't even get orders, we should exit.
        auth_working = False
        try:
            asyncio.run(bot._run_in_thread(bot.clob_client.get_open_orders))
            auth_working = True
        except:
             pass
        
        if not auth_working:
             print(f"{Colors.RED}Fatal: Could not authenticate with Polymarket. Exiting.{Colors.RESET}")
             sys.exit(1)
        
        print(f"{Colors.YELLOW}Proceeding anyway in 3 seconds...{Colors.RESET}")
        time.sleep(3)
    
    # Fetch the first market using the same logic as the main bot
    first_coin = coins[0] if coins else "BTC"
    print(f"{Colors.CYAN}Fetching {first_coin} market for validation...{Colors.RESET}")
    try:
        # Create a temporary strategy to fetch the market
        temp_cfg = FlashCrashConfig(
            coin=first_coin,
            size=0.01,
            drop_threshold=0.20,
            take_profit=0.05,
            stop_loss=0.10,
            render_enabled=False
        )
        temp_strategy = FlashCrashStrategy(bot, temp_cfg)
        
        # Wait for market to be fetched
        await_time = 0
        while not temp_strategy.market.current_market and await_time < 5:
            asyncio.run(asyncio.sleep(0.5))
            await_time += 0.5
        
        if temp_strategy.market.current_market and temp_strategy.market.token_ids:
            # Use the UP token for validation
            token_id = temp_strategy.market.token_ids.get('up')
            if token_id:
                bot._validation_token_id = token_id
                print(f"{Colors.GREEN}✓ Using {first_coin} market for validation{Colors.RESET}")
            else:
                print(f"{Colors.RED}✗ Market has no UP token, validation will fail{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ Could not fetch {first_coin} market, validation will fail{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Error fetching market: {e}{Colors.RESET}")
    
    # Wait for user confirmation before starting
    print(f"\n{Colors.CYAN}{'='*80}{Colors.RESET}")
    input(f"{Colors.BOLD}Validation complete. Press Enter to start trading (or Ctrl+C to cancel)...{Colors.RESET} ")
    print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")

    strategies = []
    for coin in coins:
        cfg = FlashCrashConfig(
            coin=coin,
            size=args.size,
            drop_threshold=args.drop,
            take_profit=args.take_profit,
            stop_loss=args.stop_loss,
            render_enabled=False 
        )
        strategies.append(FlashCrashStrategy(bot, cfg))

    try:
        asyncio.run(run_strategies(bot, strategies))
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
