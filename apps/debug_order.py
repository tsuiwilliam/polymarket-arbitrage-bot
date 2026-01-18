
import os
import sys
import logging
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from src.signer import OrderSigner, Order
from src.client import ClobClient
# from src.utils import Order, OrderSignature # Removed invalid import

async def test_order():
    print("--- Testing Order Placement ---")
    
    private_key = os.environ.get("POLY_PRIVATE_KEY")
    if not private_key:
        print("Missing POLY_PRIVATE_KEY")
        return

    private_key = private_key.strip().replace('"', '').replace("'", "")
    if private_key.startswith("0x"): private_key = private_key[2:]
    
    signer = OrderSigner(private_key)
    print(f"Signer Address: {signer.address}")

    # Initialize Client with EOA settings
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        signature_type=0, # EOA
        funder=signer.address # IMPORTANT: Funder must be EOA for Type 0
    )

    # Auth
    try:
        creds = client.create_or_derive_api_key(signer)
        client.set_api_creds(creds)
        print("Authenticated successfully.")
    except Exception as e:
        print(f"Auth failed: {e}")
        return

    # Create a dummy order (Buy NO at very low price to not fill)
    # Using a known active market would be best. 
    # Let's try to get a market first or hardcode one if we know it.
    # The user logs showed BTC/ETH/SOL markets.
    
    # We'll rely on the client to get a random market or just try to structure an order 
    # and fail on "Invalid Token" which is better than 401.
    # 401 means we didn't even get to validation.
    
    dummy_token_id = "000000000000000000000000000000000000000000000000000000000000000" # Invalid
    
    order = Order(
        token_id=dummy_token_id,
        price=0.01,
        size=1.0,
        side="BUY",
        maker=signer.address, # Must match signer
        fee_rate_bps=0,
        signature_type=0
    )
    
    print(f"Signing Order: {order}")
    try:
        signed_order = signer.sign_order(order)
        print(f"Signed: {json.dumps(signed_order, indent=2)}")
        
        print("Posting Order...")
        # We manually call post_order to catch the exact error response
        resp = client.post_order(signed_order)
        print(f"Response: {resp}")
        
    except Exception as e:
        print(f"Order Placement Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_order())
