#!/usr/bin/env python3
"""Debug script to check which address balance is being queried."""

import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def main():
    from src.bot import TradingBot
    from src.config import BotConfig, ClobConfig
    
    # Initialize bot
    config = BotConfig(
        private_key=os.getenv("POLY_PRIVATE_KEY"),
        clob=ClobConfig(signature_type=2),
        use_gasless=True
    )
    
    bot = TradingBot(config)
    
    print("=" * 60)
    print("BALANCE DEBUG")
    print("=" * 60)
    print(f"Config Safe Address: {bot.config.safe_address}")
    print(f"Signer EOA Address: {bot.signer.address if bot.signer else 'N/A'}")
    print(f"ClobClient Funder: {bot.clob_client.funder}")
    print(f"Signature Type: {bot.config.clob.signature_type}")
    print("=" * 60)
    
    # Query balance
    balance = await bot.get_collateral_balance()
    print(f"Balance: ${balance:.2f}")
    print("=" * 60)
    
    if balance == 1.00:
        print("⚠️  Balance is $1.00 - this is the EOA balance!")
        print(f"   EOA: {bot.signer.address}")
    elif abs(balance - 39.95) < 0.10:
        print("✓  Balance is ~$39.95 - this is the Proxy wallet balance!")
        print(f"   Proxy: {bot.config.safe_address}")
    else:
        print(f"?  Unexpected balance: ${balance:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
