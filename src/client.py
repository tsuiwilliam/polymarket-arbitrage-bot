"""
Client Module - API Clients for Polymarket

Provides clients for interacting with:
- CLOB (Central Limit Order Book) API
- Builder Relayer API

Features:
- Gasless transactions via Builder Program
- HMAC authentication for Builder APIs
- Automatic retry and error handling

Example:
    from src.client import ClobClient, RelayerClient

    clob = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        signature_type=2,
        funder="0x..."
    )

    relayer = RelayerClient(
        host="https://relayer-v2.polymarket.com",
        chain_id=137,
        builder_creds=builder_creds
    )
"""

import time
import hmac
import hashlib
import base64
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.websocket_client import MarketWebSocket

import requests

from .config import BuilderConfig
from .http import ThreadLocalSessionMixin


class ApiError(Exception):
    """Base exception for API errors."""
    pass


class AuthenticationError(ApiError):
    """Raised when authentication fails."""
    pass


class OrderError(ApiError):
    """Raised when order operations fail."""
    pass


@dataclass
class ApiCredentials:
    """User-level API credentials for CLOB."""
    api_key: str
    secret: str
    passphrase: str

    @classmethod
    def load(cls, filepath: str) -> "ApiCredentials":
        """Load credentials from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(
            api_key=data.get("apiKey", ""),
            secret=data.get("secret", ""),
            passphrase=data.get("passphrase", ""),
        )

    def is_valid(self) -> bool:
        """Check if credentials are valid."""
        return bool(self.api_key and self.secret and self.passphrase)


class ApiClient(ThreadLocalSessionMixin):
    """
    Base HTTP client with common functionality.

    Provides:
    - Automatic JSON handling
    - Request/response logging
    - Error handling
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        retry_count: int = 3
    ):
        """
        Initialize API client.

        Args:
            base_url: Base URL for all requests
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
        """
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.retry_count = retry_count

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Any] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            headers: Additional headers
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            ApiError: On request failure
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = {"Content-Type": "application/json"}

        if headers:
            request_headers.update(headers)

        last_error = None
        for attempt in range(self.retry_count):
            try:
                session = self.session
                if method.upper() == "GET":
                    response = session.get(
                        url, headers=request_headers,
                        params=params, timeout=self.timeout
                    )
                elif method.upper() in ("POST", "DELETE"):
                    # If data is a string, assume it's already serialized JSON
                    if isinstance(data, str):
                        response = session.request(
                            method.upper(),
                            url, headers=request_headers,
                            data=data, params=params, timeout=self.timeout
                        )
                    else:
                        response = session.request(
                            method.upper(),
                            url, headers=request_headers,
                            json=data, params=params, timeout=self.timeout
                        )
                else:
                    raise ApiError(f"Unsupported method: {method}")

                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as he:
                    error_msg = f"HTTP Error {response.status_code}: {response.text}"
                    raise ApiError(error_msg)
                
                return response.json() if response.text else {}

            except requests.exceptions.RequestException as e:
                # If we already raised an ApiError (e.g. from HTTPError), re-raise it
                if isinstance(e, ApiError):
                    raise e
                last_error = e
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        raise ApiError(f"Request failed after {self.retry_count} attempts: {last_error}")


