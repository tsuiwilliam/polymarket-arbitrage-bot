"""
Polymarket Arbitrage Bot - Main Trading Interface

The core TradingBot class provides a high-level interface for interacting
with the Polymarket decentralized prediction market platform. This module
handles order placement, cancellation, position management, and real-time
market data retrieval.

Features:
    - Gasless transactions via Builder Program integration
    - Encrypted private key storage support
    - Modular strategy support for custom trading logic
    - Comprehensive order management (place, cancel, query)
    - Real-time market data and orderbook access

Example:
    from src.bot import TradingBot, Config

    # Initialize with config file
    bot = TradingBot(config_path="config.yaml")

    # Or initialize manually
    from src.config import BuilderConfig
    config = Config(
        safe_address="0x...",
        builder=BuilderConfig(api_key="...", api_secret="...")
    )
    bot = TradingBot(config=config, private_key="0x...")

    # Or use encrypted key file
    bot = TradingBot(
        config=config,
        encrypted_key_path="credentials/key.enc",
        password="your_password"
    )

    # Place a limit order
    result = await bot.place_order(
        token_id="123...",
        price=0.65,
        size=10.0,
        side="BUY"
    )

    if result.success:
        print(f"Order placed: {result.order_id}")
    else:
        print(f"Order failed: {result.message}")

Note:
    All methods are async and must be awaited. The bot automatically
    handles initialization, signing, and API communication.
"""

import os
import asyncio
import logging
import time
import random
from typing import Optional, Dict, Any, List, Callable, TypeVar
from dataclasses import dataclass, field
from enum import Enum

from .config import Config, BuilderConfig
from .signer import OrderSigner, Order
from .client import ClobClient, RelayerClient, ApiCredentials
from .crypto import KeyManager, CryptoError, InvalidPasswordError
from .gamma_client import GammaClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

T = TypeVar("T")

class OrderSide(str, Enum):
    """Order side constants."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type constants."""
    GTC = "GTC"  # Good Till Cancelled
    GTD = "GTD"  # Good Till Date
    FOK = "FOK"  # Fill Or Kill


@dataclass
class OrderResult:
    """Result of an order operation."""
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> "OrderResult":
        """Create from API response."""
        success = response.get("success", False)
        error_msg = response.get("errorMsg", "")

        return cls(
            success=success,
            order_id=response.get("orderId"),
            status=response.get("status"),
            message=error_msg if not success else "Order placed successfully",
            data=response
        )


class TradingBotError(Exception):
    """Base exception for trading bot errors."""
    pass


class NotInitializedError(TradingBotError):
    """Raised when bot is not initialized."""
    pass


