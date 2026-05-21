"""
om_client.py — OpenMetadata client (STUB)

OpenMetadata integration removed. This stub allows API to start without OM.
All methods return empty/graceful defaults.
"""

import logging

logger = logging.getLogger(__name__)


class OpenMetadataClient:
    """Stub client. No-op methods."""

    def __init__(self, *args, **kwargs):
        logger.info("OpenMetadata client initialized (stub mode — no OM available)")

    async def get_table(self, fqn):
        """Return None — table not found in OM."""
        return None

    async def get_lineage(self, fqn):
        """Return empty lineage."""
        return {"upstream": [], "downstream": []}

    async def list_tables(self, service, database):
        """Return empty list."""
        return []

    async def get_table_profile(self, fqn):
        """Return None — no profile available."""
        return None


def get_om_client():
    """Return stub client. No-op."""
    return OpenMetadataClient()
