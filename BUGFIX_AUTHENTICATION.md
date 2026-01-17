# Authentication Bug Fix

## Problem

The bot was failing to authenticate with Polymarket's CLOB API due to using the wrong address in authentication headers.

## Root Cause

According to [Polymarket documentation](https://docs.polymarket.com/developers/CLOB/authentication):

> **Critical Detail:** The funder address should match the proxy wallet displayed on Polymarket.com, not necessarily the signer address.

For **Gnosis Safe wallets** (signature_type=2, which is the default and most common):
- **Signer address**: The address derived from your private key
- **Proxy wallet**: The Safe contract address shown on Polymarket.com

These are **two different addresses**.

### The Bug

In `src/client.py`, both `derive_api_key()` and `create_api_key()` methods were using:

```python
headers = {
    "POLY_ADDRESS": signer.address,  # ❌ WRONG - signer's address
    "POLY_SIGNATURE": auth_signature,
    "POLY_TIMESTAMP": timestamp,
    "POLY_NONCE": str(nonce),
}
```

This caused authentication to fail because Polymarket expected the proxy wallet address, not the signer's address.

## The Fix

Changed both methods to use the proxy wallet address (`self.funder`):

```python
headers = {
    "POLY_ADDRESS": self.funder,  # ✓ CORRECT - proxy wallet address
    "POLY_SIGNATURE": auth_signature,
    "POLY_TIMESTAMP": timestamp,
    "POLY_NONCE": str(nonce),
}
```

## Files Changed

### `src/client.py`

**Line 315** (in `derive_api_key` method):
```diff
- "POLY_ADDRESS": signer.address,
+ "POLY_ADDRESS": self.funder,
```

**Line 349** (in `create_api_key` method):
```diff
- "POLY_ADDRESS": signer.address,
+ "POLY_ADDRESS": self.funder,
```

## How Authentication Works

### EIP-712 Signature Flow

1. **Signer signs** the message with their private key
   - This proves ownership of the private key
   - Signature contains `signer.address` in the message data

2. **Headers sent to API** include:
   - `POLY_ADDRESS`: **Proxy wallet address** (not signer address!)
   - `POLY_SIGNATURE`: EIP-712 signature from step 1
   - `POLY_TIMESTAMP`: Current timestamp
   - `POLY_NONCE`: Usually 0

3. **Polymarket verifies**:
   - Signature is valid for the signer
   - Signer has authorization for the proxy wallet
   - Timestamp is recent

### Why This Works

The EIP-712 message includes the signer's address in the message data:

```javascript
{
  address: signer.address,  // Signer proves they control this
  timestamp: "...",
  nonce: 0,
  message: "This message attests that I control the given wallet"
}
```

But the `POLY_ADDRESS` header tells Polymarket **which proxy wallet** this authentication is for.

## Wallet Types

| Type | Signature Type | POLY_ADDRESS | Notes |
|------|----------------|--------------|-------|
| EOA (MetaMask) | 0 | Same as signer address | Address from private key |
| POLY_PROXY (Magic Link) | 1 | Proxy wallet address | Different from signer |
| **GNOSIS_SAFE** | **2** | **Proxy wallet address** | **Most common - DIFFERENT** |

## Verification

Run the test scripts to verify the fix:

```bash
# Quick verification
python test_auth_fix.py

# Full authentication test
python debug_auth.py
```

## Impact

This fix enables:
- L1 authentication to succeed
- API credentials to be created/derived
- Orders to be placed successfully
- Full bot functionality to work

## Additional Resources

- [AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md) - Complete authentication guide
- [Polymarket CLOB Authentication Docs](https://docs.polymarket.com/developers/CLOB/authentication)
- [EIP-712 Standard](https://eips.ethereum.org/EIPS/eip-712)