class TradingBot:
    """
    Main trading bot class for Polymarket.

    Provides a high-level interface for:
    - Order placement and cancellation
    - Position management
    - Trade history
    - Gasless transactions (with Builder Program)

    Attributes:
        config: Bot configuration
        signer: Order signer instance
        clob_client: CLOB API client
        relayer_client: Relayer API client (if gasless enabled)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[Config] = None,
        safe_address: Optional[str] = None,
        builder_creds: Optional[BuilderConfig] = None,
        private_key: Optional[str] = None,
        encrypted_key_path: Optional[str] = None,
        password: Optional[str] = None,
        api_creds_path: Optional[str] = None,
        log_level: int = logging.INFO
    ):
        """
        Initialize trading bot.

        Can be initialized in multiple ways:

        1. From config file:
           bot = TradingBot(config_path="config.yaml")

        2. From Config object:
           bot = TradingBot(config=my_config)

        3. With manual parameters:
           bot = TradingBot(
               safe_address="0x...",
               builder_creds=builder_creds,
               private_key="0x..."
           )

        4. With encrypted key:
           bot = TradingBot(
               safe_address="0x...",
               encrypted_key_path="credentials/key.enc",
               password="mypassword"
           )

        Args:
            config_path: Path to config YAML file
            config: Config object
            safe_address: Safe/Proxy wallet address
            builder_creds: Builder Program credentials
            private_key: Raw private key (with 0x prefix)
            encrypted_key_path: Path to encrypted key file
            password: Password for encrypted key
            api_creds_path: Path to API credentials file
            log_level: Logging level
        """
        # Set log level
        logger.setLevel(log_level)

        # Load configuration
        if config_path:
            self.config = Config.load(config_path)
        elif config:
            self.config = config
        else:
            self.config = Config()

        # Override with provided parameters
        if safe_address:
            self.config.safe_address = safe_address
        if builder_creds:
            self.config.builder = builder_creds
            self.config.use_gasless = True

        # Initialize components
        self.signer: Optional[OrderSigner] = None
        self.clob_client: Optional[ClobClient] = None
        self.relayer_client: Optional[RelayerClient] = None
        self._api_creds: Optional[ApiCredentials] = None

        # Load private key
        if private_key:
            self.signer = OrderSigner(private_key)
        elif encrypted_key_path and password:
            self._load_encrypted_key(encrypted_key_path, password)

        # Load API credentials
        if api_creds_path:
            self._load_api_creds(api_creds_path)

        # Initialize API clients
        self._init_clients()

        # Auto-derive API credentials for all modes
        # Per Polymarket docs: User API credentials are needed for ClobClient constructor
        # even in Proxy mode, though only Builder credentials are sent in request headers
        if self.signer and not self._api_creds:
            self._derive_api_creds()

        # Components for auto-discovery
        self.gamma_client = GammaClient(host=self.config.clob.host.replace("clob", "gamma-api"))
        
        logger.info(f"TradingBot initialized (gasless: {self.config.use_gasless})")

    def _load_encrypted_key(self, filepath: str, password: str) -> None:
        """Load and decrypt private key from encrypted file."""
        try:
            manager = KeyManager()
            private_key = manager.load_and_decrypt(password, filepath)
            self.signer = OrderSigner(private_key)
            logger.info(f"Loaded encrypted key from {filepath}")
        except FileNotFoundError:
            raise TradingBotError(f"Encrypted key file not found: {filepath}")
        except InvalidPasswordError:
            raise TradingBotError("Invalid password for encrypted key")
        except CryptoError as e:
            raise TradingBotError(f"Failed to load encrypted key: {e}")

    def _load_api_creds(self, filepath: str) -> None:
        """Load API credentials from file."""
        if os.path.exists(filepath):
            try:
                self._api_creds = ApiCredentials.load(filepath)
                logger.info(f"Loaded API credentials from {filepath}")
            except Exception as e:
                logger.warning(f"Failed to load API credentials: {e}")

    def _derive_api_creds(self) -> None:
        """Derive L2 API credentials from signer."""
        if not self.signer or not self.clob_client:
            return

        try:
            logger.info("Deriving L2 API credentials...")
            self._api_creds = self.clob_client.create_or_derive_api_key(self.signer)
            self.clob_client.set_api_creds(self._api_creds)
            logger.info("L2 API credentials derived successfully")
        except Exception as e:
            logger.warning(f"Failed to derive API credentials: {e}")
            logger.warning("Some API endpoints may not be accessible")

    def _init_clients(self) -> None:
        """Initialize API clients."""
        # CLOB client
        # Determine funder address based on signature type
        # If using EOA (type 0), funder should be the EOA address (signer)
        # If using SAFE (type 1/2), funder should be the Safe address
        funder_address = self.config.safe_address
        if self.config.clob.signature_type == 0 and self.signer:
            funder_address = self.signer.address
            logger.info(f"Using EOA address {funder_address} as funder (Signature Type 0)")
        
        self.clob_client = ClobClient(
            host=self.config.clob.host,
            chain_id=self.config.clob.chain_id,
            signature_type=self.config.clob.signature_type,
            funder=funder_address,
            api_creds=self._api_creds,
            builder_creds=self.config.builder if self.config.use_gasless else None,
            signer_address=self.signer.address if self.signer else "",
        )

        # Relayer client (for gasless)
        if self.config.use_gasless:
            self.relayer_client = RelayerClient(
                host=self.config.relayer.host,
                chain_id=self.config.clob.chain_id,
                builder_creds=self.config.builder,
                tx_type=self.config.relayer.tx_type,
            )
            logger.info("Relayer client initialized (gasless enabled)")

    async def auto_discover_proxy(self) -> Optional[str]:
        """
        Attempt to automatically discover the user's proxy (Safe) address.
        Checks the Gamma API public-profile first.
        """
        if not self.signer:
            return None
        
        eoa = self.signer.address
        logger.info(f"Attempting to auto-discover proxy for {eoa}...")
        
        try:
            profile = await self._run_in_thread(self.gamma_client.get_public_profile, eoa)
            if profile and profile.get("proxyWallet"):
                proxy = profile["proxyWallet"]
                logger.info(f"✓ Found proxy wallet: {proxy}")
                return proxy
            
            logger.info("! No proxy wallet found in public profile.")
            return None
        except Exception as e:
            logger.warning(f"Failed to auto-discover proxy: {e}")
            return None

    async def verify_setup(self) -> bool:
        """
        Verify that the bot is properly configured and has access to APIs.
        Returns True if setup is valid.
        """
        logger.info("--- Performing Startup Sanity Checks ---")
        success = True

        # 1. Check Signer/Funder
        if not self.signer:
            logger.error("✗ No private key loaded. Signer unavailable.")
            success = False
        else:
            logger.info(f"✓ Signer loaded: {self.signer.address}")

        # 2. Check User API Credentials
        # Both EOA and Proxy modes need L2 API credentials for authentication
        # Builder credentials are for attribution only
        try:
            # get_open_orders is a reliable health check for L2 auth
            await self._run_in_thread(self.clob_client.get_open_orders)
            logger.info("✓ User API Key valid.")
        except Exception as e:
            if self.config.clob.signature_type == 2:
                # In Proxy mode, L2 API check may fail but Builder auth is sufficient for orders
                logger.warning(f"! L2 API check failed in Proxy mode (expected): {e}")
                logger.info("✓ Proxy mode: Builder credentials will be used for order placement")
            else:
                # In EOA mode, L2 API credentials are required
                logger.error(f"✗ User API credentials invalid or expired: {e}")
                success = False

        # 3. Check Builder API (if gasless)
        if self.config.use_gasless:
            if not self.config.builder or not self.config.builder.is_configured():
                logger.error("✗ Gasless enabled but Builder API keys are missing (Master Builder fallback failed)")
                success = False
            else:
                logger.info("✓ Builder API keys configured (using Admin or User keys)")
            
            if not self.config.safe_address:
                logger.info("! POLY_PROXY_WALLET missing. Attempting auto-discovery...")
                proxy = await self.auto_discover_proxy()
                if proxy:
                    self.config.safe_address = proxy
                    self._init_clients()
                    logger.info(f"✓ Proxy Wallet discovered: {proxy}")
                else:
                    logger.error("✗ Gasless enabled but proxy wallet could not be discovered.")
                    success = False
            
            if self.config.safe_address:
                logger.info("✓ Proxy Wallet configured. Checking deployment...")
                # Try to deploy/ensure deployment
                await self.deploy_safe_if_needed()
                # Ensure USDC approval for CTF exchange
                await self.approve_usdc_gasless()
                logger.info("✓ Proxy setup (deployment/approval) initiated.")
                
                # 3b. Test order placement (validate auth works end-to-end)
                logger.info("Testing order placement authentication with live API call...")
                try:
                    # Create a test order with impossible price to avoid execution
                    test_token_id = "99914208981568816645551301561974062576963636618104166856807686031985202521238"  # BTC UP
                    
                    from src.signer import Order
                    import random
                    import json
                    
                    test_order = Order(
                        token_id=test_token_id,
                        price=0.001,  # Extremely low price - will never match
                        size=0.01,    # Minimal size (1 cent)
                        side="BUY",
                        maker=self.config.safe_address,
                        expiration=0,
                        salt=random.randint(1, 10**12),
                        nonce=None,
                        fee_rate_bps=0,
                        signature_type=self.config.clob.signature_type,
                    )
                    
                    # Sign the order
                    api_key = self.config.safe_address if self.config.clob.signature_type == 2 else self.clob_client.api_creds.api_key
                    signed = self.signer.sign_order(test_order, api_key=api_key)
                    
                    # Build headers
                    body_json = json.dumps(signed, separators=(',', ':'))
                    headers = self.clob_client._build_headers("POST", "/order", body_json)
                    
                    # Log headers for debugging
                    logger.info(f"Test order headers: {list(headers.keys())}")
                    if "POLY_BUILDER_API_KEY" in headers:
                        logger.info("  ✓ Builder credentials included")
                    if "POLY_API_KEY" in headers:
                        logger.info(f"  ✓ User L2 credentials included (POLY_ADDRESS: {headers.get('POLY_ADDRESS', 'N/A')})")
                    
                    # Actually POST the test order to the server
                    logger.info("Submitting test order to Polymarket API...")
                    try:
                        response = await self._run_in_thread(
                            self.clob_client.post_order,
                            signed,
                            "GTC"
                        )
                        logger.info(f"✓ Test order ACCEPTED! Order ID: {response.get('orderID', 'N/A')}")
                        logger.info("  Authentication is working correctly!")
                        # Cancel the test order immediately
                        try:
                            await self._run_in_thread(
                                self.clob_client.cancel_order,
                                response.get('orderID')
                            )
                            logger.info("  Test order cancelled successfully")
                        except:
                            pass  # Ignore cancel errors
                    except Exception as post_error:
                        error_msg = str(post_error)
                        logger.error(f"✗ Test order REJECTED: {error_msg}")
                        if "401" in error_msg or "Unauthorized" in error_msg:
                            logger.error("  → Authentication failure - credentials are invalid or mismatched")
                            logger.error(f"  → Check that POLY_ADDRESS matches the address used to derive API key")
                            success = False
                        elif "400" in error_msg:
                            logger.warning("  → Order format issue (but auth might be OK)")
                        else:
                            logger.error(f"  → Unexpected error: {error_msg}")
                            success = False
                        
                except Exception as e:
                    logger.error(f"✗ Order validation failed: {e}")
                    success = False

        # 4. Check Balance
        try:
            balance = await self.get_collateral_balance()
            logger.info(f"✓ USDC Balance: ${balance:.2f}")
            if balance < 1.0:
                logger.warning("! Low balance (under $1.00). Trades might fail.")
        except Exception as e:
            logger.warning(f"! Could not fetch balance (check your network/RPC): {e}")

        logger.info("--- Sanity Checks Complete ---")
        return success

    async def _run_in_thread(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a blocking call in a worker thread to avoid event loop stalls."""
        return await asyncio.to_thread(func, *args, **kwargs)

    def is_initialized(self) -> bool:
        """Check if bot is properly initialized."""
        return (
            self.signer is not None and
            self.config.safe_address and
            self.clob_client is not None
        )

    def require_signer(self) -> OrderSigner:
        """Get signer or raise if not initialized."""
        if not self.signer:
            raise NotInitializedError(
                "Signer not initialized. Provide private_key or encrypted_key."
            )
        return self.signer

    async def place_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str = "GTC",
        fee_rate_bps: int = 0
    ) -> OrderResult:
        """
        Place a limit order.

        Args:
            token_id: Market token ID
            price: Price per share (0-1)
            size: Number of shares
            side: 'BUY' or 'SELL'
            order_type: Order type (GTC, GTD, FOK)
            fee_rate_bps: Fee rate in basis points

        Returns:
            OrderResult with order status
        """
        signer = self.require_signer()

        try:
            # Determine maker address
            maker_address = self.config.safe_address
            if self.config.clob.signature_type == 0 and self.signer:
                maker_address = self.signer.address

            # For GTC orders, expiration must be 0. For GTD, it should be a timestamp.
            expiration = 0 if order_type == "GTC" else int(time.time() + 3600)
            salt = random.randint(1, 10**12)      # Random salt for uniqueness

            order = Order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                maker=maker_address,
                expiration=expiration,
                salt=salt,
                nonce=None, # Allow Order class to generate timestamp nonce
                fee_rate_bps=fee_rate_bps,
                signature_type=self.config.clob.signature_type,
            )

            # Sign order with appropriate owner
            # In Proxy mode (signature_type=2), owner is the Proxy address
            # In EOA mode (signature_type=0), owner is the API key
            if self.config.clob.signature_type == 2:
                # Proxy mode: owner is the Proxy wallet address
                api_key = self.config.safe_address
            else:
                # EOA mode: owner is the API key
                api_key = self.clob_client.api_creds.api_key if self.clob_client.api_creds else None
            
            signed = signer.sign_order(order, api_key=api_key)

            # Log physical payload for debugging auth issues
            logger.debug(f"Order owner field (API Key): {signed.get('owner')}")
            logger.debug(f"Order maker field: {signed.get('order', {}).get('maker')}")

            # Submit to CLOB
            try:
                response = await self._run_in_thread(
                    self.clob_client.post_order,
                    signed,
                    order_type,
                )
                
                # If we get a response, it's already parsed as JSON
                order_result = OrderResult.from_response(response)
                if not order_result.success:
                    error_msg = response.get("errorMsg", "Unknown error")
                    logger.error(f"Order placement failed: {error_msg}")
                    logger.debug(f"Raw error response: {response}")
                return order_result
            except Exception as e:
                logger.error(f"Post order exception: {e}")
                return OrderResult(success=False, message=str(e))

            logger.info(
                f"Order placed: {side} {size}@{price} "
                f"(token: {token_id[:16]}...)"
            )

            return OrderResult.from_response(response)

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return OrderResult(
                success=False,
                message=str(e)
            )

    async def place_orders(
        self,
        orders: List[Dict[str, Any]],
        order_type: str = "GTC"
    ) -> List[OrderResult]:
        """
        Place multiple orders.

        Args:
            orders: List of order dictionaries with keys:
                - token_id: Market token ID
                - price: Price per share
                - size: Number of shares
                - side: 'BUY' or 'SELL'
            order_type: Order type (GTC, GTD, FOK)

        Returns:
            List of OrderResults
        """
        results = []
        for order_data in orders:
            result = await self.place_order(
                token_id=order_data["token_id"],
                price=order_data["price"],
                size=order_data["size"],
                side=order_data["side"],
                order_type=order_type,
            )
            results.append(result)

            # Small delay between orders to avoid rate limits
            await asyncio.sleep(0.1)

        return results

    async def cancel_order(self, order_id: str) -> OrderResult:
        """
        Cancel a specific order.

        Args:
            order_id: Order ID to cancel

        Returns:
            OrderResult with cancellation status
        """
        try:
            response = await self._run_in_thread(self.clob_client.cancel_order, order_id)
            logger.info(f"Order cancelled: {order_id}")
            return OrderResult(
                success=True,
                order_id=order_id,
                message="Order cancelled",
                data=response
            )
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return OrderResult(
                success=False,
                order_id=order_id,
                message=str(e)
            )

    async def cancel_all_orders(self) -> OrderResult:
        """
        Cancel all open orders.

        Returns:
            OrderResult with cancellation status
        """
        try:
            response = await self._run_in_thread(self.clob_client.cancel_all_orders)
            logger.info("All orders cancelled")
            return OrderResult(
                success=True,
                message="All orders cancelled",
                data=response
            )
        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
            return OrderResult(success=False, message=str(e))

    async def cancel_market_orders(
        self,
        market: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> OrderResult:
        """
        Cancel orders for a specific market.

        Args:
            market: Condition ID of the market (optional)
            asset_id: Token/asset ID (optional)

        Returns:
            OrderResult with cancellation status
        """
        try:
            response = await self._run_in_thread(
                self.clob_client.cancel_market_orders,
                market,
                asset_id,
            )
            logger.info(f"Market orders cancelled (market: {market or 'all'}, asset: {asset_id or 'all'})")
            return OrderResult(
                success=True,
                message=f"Orders cancelled for market {market or 'all'}",
                data=response
            )
        except Exception as e:
            logger.error(f"Failed to cancel market orders: {e}")
            return OrderResult(success=False, message=str(e))

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders.

        Returns:
            List of open orders
        """
        try:
            orders = await self._run_in_thread(self.clob_client.get_open_orders)
            logger.debug(f"Retrieved {len(orders)} open orders")
            return orders
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order details.

        Args:
            order_id: Order ID

        Returns:
            Order details or None
        """
        try:
            return await self._run_in_thread(self.clob_client.get_order, order_id)
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None

    async def get_trades(
        self,
        token_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get trade history.

        Args:
            token_id: Optional token ID to filter
            limit: Maximum number of trades

        Returns:
            List of trades
        """
        try:
            trades = await self._run_in_thread(self.clob_client.get_trades, token_id, limit)
            logger.debug(f"Retrieved {len(trades)} trades")
            return trades
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []

    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book for a token.

        Args:
            token_id: Market token ID

        Returns:
            Order book data
        """
        try:
            return await self._run_in_thread(self.clob_client.get_order_book, token_id)
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return {}

    async def get_market_price(self, token_id: str) -> Dict[str, Any]:
        """
        Get current market price for a token.

        Args:
            token_id: Market token ID

        Returns:
            Price data
        """
        try:
            return await self._run_in_thread(self.clob_client.get_market_price, token_id)
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")
            return {}

    async def deploy_safe_if_needed(self) -> bool:
        """
        Deploy Safe proxy wallet if not already deployed.

        Returns:
            True if deployment was needed or successful
        """
        if not self.config.use_gasless or not self.relayer_client:
            logger.debug("Gasless not enabled, skipping Safe deployment")
            return False

        try:
            response = await self._run_in_thread(
                self.relayer_client.deploy_safe,
                self.config.safe_address,
            )
            logger.info(f"Safe deployment initiated: {response}")
            return True
        except Exception as e:
            logger.warning(f"Safe deployment failed (may already be deployed): {e}")
            return False

    async def approve_usdc_gasless(self, amount: int = 10**12) -> bool:
        """
        Approve USDC spending via Builder Relayer.
        
        Args:
            amount: Amount in base units (6 decimals). Default: $1M
        """
        if not self.config.use_gasless or not self.relayer_client:
            return False
            
        from src.config import CTF_EXCHANGE_ADDRESS
        try:
            response = await self._run_in_thread(
                self.relayer_client.approve_usdc,
                self.config.safe_address,
                CTF_EXCHANGE_ADDRESS,
                amount
            )
            logger.info(f"USDC approval initiated: {response}")
            return True
        except Exception as e:
            logger.error(f"USDC approval failed: {e}")
            return False

    async def setup_gasless(self) -> Dict[str, bool]:
        """
        Perform complete gasless deployment and approval setup.
        
        Returns:
            Dictionary with setup results
        """
        results = {"deployed": False, "approved": False}
        if not self.config.use_gasless:
            return results
            
        results["deployed"] = await self.deploy_safe_if_needed()
        results["approved"] = await self.approve_usdc_gasless()
        return results
    async def get_collateral_balance(self) -> float:
        """Get USDC balance."""
        if not self.clob_client:
            return 0.0
        return await self._run_in_thread(self.clob_client.get_collateral_balance)

    def create_order_dict(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str
    ) -> Dict[str, Any]:
        """
        Create an order dictionary for batch processing.

        Args:
            token_id: Market token ID
            price: Price per share
            size: Number of shares
            side: 'BUY' or 'SELL'

        Returns:
            Order dictionary
        """
        return {
            "token_id": token_id,
            "price": price,
            "size": size,
            "side": side.upper(),
        }


# Convenience function for quick initialization
def create_bot(
    config_path: str = "config.yaml",
    private_key: Optional[str] = None,
    encrypted_key_path: Optional[str] = None,
    password: Optional[str] = None,
    **kwargs
) -> TradingBot:
    """
    Create a TradingBot instance with common options.

    Args:
        config_path: Path to config file
        private_key: Private key (with 0x prefix)
        encrypted_key_path: Path to encrypted key file
        password: Password for encrypted key
        **kwargs: Additional arguments for TradingBot

    Returns:
        Configured TradingBot instance
    """
    return TradingBot(
        config_path=config_path,
        private_key=private_key,
        encrypted_key_path=encrypted_key_path,
        password=password,
        **kwargs
    )
