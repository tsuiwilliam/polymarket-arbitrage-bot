# Polymarket Authentication Guide

Complete guide to troubleshooting authentication issues with Polymarket trading bot.

## Overview

Polymarket uses a **two-tier authentication system**:
- **L1 Authentication**: Uses your private key to sign EIP-712 messages
- **L2 Authentication**: Uses API credentials (apiKey, secret, passphrase) derived from L1

## Critical Concepts

### Proxy Wallet vs Signer Address

**IMPORTANT**: For Gnosis Safe wallets (most Polymarket users), there are TWO different addresses:

1. **Signer Address**: The address derived from your private key
2. **Proxy Wallet**: The Safe contract address shown on Polymarket.com

**You MUST use the Proxy Wallet address for authentication**, not the signer address!

### Finding Your Proxy Wallet Address

1. Go to [polymarket.com/settings](https://polymarket.com/settings)
2. Navigate to **General** tab
3. Find **Wallet Address** - this is your **PROXY WALLET**
4. Copy this address for `POLY_PROXY_WALLET` environment variable

## Environment Setup

### Required Environment Variables

```bash
# Your wallet's private key (with or without 0x prefix)
export POLY_PRIVATE_KEY="0x1234567890abcdef..."

# Your Polymarket PROXY wallet address (from polymarket.com/settings)
export POLY_PROXY_WALLET="0xYourProxyWalletAddress"
```

### Optional: Builder Program (for gasless trading)

```bash
export POLY_BUILDER_API_KEY="your_builder_key"
export POLY_BUILDER_API_SECRET="your_builder_secret"
export POLY_BUILDER_API_PASSPHRASE="your_builder_passphrase"
```

Apply for Builder Program at: [polymarket.com/settings?tab=builder](https://polymarket.com/settings?tab=builder)

## Wallet Types

### Signature Types

| Type | Value | Description | POLY_ADDRESS |
|------|-------|-------------|--------------|
| EOA | 0 | Standard Ethereum wallets (MetaMask, etc.) | Your wallet address |
| POLY_PROXY | 1 | Magic Link email/Google login | Exported proxy address |
| GNOSIS_SAFE | 2 | Multisig proxy wallets (MOST COMMON) | Proxy wallet address |

**Default**: The bot uses signature_type=2 (Gnosis Safe) which is correct for most users.

## Authentication Flow

### L1 Authentication (Private Key)

1. Generate current timestamp
2. Sign EIP-712 message with your private key
3. Send signature to Polymarket API with headers:
   - `POLY_ADDRESS`: Your **proxy wallet** address
   - `POLY_SIGNATURE`: EIP-712 signature
   - `POLY_TIMESTAMP`: Current timestamp
   - `POLY_NONCE`: Usually 0

### EIP-712 Message Structure

```javascript
{
  domain: {
    name: "ClobAuthDomain",
    version: "1",
    chainId: 137  // Polygon mainnet
  },
  types: {
    ClobAuth: [
      { name: "address", type: "address" },
      { name: "timestamp", type: "string" },
      { name: "nonce", type: "uint256" },
      { name: "message", type: "string" }
    ]
  },
  message: {
    address: "0xYourSignerAddress",
    timestamp: "1234567890",
    nonce: 0,
    message: "This message attests that I control the given wallet"
  }
}
```

### L2 Authentication (API Credentials)

After L1 authentication succeeds, you receive:
- `apiKey`: UUID identifier
- `secret`: Base64-encoded HMAC secret
- `passphrase`: Random string

These are used for subsequent API requests with HMAC-SHA256 signatures.

## Troubleshooting

### Common Issues

#### 1. "Authentication Failed" or "Invalid Signature"

**Likely Cause**: Using signer address instead of proxy wallet address

**Solution**:
```bash
# Make sure you're using the PROXY wallet, not your private key's address
export POLY_PROXY_WALLET="0xYourProxyFromPolymarket.com"
```

Run the debug script:
```bash
python debug_auth.py
```

This will show you both addresses and highlight if they differ.

#### 2. "Timestamp too old" or "Timestamp in the future"

**Likely Cause**: System clock out of sync

**Solution**:
```bash
# Check your system time
date

# Sync time (Linux/Mac)
sudo ntpdate -s time.nist.gov

# Or use timedatectl (systemd)
sudo timedatectl set-ntp true
```

#### 3. "Invalid nonce" or "Nonce already used"

**Likely Cause**: Trying to create credentials that already exist

**Solution**: Use `derive_api_key` instead of `create_api_key`:
```python
# In your code, the bot automatically tries create then derive
creds = clob.create_or_derive_api_key(signer, nonce=0)
```

#### 4. "Cannot derive - no credentials found"

**Likely Cause**: First time setup - credentials never created

**Solution**: Run the debug script which will create credentials:
```bash
python debug_auth.py
```

#### 5. Private key format errors

**Symptoms**: "Invalid private key" or "Key must be 64 hex characters"

**Solution**: Ensure your private key is properly formatted:
```bash
# Valid formats:
# With 0x prefix (recommended)
export POLY_PRIVATE_KEY="0x1234567890abcdef..."

# Without 0x prefix (also works)
export POLY_PRIVATE_KEY="1234567890abcdef..."

# Invalid (do not use)
export POLY_PRIVATE_KEY="0X..."  # Wrong - uppercase X
export POLY_PRIVATE_KEY="1234..."  # Too short
```

## Debug Script

Run the authentication debug script to identify issues:

```bash
python debug_auth.py
```

This script will:
1. Check environment variables
2. Validate addresses
3. Test EIP-712 signature generation
4. Attempt L1 authentication
5. Create or derive API credentials
6. Save credentials for future use

## Testing Authentication

### Quick Test

```python
from src import create_bot_from_env
import asyncio

async def test():
    bot = create_bot_from_env()

    if not bot.is_initialized():
        print("Bot not initialized!")
        return

    # Test getting open orders (requires authentication)
    orders = await bot.get_open_orders()
    print(f"Successfully authenticated! Found {len(orders)} open orders")

asyncio.run(test())
```

### Manual Test

```python
from src.config import Config
from src.signer import OrderSigner
from src.client import ClobClient
import os

# Load config
private_key = os.environ["POLY_PRIVATE_KEY"]
proxy_wallet = os.environ["POLY_PROXY_WALLET"]

# Initialize
signer = OrderSigner(private_key)
config = Config.from_env()

clob = ClobClient(
    host=config.clob.host,
    chain_id=config.clob.chain_id,
    signature_type=2,  # Gnosis Safe
    funder=proxy_wallet  # Use proxy wallet!
)

# Authenticate
creds = clob.create_or_derive_api_key(signer, nonce=0)
print(f"API Key: {creds.api_key}")
print(f"Authentication successful!")
```

## Security Best Practices

1. **Never commit** your `.env` file or private keys to git
2. **Use encrypted key storage** for production:
   ```python
   from src.crypto import KeyManager

   manager = KeyManager()
   manager.encrypt_and_save(private_key, password, "credentials/key.enc")
   ```
3. **Rotate credentials** periodically
4. **Use Builder Program** for gasless trading (reduces tx costs)
5. **Keep credentials secure** with file permissions:
   ```bash
   chmod 600 credentials/*.enc
   chmod 600 .env
   ```

## Additional Resources

- [Polymarket CLOB Authentication Docs](https://docs.polymarket.com/developers/CLOB/authentication)
- [EIP-712 Standard](https://eips.ethereum.org/EIPS/eip-712)
- [Builder Program Application](https://polymarket.com/settings?tab=builder)

## Support

If issues persist after following this guide:

1. Run `python debug_auth.py` and save the output
2. Check the Polymarket documentation
3. Verify your wallet on polymarket.com is properly set up
4. Contact via Telegram: [@Vladmeer](https://t.me/vladmeer67)
