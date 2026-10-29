"""Startup seed of the livestock connector: creates no connector definitions.

Replaces the crop build's module of the same name, which inserted crop's four ODK
pipelines, with personal ODK credential fallbacks, into any connector database it
started against. main.py still calls seed_default_pipelines at start, so the name and
signature stay.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncConnection

_logger = logging.getLogger("connector.pipelines.seed")


async def seed_default_pipelines(conn: AsyncConnection) -> None:
    _logger.info("No default pipelines: livestock connector definitions are created through the admin API.")