class ClobClient(ApiClient):
    """
    Client for Polymarket CLOB (Central Limit Order Book) API.

    Features:
    - Order placement and cancellation
    - Order book queries
    - Trade history
    - Builder attribution support

    Example:
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            signature_type=2,
            funder="0x..."
        )
    """

    def __init__(
        self,
        host: str = "https://clob.polymarket.com",
        chain_id: int = 137,
        signature_type: int = 2,
        funder: str = "",
        api_creds: Optional[ApiCredentials] = None,
        builder_creds: Optional[BuilderConfig] = None,
        timeout: int = 30
    ):
        """
        Initialize CLOB client.

        Args:
            host: CLOB API host
            chain_id: Chain ID (137 for Polygon mainnet)
            signature_type: Signature type (2 = Gnosis Safe)
            funder: Funder/Safe address
            api_creds: User API credentials (optional)
            builder_creds: Builder credentials for attribution (optional)
            timeout: Request timeout
        """
        super().__init__(base_url=host, timeout=timeout)
        self.host = host
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.funder = funder
        self.api_creds = api_creds
        self.builder_creds = builder_creds
        self.ws = MarketWebSocket()  # Initialize shared WebSocket
        
        # Balance cache to avoid rate limiting on RPC calls
        self._balance_cache = 0.0
        self._balance_cache_time = 0.0
        self._balance_cache_ttl = 30.0  # Cache for 30 seconds

    def _build_headers(
        self,
        method: str,
        path: str,
        body: str = ""
    ) -> Dict[str, str]:
        """
        Build authentication headers.

        Supports both user API credentials and Builder credentials.

        Args:
            method: HTTP method
            path: Request path
            body: Request body

        Returns:
            Dictionary of headers
        """
        headers = {}

        # Builder HMAC authentication
        if self.builder_creds and self.builder_creds.is_configured():
            timestamp = str(int(time.time()))

            message = f"{timestamp}{method}{path}{body}"
            signature = hmac.new(
                self.builder_creds.api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            headers.update({
                "POLY_BUILDER_API_KEY": self.builder_creds.api_key,
                "POLY_BUILDER_TIMESTAMP": timestamp,
                "POLY_BUILDER_PASSPHRASE": self.builder_creds.api_passphrase,
                "POLY_BUILDER_SIGNATURE": signature,
            })

        # User API credentials (L2 authentication)
        # Only use L2 API credentials in EOA mode (signature_type=0)
        # Proxy mode (signature_type=2) uses Builder credentials exclusively
        if self.api_creds and self.api_creds.is_valid() and self.signature_type == 0:
            timestamp = str(int(time.time()))

            # Build message: timestamp + method + path + body
            message = f"{timestamp}{method}{path}"
            if body:
                message += body

            # Decode base64 secret and create HMAC signature
            try:
                base64_secret = base64.urlsafe_b64decode(self.api_creds.secret)
                h = hmac.new(base64_secret, message.encode("utf-8"), hashlib.sha256)
                signature = base64.urlsafe_b64encode(h.digest()).decode("utf-8")
            except Exception:
                # Fallback: use secret directly if not base64 encoded
                signature = hmac.new(
                    self.api_creds.secret.encode(),
                    message.encode(),
                    hashlib.sha256
                ).hexdigest()

            headers.update({
                "POLY_ADDRESS": self.funder,
                "POLY_API_KEY": self.api_creds.api_key,
                "POLY_TIMESTAMP": timestamp,
                "POLY_PASSPHRASE": self.api_creds.passphrase,
                "POLY_SIGNATURE": signature,
            })

        return headers

    def derive_api_key(self, signer: "OrderSigner", nonce: int = 0) -> ApiCredentials:
        """
        Derive L2 API credentials using L1 EIP-712 authentication.

        This is required to access authenticated endpoints like
        /orders and /trades.

        Args:
            signer: OrderSigner instance with private key
            nonce: Nonce for the auth message (default 0)

        Returns:
            ApiCredentials with api_key, secret, and passphrase
        """
        timestamp = str(int(time.time()))

        # Sign the auth message using EIP-712
        auth_signature = signer.sign_auth_message(timestamp=timestamp, nonce=nonce)

        # L1 headers
        headers = {
            "POLY_ADDRESS": signer.address,
            "POLY_SIGNATURE": auth_signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_NONCE": str(nonce),
        }

        response = self._request("GET", "/auth/derive-api-key", headers=headers)

        return ApiCredentials(
            api_key=response.get("apiKey", ""),
            secret=response.get("secret", ""),
            passphrase=response.get("passphrase", ""),
        )

    def create_api_key(self, signer: "OrderSigner", nonce: int = 0) -> ApiCredentials:
        """
        Create new L2 API credentials using L1 EIP-712 authentication.

        Use this if derive_api_key fails (first time setup).

        Args:
            signer: OrderSigner instance with private key
            nonce: Nonce for the auth message (default 0)

        Returns:
            ApiCredentials with api_key, secret, and passphrase
        """
        timestamp = str(int(time.time()))

        # Sign the auth message using EIP-712
        auth_signature = signer.sign_auth_message(timestamp=timestamp, nonce=nonce)

        # L1 headers
        headers = {
            "POLY_ADDRESS": signer.address,
            "POLY_SIGNATURE": auth_signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_NONCE": str(nonce),
        }

        response = self._request("POST", "/auth/api-key", headers=headers)

        return ApiCredentials(
            api_key=response.get("apiKey", ""),
            secret=response.get("secret", ""),
            passphrase=response.get("passphrase", ""),
        )

    def create_or_derive_api_key(self, signer: "OrderSigner", nonce: int = 0) -> ApiCredentials:
        """
        Create API credentials if not exists, otherwise derive them.

        Args:
            signer: OrderSigner instance with private key
            nonce: Nonce for the auth message (default 0)

        Returns:
            ApiCredentials with api_key, secret, and passphrase
        """
        try:
            return self.create_api_key(signer, nonce)
        except Exception:
            return self.derive_api_key(signer, nonce)

    def set_api_creds(self, creds: ApiCredentials) -> None:
        """Set API credentials for authenticated requests."""
        self.api_creds = creds

    def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book for a token.

        Args:
            token_id: Market token ID

        Returns:
            Order book data
        """
        return self._request(
            "GET",
            "/book",
            params={"token_id": token_id}
        )

    def get_market_price(self, token_id: str) -> Dict[str, Any]:
        """
        Get current market price for a token.

        Args:
            token_id: Market token ID

        Returns:
            Price data
        """
        return self._request(
            "GET",
            "/price",
            params={"token_id": token_id}
        )

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders for the funder.

        Returns:
            List of open orders
        """
        endpoint = "/data/orders"

        headers = self._build_headers("GET", endpoint)

        result = self._request(
            "GET",
            endpoint,
            headers=headers
        )

        # Handle paginated response
        if isinstance(result, dict) and "data" in result:
            return result.get("data", [])
        return result if isinstance(result, list) else []

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order details
        """
        endpoint = f"/data/order/{order_id}"
        headers = self._build_headers("GET", endpoint)
        return self._request("GET", endpoint, headers=headers)

    def get_trades(
        self,
        token_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get trade history.

        Args:
            token_id: Filter by token (optional)
            limit: Maximum number of trades

        Returns:
            List of trades
        """
        endpoint = "/data/trades"
        headers = self._build_headers("GET", endpoint)
        params: Dict[str, Any] = {"limit": limit}
        if token_id:
            params["token_id"] = token_id

        result = self._request(
            "GET",
            endpoint,
            headers=headers,
            params=params
        )

        # Handle paginated response
        if isinstance(result, dict) and "data" in result:
            return result.get("data", [])
        return result if isinstance(result, list) else []

    def post_order(
        self,
        signed_order: Dict[str, Any],
        order_type: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Submit a signed order.

        Args:
            signed_order: Order with signature
            order_type: Order type (GTC, GTD, FOK)

        Returns:
            Response with order ID and status
        """
        endpoint = "/order"

        # Use the signed order as the base body if it has the required structure
        if isinstance(signed_order, dict) and "order" in signed_order:
            body = signed_order.copy()
            # Ensure orderType is set correctly
            if order_type:
                body["orderType"] = order_type
        else:
            # Fallback for legacy format
            body = {
                "order": signed_order,
                "owner": self.funder,
                "orderType": order_type,
            }

        body_json = json.dumps(body, separators=(',', ':'))
        headers = self._build_headers("POST", endpoint, body_json)
        
        # Debug: Log headers to diagnose 401 errors
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"POST /order headers: {list(headers.keys())}")
        if "POLY_BUILDER_API_KEY" in headers:
            logger.debug("  ✓ Builder credentials included")
        else:
            logger.warning("  ✗ Builder credentials MISSING from order request!")

        return self._request(
            "POST",
            endpoint,
            data=body_json, # Send the EXACT same JSON string used for signature
            headers=headers
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        endpoint = "/order"
        body = {"orderID": order_id}
        body_json = json.dumps(body, separators=(',', ':'))
        headers = self._build_headers("DELETE", endpoint, body_json)

        return self._request(
            "DELETE",
            endpoint,
            data=body_json, # Send the EXACT same JSON string used for signature
            headers=headers
        )

    def cancel_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple orders by their IDs.

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Cancellation response with canceled and not_canceled lists
        """
        endpoint = "/orders"
        body_json = json.dumps(order_ids, separators=(',', ':'))
        headers = self._build_headers("DELETE", endpoint, body_json)

        return self._request(
            "DELETE",
            endpoint,
            data=order_ids,
            headers=headers
        )

    def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all open orders.

        Returns:
            Cancellation response with canceled and not_canceled lists
        """
        endpoint = "/cancel-all"
        headers = self._build_headers("DELETE", endpoint)

        return self._request(
            "DELETE",
            endpoint,
            headers=headers
        )

    def cancel_market_orders(
        self,
        market: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel orders for a specific market.

        Args:
            market: Condition ID of the market (optional)
            asset_id: Token/asset ID (optional)

        Returns:
            Cancellation response with canceled and not_canceled lists
        """
        endpoint = "/cancel-market-orders"
        body = {}

        if market:
            body["market"] = market
        if asset_id:
            body["asset_id"] = asset_id

        body_json = json.dumps(body, separators=(',', ':')) if body else ""
        headers = self._build_headers("DELETE", endpoint, body_json)

        return self._request(
            "DELETE",
            endpoint,
            data=body if body else None,
            headers=headers
        )

    def get_balance(self) -> List[Dict[str, Any]]:
        """
        Get user balances.

        Returns:
            List of balance objects
        """
        endpoint = "/balance"
        headers = self._build_headers("GET", endpoint)
        
        return self._request(
            "GET",
            endpoint,
            headers=headers
        )

    def get_collateral_balance(self) -> float:
        """
        Get USDC/Collateral balance.
        Uses 30-second cache to avoid rate limiting on RPC calls.
        
        Returns:
            Balance as float (USDC)
        """
        import time
        
        # Check cache first
        if time.time() - self._balance_cache_time < self._balance_cache_ttl:
            return self._balance_cache
        
        try:
            endpoint = "/balance-allowance"
            params = {"asset_type": "COLLATERAL"}
            headers = self._build_headers("GET", endpoint)
            
            res = self._request("GET", endpoint, headers=headers, params=params)
            
            # Response format: {"balance": "1000000", "allowances": ...}
            raw_balance = res.get("balance", "0")
            balance = float(raw_balance) / 1_000_000 # USDC has 6 decimals
            
            # Update cache
            self._balance_cache = balance
            self._balance_cache_time = time.time()
            return balance
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            
            # If API fails (common in Proxy mode without L2 API keys),
            # fall back to on-chain balance query
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.info("API balance check failed (no L2 API key), querying blockchain directly...")
                try:
                    balance = self._get_onchain_usdc_balance()
                    # Update cache
                    self._balance_cache = balance
                    self._balance_cache_time = time.time()
                    return balance
                except Exception as e2:
                    logger.warning(f"On-chain balance query also failed: {e2}")
            else:
                logger.warning(f"Failed to get collateral balance: {e}")
        
        # Return cached value if available, otherwise 0
        return self._balance_cache if self._balance_cache > 0 else 0.0
    
    def _get_onchain_usdc_balance(self) -> float:
        """
        Query USDC balance directly from blockchain.
        Used as fallback when API authentication fails.
        """
        try:
            from web3 import Web3
            from src.config import USDC_ADDRESS
            
            # Connect to Polygon RPC
            w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
            
            # USDC contract ABI (just the balanceOf function)
            usdc_abi = [{
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }]
            
            usdc_contract = w3.eth.contract(
                address=Web3.to_checksum_address(USDC_ADDRESS),
                abi=usdc_abi
            )
            
            # Query balance
            balance_wei = usdc_contract.functions.balanceOf(
                Web3.to_checksum_address(self.funder)
            ).call()
            
            # USDC has 6 decimals
            return float(balance_wei) / 1_000_000
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"On-chain balance query failed: {e}")
            return 0.0


class RelayerClient(ApiClient):
    """
    Client for Builder Relayer API.

    Provides gasless transactions through Polymarket's
    relayer infrastructure.

    Example:
        client = RelayerClient(
            host="https://relayer-v2.polymarket.com",
            chain_id=137,
            builder_creds=builder_creds
        )
    """

    def __init__(
        self,
        host: str = "https://relayer-v2.polymarket.com",
        chain_id: int = 137,
        builder_creds: Optional[BuilderConfig] = None,
        tx_type: str = "SAFE",
        timeout: int = 60
    ):
        """
        Initialize Relayer client.

        Args:
            host: Relayer API host
            chain_id: Chain ID (137 for Polygon)
            builder_creds: Builder credentials
            tx_type: Transaction type (SAFE or PROXY)
            timeout: Request timeout
        """
        super().__init__(base_url=host, timeout=timeout)
        self.chain_id = chain_id
        self.builder_creds = builder_creds
        self.tx_type = tx_type

    def _build_headers(
        self,
        method: str,
        path: str,
        body: str = ""
    ) -> Dict[str, str]:
        """Build Builder HMAC authentication headers."""
        if not self.builder_creds or not self.builder_creds.is_configured():
            raise AuthenticationError("Builder credentials required for relayer")

        timestamp = str(int(time.time()))

        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.builder_creds.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            "POLY_BUILDER_API_KEY": self.builder_creds.api_key,
            "POLY_BUILDER_TIMESTAMP": timestamp,
            "POLY_BUILDER_PASSPHRASE": self.builder_creds.api_passphrase,
            "POLY_BUILDER_SIGNATURE": signature,
        }

    def deploy_safe(self, safe_address: str) -> Dict[str, Any]:
        """
        Deploy a Safe proxy wallet.

        Args:
            safe_address: The Safe address to deploy

        Returns:
            Deployment transaction response
        """
        endpoint = "/wallet/deploy-safe"
        body = {
            "safeAddress": safe_address,
            "owner": safe_address  # Some endpoints require owner, usually the Safe itself or EOA
        }
        # Actually, for deploy-safe, the body usually just needs the owner's EOA or the predicted Safe address.
        # Let's stick safeAddress first, but we might need "owner" too.
        # Research suggests: POST /wallet/deploy-safe { "owner": "0xEOA" } or { "safeAddress": "..." }
        # Let's try matching the TypeScript SDK: it sends { safeAddress }.
        
        body_json = json.dumps(body, separators=(',', ':'))
        headers = self._build_headers("POST", endpoint, body_json)

        return self._request(
            "POST",
            endpoint,
            data=body,
            headers=headers
        )

    def approve_usdc(
        self,
        safe_address: str,
        spender: str,
        amount: int
    ) -> Dict[str, Any]:
        """
        Approve USDC spending.

        Args:
            safe_address: Safe address
            spender: Spender address
            amount: Amount to approve

        Returns:
            Approval transaction response
        """
        endpoint = "/allowance/approve"
        # The relayer usually expects: { "token": "USDC_ADDRESS", "spender": "...", "amount": "...", "safeAddress": "..." }
        # Need to verify if "token" is implicit or explicit.
        # Let's assume explicit for now, but defaulting to USDC logic inside the bot caller.
        # Wait, the bot caller passed 'amount' and we didn't pass the token address here.
        # Let's update the caller or hardcode USDC here if we are sure.
        # Actually the method signature is approve_usdc, so hardcoding/config lookup is fine.
        from src.config import USDC_ADDRESS
        
        body = {
            "safeAddress": safe_address,
            "token": USDC_ADDRESS,
            "spender": spender,
            "amount": str(amount),
        }
        body_json = json.dumps(body, separators=(',', ':'))
        headers = self._build_headers("POST", endpoint, body_json)

        return self._request(
            "POST",
            endpoint,
            data=body,
            headers=headers
        )

    def approve_token(
        self,
        safe_address: str,
        token_id: str,
        spender: str,
        amount: int
    ) -> Dict[str, Any]:
        """
        Approve an ERC-1155 token.

        Args:
            safe_address: Safe address
            token_id: Token ID
            spender: Spender address
            amount: Amount to approve

        Returns:
            Approval transaction response
        """
        endpoint = "/approve-token"
        body = {
            "safeAddress": safe_address,
            "tokenId": token_id,
            "spender": spender,
            "amount": str(amount),
        }
        body_json = json.dumps(body, separators=(',', ':'))
        headers = self._build_headers("POST", endpoint, body_json)

        return self._request(
            "POST",
            endpoint,
            data=body,
            headers=headers
        )


