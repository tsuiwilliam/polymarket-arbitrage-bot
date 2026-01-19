"""
Debug script to test API key binding for Proxy vs EOA mode.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient

def main():
    config = Config.from_env()
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    
    if not private_key:
        print("ERROR: POLY_PRIVATE_KEY not set")
        return
    
    signer = OrderSigner(private_key)
    
    print("=" * 80)
    print("API Key Binding Test")
    print("=" * 80)
    print(f"EOA Address: {signer.address}")
    print(f"Proxy Address: {config.safe_address}")
    print(f"Signature Type: {config.clob.signature_type}")
    print()
    
    # Test 1: Derive key with EOA (current behavior)
    print("Test 1: Deriving API key (EOA binding)...")
    clob_eoa = ClobClient(
        host=config.clob.host,
        chain_id=config.clob.chain_id,
        signature_type=0,  # Force EOA mode for derivation
        funder=signer.address
    )
    
    try:
        creds_eoa = clob_eoa.create_or_derive_api_key(signer)
        print(f"✓ API Key: {creds_eoa.api_key[:20]}...")
        
        # Now test using it with Proxy address
        print("\nTest 2: Using EOA-bound key with Proxy address...")
        clob_proxy = ClobClient(
            host=config.clob.host,
            chain_id=config.clob.chain_id,
            signature_type=2,
            funder=config.safe_address,
            api_creds=creds_eoa
        )
        
        try:
            orders = clob_proxy.get_open_orders()
            print(f"✓ SUCCESS: Key works with Proxy! Orders: {len(orders)}")
        except Exception as e:
            print(f"✗ FAILED: {e}")
            print("\nThis confirms the key is bound to EOA, not Proxy.")
            
    except Exception as e:
        print(f"✗ Failed to derive key: {e}")
    
    print("\n" + "=" * 80)
    print("CONCLUSION:")
    print("If Test 2 failed, the API key system binds keys to the address used")
    print("in authenticated requests (POLY_ADDRESS header), not the signer.")
    print("=" * 80)

if __name__ == "__main__":
    main()
