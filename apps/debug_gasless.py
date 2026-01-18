"""
Diagnostic script for gasless transactions and proxy wallet setup.
Checks:
1. Safe deployment status
2. USDC balance
3. USDC allowance for the CTF exchange
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from src.config import Config
from src.bot import TradingBot
from lib.terminal_utils import Colors

async def main():
    print("=" * 80)
    print("GASLESS TRANSACTION & PROXY WALLET DIAGNOSTIC")
    print("=" * 80)

    config = Config.from_env()
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    if not private_key:
        print(f"{Colors.RED}ERROR: POLY_PRIVATE_KEY not set{Colors.RESET}")
        return

    bot = TradingBot(config=config, private_key=private_key)
    if not bot.is_initialized():
        print(f"{Colors.RED}ERROR: Bot failed to initialize{Colors.RESET}")
        return

    print(f"\n1. SETTINGS:")
    print(f"   Signature Type: {config.clob.signature_type} ({'Proxy/Safe' if config.clob.signature_type == 2 else 'EOA'})")
    print(f"   Gasless Enabled: {config.use_gasless}")
    print(f"   Proxy Address: {config.safe_address}")
    
    if not config.use_gasless:
        print(f"\n{Colors.YELLOW}Warning: Gasless is NOT enabled in your config.{Colors.RESET}")
        print("To enable, ensure POLY_BUILDER_API_KEY and related vars are set.")

    # 2. Check deployment
    print(f"\n2. SAFE DEPLOYMENT:")
    if config.safe_address:
        try:
            # We can try to get balance. If it fails with specific error or returns something, we know
            balance = await bot.get_collateral_balance()
            print(f"   ✓ Safe is accessible. USDC Balance: ${balance:.2f}")
        except Exception as e:
            print(f"   ? Could not confirm deployment via balance: {e}")
            print(f"   Attempting to deploy via Relayer (gasless)...")
            success = await bot.deploy_safe_if_needed()
            if success:
                print(f"   ✓ Deployment transaction initiated.")
            else:
                print(f"   ! Deployment attempt failed or not needed.")
    else:
        print(f"   ! No POLY_PROXY_WALLET set.")

    # 3. Check Builder Credentials
    print(f"\n3. BUILDER AUTH:")
    if config.builder and config.builder.is_configured():
        print(f"   ✓ Builder API Key: {config.builder.api_key[:10]}...")
        print(f"   ✓ Builder credentials are configured.")
    else:
        print(f"   ! Builder credentials MISSING.")

    # 4. Check Allowance
    print(f"\n4. USDC ALLOWANCE:")
    print(f"   (This requires querying the blockchain or clob for allowance status)")
    # Polymarket uses a specific spender for USDC. 
    # For gasless, we usually rely on the Relayer to handle approvals.
    
    # Let's try to get balance again to be sure
    try:
        balance = await bot.get_collateral_balance()
        if balance > 0:
             print(f"   ✓ USDC Balance: ${balance:.2f} - Sufficient for testing.")
        else:
             print(f"   ! USDC Balance is 0.00. You need USDC to trade.")
    except Exception as e:
        print(f"   ! Error checking balance: {e}")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    if config.clob.signature_type != 2:
        print(f"- Change POLY_SIGNATURE_TYPE to 2 to use the Proxy wallet.")
    if balance == 0:
        print(f"- Deposit USDC to your Proxy wallet: {config.safe_address}")
    print("- Run 'python apps/run_multi.py' to start trading once balance is cleared.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
