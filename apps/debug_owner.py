"""
Diagnostic script to determine the correct owner field for orders.
This will help us understand what value Polymarket expects in the 'owner' field.
"""
import os
import sys
from pathlib import Path
import json
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()  # Load .env file

from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient

def main():
    print("=" * 80)
    print("POLYMARKET ORDER OWNER DIAGNOSTIC")
    print("=" * 80)
    
    # Load config
    config = Config.from_env()
    
    # Get private key from environment
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    if not private_key:
        print("ERROR: POLY_PRIVATE_KEY not set in environment")
        return
    
    # Clean private key
    private_key = private_key.strip().replace('"', '').replace("'", "")
    if private_key.startswith("0x"):
        private_key = private_key[2:]
    
    # Get addresses
    signer = OrderSigner(private_key)
    eoa_address = signer.address
    proxy_address = config.safe_address
    
    print(f"\n1. WALLET ADDRESSES:")
    print(f"   EOA Address:   {eoa_address}")
    print(f"   Proxy Address: {proxy_address}")
    print(f"   Signature Type: {config.clob.signature_type}")
    
    # Initialize client correctly
    clob = ClobClient(
        host=config.clob.host,
        chain_id=config.clob.chain_id,
        signature_type=config.clob.signature_type,
        funder=eoa_address if config.clob.signature_type == 0 else proxy_address,
        api_creds=ApiCredentials.load(creds_file) if creds_file.exists() else None
    )
    
    print(f"\n2. CLIENT CONFIGURATION:")
    print(f"   Funder Address: {clob.funder}")
    print(f"   Host: {config.clob.host}")
    
    # Check API credentials
    if creds_file.exists():
        print(f"\n3. API CREDENTIALS (from {creds_file}):")
        print(f"   API Key exists: Yes")
    else:
        print(f"\n3. API CREDENTIALS:")
        print(f"   No cached credentials found at {creds_file}")
        print(f"   Will derive new API key...")
        
    # Derive/get API key
    try:
        if not clob.api_creds:
            api_creds = clob.create_or_derive_api_key(signer)
            clob.set_api_creds(api_creds)
            print(f"   ✓ API key derived successfully")
        else:
            print(f"   ✓ Using existing API key")
    except Exception as e:
        print(f"   ✗ Failed to derive API key: {e}")
        return
    
    # Get balance to confirm auth works
    try:
        balance_data = clob.get_balance_allowance()
        balance = float(balance_data.get('balance', 0)) / 1_000_000
        print(f"\n4. BALANCE CHECK:")
        print(f"   ✓ Balance: ${balance:.2f}")
        print(f"   ✓ Authentication working for READ operations")
    except Exception as e:
        print(f"\n4. BALANCE CHECK:")
        print(f"   ✗ Failed: {e}")
        return
    
    print(f"\n5. ORDER OWNER FIELD ANALYSIS:")
    print(f"   When signature_type={config.clob.signature_type}:")
    
    if config.clob.signature_type == 0:
        print(f"   → Maker address should be: {eoa_address} (EOA)")
        print(f"   → Owner field should be: {eoa_address} (EOA)")
        print(f"   → Funder should be: {eoa_address} (EOA)")
    else:
        print(f"   → Maker address should be: {proxy_address} (Proxy)")
        print(f"   → Owner field should be: {proxy_address} (Proxy)")
        print(f"   → Funder should be: {proxy_address} (Proxy)")
    
    print(f"\n6. RECOMMENDATION:")
    print(f"   The 'owner' field in order payloads MUST match the wallet")
    print(f"   that was used to create the API key.")
    print(f"   ")
    print(f"   Current setup:")
    print(f"   - API key was created by: {clob.funder}")
    print(f"   - Orders should use owner: {clob.funder}")
    print(f"   ")
    print(f"   If orders still fail, the API key may have been created")
    print(f"   with a different wallet. Delete credentials/ and restart.")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
