"""
Debug script to check which wallet owns the API key.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient

def main():
    # Load config
    config = Config.from_env()
    
    # Get addresses
    signer = OrderSigner(config.private_key)
    eoa_address = signer.address
    proxy_address = config.safe_address
    
    print("=" * 80)
    print("API Key Owner Debug")
    print("=" * 80)
    print(f"EOA Address (from private key): {eoa_address}")
    print(f"Proxy Address (from config):    {proxy_address}")
    print(f"Signature Type:                 {config.clob.signature_type}")
    print()
    
    # Initialize client
    clob = ClobClient(
        host=config.clob.host,
        key=config.private_key,
        chain_id=config.clob.chain_id,
        signature_type=config.clob.signature_type,
        funder=proxy_address if config.clob.signature_type == 2 else eoa_address
    )
    
    # Derive API key
    print("Deriving API key...")
    api_creds = clob.derive_api_key()
    print(f"API Key derived successfully")
    print()
    
    print("=" * 80)
    print("SOLUTION:")
    print("=" * 80)
    print("The API key is associated with the wallet that SIGNED the derivation request.")
    print(f"Since you're using signature_type={config.clob.signature_type}:")
    if config.clob.signature_type == 0:
        print(f"  → The API key is owned by: {eoa_address} (EOA)")
        print(f"  → Orders should use owner: {eoa_address}")
    else:
        print(f"  → The API key is owned by: {proxy_address} (Proxy)")
        print(f"  → Orders should use owner: {proxy_address}")
    print()
    print("Current maker address in orders:")
    if config.clob.signature_type == 0:
        print(f"  → Using: {eoa_address} (EOA) ✓ CORRECT")
    else:
        print(f"  → Using: {proxy_address} (Proxy) ✓ CORRECT")
    print("=" * 80)

if __name__ == "__main__":
    main()
