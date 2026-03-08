import logging

from app.application.services import (
    AccountService,
    MarketDataService,
    OrderService,
    PositionService,
)
from app.infrastructure.ctrader_client import CtraderClient
from app.infrastructure.ctrader_oauth_client import CtraderOAuthClient
from app.infrastructure.redis_streams_publisher import RedisStreamsPublisher
from app.infrastructure.stream_registry import StreamRegistry
from app.infrastructure.token_lifecycle import TokenLifecycleManager
from app.infrastructure.token_repository import RedisTokenRepository
from app.infrastructure.trendbar_stream_registry import TrendbarStreamRegistry
from app.settings import Settings
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Simple service locator stored on FastAPI app state."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        credentials = settings.load_credentials()

        self.redis: Redis = Redis.from_url(settings.redis_url)
        self.token_repository = RedisTokenRepository(
            self.redis,
            settings.broker_token_redis_key,
        )
        self.token_oauth_client = CtraderOAuthClient(credentials)
        self.token_lifecycle = TokenLifecycleManager(
            settings=settings,
            credentials=credentials,
            repository=self.token_repository,
            oauth_client=self.token_oauth_client,
        )
        self.broker_client = CtraderClient(
            credentials,
            request_timeout=settings.ctrader_request_timeout_seconds,
            access_token_provider=self.token_lifecycle.get_access_token,
        )
        self.token_lifecycle.set_token_refreshed_callback(
            self.broker_client.reset_authorized_accounts,
        )
        self.redis_publisher = RedisStreamsPublisher(
            self.redis,
            settings,
        )
        self.stream_registry = StreamRegistry(
            subscribe_fn=self.broker_client.register_tick_handler,
            unsubscribe_fn=self.broker_client.unregister_tick_handler,
            publisher=self.redis_publisher.publish_tick,
            settings=settings,
        )
        self.trendbar_stream_registry = TrendbarStreamRegistry(
            subscribe_fn=self.broker_client.register_trendbar_handler,
            unsubscribe_fn=self.broker_client.unregister_trendbar_handler,
            publisher=self.redis_publisher.publish_candle,
            settings=settings,
        )

        self.account_service = AccountService(self.broker_client)
        self.order_service = OrderService(self.broker_client)
        self.position_service = PositionService(self.broker_client)
        self.market_data_service = MarketDataService(
            self.broker_client,
            self.stream_registry,
            self.trendbar_stream_registry,
        )

    async def startup(self) -> None:
        await self.token_lifecycle.startup()
        await self.broker_client.connect()
        try:
            await self.redis.ping()  # type: ignore[func-returns-value]
        except Exception:
            logger.exception("Unable to ping Redis during startup")

    async def shutdown(self) -> None:
        await self.stream_registry.shutdown()
        await self.trendbar_stream_registry.shutdown()
        await self.broker_client.disconnect()
        await self.token_lifecycle.shutdown()
        await self.redis_publisher.close()

    @property
    def broker_connected(self) -> bool:
        return self.broker_client.is_connected

    @property
    def active_streams(self) -> int:
        return self.stream_registry.active_stream_count()

    @property
    def active_trendbar_streams(self) -> int:
        return self.trendbar_stream_registry.active_stream_count()

    @property
    def token_lifecycle_component(self) -> dict[str, str | None]:
        return self.token_lifecycle.health_component()
