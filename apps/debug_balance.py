
import os
import sys
import logging
import json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

from src.config import Config, get_env
from src.signer import OrderSigner
from src.client import ClobClient, ApiCredentials

def test_balance():
    print("--- Testing Balance Fetch ---")
    
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    # For EOA, we use EOA address as funder
    
    if not private_key:
        print("Missing POLY_PRIVATE_KEY")
        return

    private_key = private_key.strip().replace('"', '').replace("'", "")
    if private_key.startswith("0x"): private_key = private_key[2:]
    
    signer = OrderSigner(private_key)
    print(f"Address: {signer.address}")

    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        signature_type=0, # EOA
        funder=signer.address
    )

    try:
        # Auth
        client.set_api_creds(client.create_or_derive_api_key(signer))
        print("Authenticated.")
        
        # Test endpoints
        endpoints = [
            "/balance", 
            "/data/balance", 
            "/data/balances", 
            "/data/balance-allowance", 
            "/balance-allowance"
        ]
        
        for ep in endpoints:
            print(f"\nTesting GET {ep}...")
            try:
                headers = client._build_headers("GET", ep)
                res = client._request("GET", ep, headers=headers)
                print(f"SUCCESS: {json.dumps(res, indent=2)}")
            except Exception as e:
                print(f"FAILED: {e}")

    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    test_balance()
