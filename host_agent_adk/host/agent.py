import asyncio
import nest_asyncio

from .host_agent import HostAgent
from .config import (
    CARTOLA_AGENT_ADDR,
    DILERMANO_AGENT_ADDR,
    BUARQUE_AGENT_ADDR,
)

nest_asyncio.apply()


def _initialize_host_agent_sync():
    """Synchronously creates and initializes the HostAgent."""

    async def _async_main():
        friend_agent_urls = [
            CARTOLA_AGENT_ADDR,
            DILERMANO_AGENT_ADDR,
            BUARQUE_AGENT_ADDR,
        ]

        print("Starting host agent...")
        hosting_agent_instance = await HostAgent.create(
            remote_agent_addresses=friend_agent_urls
        )
        return hosting_agent_instance.create_agent()

    return asyncio.run(_async_main())

# Root agent - Handles all requests, it is required for ADK Web run
root_agent = _initialize_host_agent_sync()
