"""
Debug script to test order placement and inspect headers.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient
from src.order import Order
import time
import random

def main():
    config = Config.from_env()
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    
    if not private_key:
        print("ERROR: POLY_PRIVATE_KEY not set")
        return
    
    signer = OrderSigner(private_key)
    
    print("=" * 80)
    print("Order Headers Debug")
    print("=" * 80)
    print(f"Signature Type: {config.clob.signature_type}")
    print(f"Proxy Address: {config.safe_address}")
    print(f"EOA Address: {signer.address}")
    print(f"Builder Configured: {config.builder.is_configured()}")
    print()
    
    # Create CLOB client
    clob = ClobClient(
        host=config.clob.host,
        chain_id=config.clob.chain_id,
        signature_type=config.clob.signature_type,
        funder=config.safe_address,
        builder_creds=config.builder
    )
    
    # Create a test order
    maker_address = config.safe_address if config.clob.signature_type == 2 else signer.address
    
    order = Order(
        token_id="99914208981568816645551301561974062576963636618104166856807686031985202521238",  # BTC UP
        price=0.50,
        size=1.0,
        side="BUY",
        maker=maker_address,
        expiration=0,
        salt=random.randint(1, 10**12),
        nonce=None,
        fee_rate_bps=0,
        signature_type=config.clob.signature_type,
    )
    
    # Sign with appropriate owner
    if config.clob.signature_type == 2:
        api_key = config.safe_address
    else:
        api_key = None
    
    signed = signer.sign_order(order, api_key=api_key)
    
    print("Signed Order Payload:")
    print(f"  owner: {signed.get('owner')}")
    print(f"  maker: {signed['order'].get('maker')}")
    print()
    
    # Build headers manually to inspect
    import json
    body_json = json.dumps(signed, separators=(',', ':'))
    headers = clob._build_headers("POST", "/order", body_json)
    
    print("Request Headers:")
    for key, value in headers.items():
        if "SIGNATURE" in key:
            print(f"  {key}: {value[:20]}...")
        else:
            print(f"  {key}: {value}")
    print()
    
    print("=" * 80)
    print("Analysis:")
    if "POLY_BUILDER_API_KEY" in headers:
        print("✓ Builder credentials are included")
    else:
        print("✗ Builder credentials are MISSING")
    
    if "POLY_API_KEY" in headers:
        print("✗ L2 API credentials are included (should NOT be for Proxy mode)")
    else:
        print("✓ L2 API credentials are NOT included")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
