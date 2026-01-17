#!/usr/bin/env python3
"""
Authentication Debug Script for Polymarket

This script helps diagnose authentication issues by:
1. Checking environment variables
2. Validating addresses
3. Testing L1 authentication with detailed logging
4. Attempting API key derivation/creation
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load .env
from dotenv import load_dotenv
load_dotenv()

from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient

print("="*80)
print("POLYMARKET AUTHENTICATION DEBUG")
print("="*80)

# Step 1: Check environment variables
print("\n1. Checking Environment Variables...")
private_key = os.environ.get("POLY_PRIVATE_KEY")
proxy_wallet = os.environ.get("POLY_PROXY_WALLET")

if not private_key:
    print("❌ POLY_PRIVATE_KEY not set")
    sys.exit(1)
else:
    print(f"✓ POLY_PRIVATE_KEY: {private_key[:6]}...{private_key[-4:]}")

if not proxy_wallet:
    print("❌ POLY_PROXY_WALLET not set")
    sys.exit(1)
else:
    print(f"✓ POLY_PROXY_WALLET: {proxy_wallet}")

# Step 2: Initialize signer and check addresses
print("\n2. Initializing Signer...")
try:
    signer = OrderSigner(private_key)
    print(f"✓ Signer initialized")
    print(f"  Signer Address (from private key): {signer.address}")
    print(f"  Proxy Wallet (from env):           {proxy_wallet}")

    if signer.address.lower() != proxy_wallet.lower():
        print("\n⚠️  WARNING: Signer address differs from proxy wallet!")
        print("   This is normal for Gnosis Safe wallets.")
        print(f"   Private key controls: {signer.address}")
        print(f"   Proxy wallet is:      {proxy_wallet}")
    else:
        print("✓ Signer address matches proxy wallet (EOA wallet)")

except Exception as e:
    print(f"❌ Failed to initialize signer: {e}")
    sys.exit(1)

# Step 3: Test EIP-712 signature generation
print("\n3. Testing EIP-712 Signature Generation...")
try:
    import time
    timestamp = str(int(time.time()))
    signature = signer.sign_auth_message(timestamp=timestamp, nonce=0)
    print(f"✓ EIP-712 signature generated successfully")
    print(f"  Timestamp: {timestamp}")
    print(f"  Signature: {signature[:20]}...{signature[-10:]}")
except Exception as e:
    print(f"❌ Failed to generate signature: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Initialize CLOB client
print("\n4. Initializing CLOB Client...")
try:
    config = Config.from_env()
    clob = ClobClient(
        host=config.clob.host,
        chain_id=config.clob.chain_id,
        signature_type=config.clob.signature_type,
        funder=proxy_wallet,  # Use proxy wallet!
    )
    print(f"✓ CLOB client initialized")
    print(f"  Host: {config.clob.host}")
    print(f"  Chain ID: {config.clob.chain_id}")
    print(f"  Signature Type: {config.clob.signature_type}")
    print(f"  Funder: {proxy_wallet}")
except Exception as e:
    print(f"❌ Failed to initialize CLOB client: {e}")
    sys.exit(1)

# Step 5: Test L1 authentication - Create API Key
print("\n5. Testing L1 Authentication (Create API Key)...")
try:
    creds = clob.create_api_key(signer, nonce=0)
    if creds.api_key:
        print(f"✓ API credentials created successfully!")
        print(f"  API Key: {creds.api_key}")
        print(f"  Secret: {creds.secret[:20]}...")
        print(f"  Passphrase: {creds.passphrase}")

        # Save credentials
        creds_path = Path("credentials/api_creds.json")
        creds_path.parent.mkdir(exist_ok=True)
        import json
        with open(creds_path, 'w') as f:
            json.dump({
                "apiKey": creds.api_key,
                "secret": creds.secret,
                "passphrase": creds.passphrase
            }, f, indent=2)
        print(f"\n  Credentials saved to: {creds_path}")
    else:
        print("❌ API key creation returned empty credentials")

except Exception as e:
    print(f"⚠️  Create failed (may already exist): {e}")

    # Try deriving instead
    print("\n6. Trying to Derive Existing API Key...")
    try:
        creds = clob.derive_api_key(signer, nonce=0)
        if creds.api_key:
            print(f"✓ API credentials derived successfully!")
            print(f"  API Key: {creds.api_key}")
            print(f"  Secret: {creds.secret[:20]}...")
            print(f"  Passphrase: {creds.passphrase}")
        else:
            print("❌ Derive returned empty credentials")
    except Exception as e2:
        print(f"❌ Derive also failed: {e2}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

print("\n" + "="*80)
print("AUTHENTICATION DEBUG COMPLETE")
print("="*80)
