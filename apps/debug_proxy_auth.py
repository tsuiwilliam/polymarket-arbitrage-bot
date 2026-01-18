
import os
import sys
import logging
import time
import hmac
import hashlib
import base64
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from src.bot import TradingBot
from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient, ApiCredentials

def test_proxy_auth():
    print("--- Testing Proxy Authentication ---")
    
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    proxy_address = os.environ.get("POLY_PROXY_WALLET")
    
    if not private_key or not proxy_address:
        print("Missing credentials.")
        return

    # Sanitize
    private_key = private_key.strip().replace('"', '').replace("'", "")
    if private_key.startswith("0x"): private_key = private_key[2:]
    
    signer = OrderSigner(private_key)
    print(f"EOA Address: {signer.address}")
    print(f"Proxy Address: {proxy_address}")

    # Try Signature Type 1 and 2
    for sig_type in [1, 2]:
        print(f"\n[Testing Signature Type {sig_type}]")
        
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            signature_type=sig_type,
            funder=proxy_address # Identifying as Proxy
        )

        # 1. Try to Derive API Key for Proxy
        print("Attempting to derive/create API key for Proxy...")
        
        # When creating API key for Proxy, do we sign with EOA? 
        # Usually yes, the EOA is the owner.
        
        # We need to hack the headers generation locally to see what happens, 
        # or just use the client method which uses the signer (EOA).
        
        try:
            # We pass the EOA signer. The client uses signer.address in headers for L1 auth? 
            # Wait, verify ClobClient.derive_api_key implementation.
            # It uses signer.address as POLY_ADDRESS for L1 headers!
            # If we want to derive key FOR PROXY, maybe we need to specify it?
            
            # Actually, standard flow:
            # 1. EOA signs message.
            # 2. Server sees EOA is owner of Proxy.
            # 3. Server issues API Creds valid for Proxy?
            
            # Let's just try the default method
            creds = client.create_or_derive_api_key(signer)
            print("Credentials obtained!")
            client.set_api_creds(creds)
            
            # Now try to check balance acting as Proxy
            print("Fetching balance...")
            bals = client.get_balance()
            print(f"Balances: {bals}")
            
            obs = client.get_open_orders()
            print(f"Open Orders: {len(obs)}")
            
            print(f"SUCCESS with Type {sig_type}")
            return # Stop if success
            
        except Exception as e:
            print(f"FAILED with Type {sig_type}: {e}")

if __name__ == "__main__":
    test_proxy_auth()
