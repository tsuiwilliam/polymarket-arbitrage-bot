"""
Complete Gasless Setup Automation.
Deploys Safe proxy and approves USDC via Builder Relayer.
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from src.bot import TradingBot
from lib.terminal_utils import Colors

async def main():
    print("=" * 80)
    print(f"{Colors.BOLD}POLYMARKET GASLESS SETUP{Colors.RESET}")
    print("=" * 80)

    private_key = os.environ.get("POLY_PRIVATE_KEY")
    if not private_key:
        print(f"{Colors.RED}ERROR: POLY_PRIVATE_KEY not set in .env{Colors.RESET}")
        return

    # Initialize bot
    bot = TradingBot(private_key=private_key)
    
    if not bot.config.use_gasless:
        print(f"{Colors.RED}ERROR: Gasless mode not configured.{Colors.RESET}")
        print("Please ensure POLY_BUILDER_API_KEY, SECRET, and PASSPHRASE are in .env")
        return

    print(f"\nTarget Safe Address: {Colors.CYAN}{bot.config.safe_address}{Colors.RESET}")
    print(f"Signature Type: {bot.config.clob.signature_type}")
    print("-" * 40)

    # 1. Deploy Safe
    print(f"\nStep 1: Deploying Safe Proxy (if needed)...")
    deployed = await bot.deploy_safe_if_needed()
    if deployed:
        print(f"   {Colors.GREEN}✓ Deployment transaction sent to Relayer.{Colors.RESET}")
        print("   (Wait 20-30 seconds for blockchain confirmation)")
        await asyncio.sleep(5) # Small buffer
    else:
        print(f"   {Colors.YELLOW}! Deployment skipped or already active.{Colors.RESET}")

    # 2. Approve USDC
    print(f"\nStep 2: Approving USDC for CTF Exchange...")
    approved = await bot.approve_usdc_gasless()
    if approved:
        print(f"   {Colors.GREEN}✓ USDC Approval transaction sent to Relayer.{Colors.RESET}")
    else:
        print(f"   {Colors.RED}! USDC Approval request FAILED.{Colors.RESET}")

    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}SETUP COMPLETE!{Colors.RESET}")
    print("1. Please check Polygonscan for your Safe address to confirm deployment.")
    print("2. Ensure you have transferred USDC to the Safe address.")
    print(f"3. Run the bot: {Colors.CYAN}python apps/run_multi.py --coins BTC,ETH,SOL,XRP --drop 0.20 --size 0.5{Colors.RESET}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
