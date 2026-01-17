
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.client import ClobClient
from src.bot import TradingBot
import src.client

print(f"src.client file: {src.client.__file__}")
print(f"ClobClient has get_collateral_balance: {hasattr(ClobClient, 'get_collateral_balance')}")
print(f"ClobClient dir: {dir(ClobClient)}")

try:
    bot = TradingBot()
    print(f"Bot ClobClient: {bot.clob_client}")
    print(f"Bot ClobClient has get_collateral_balance: {hasattr(bot.clob_client, 'get_collateral_balance')}")
except Exception as e:
    print(f"Error init bot: {e}")
