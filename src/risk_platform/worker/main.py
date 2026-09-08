import asyncio
import logging

from risk_platform.core.config import get_settings
from risk_platform.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("risk_worker_started", extra={"environment": settings.app_env})
    while True:
        # Job claiming and processing are added with the risk_jobs table.
        await asyncio.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run())
