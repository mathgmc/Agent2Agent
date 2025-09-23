import logging
import os
import sys

import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from app.agent import BuarqueAgent
from app.agent_executor import BuarqueAgentExecutor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


def main():
    """Starts Buarque's Agent server."""
    host = "localhost"
    port = 10004
    try:
        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id="schedule_jam_session",
            name="Jam Session Scheduling Tool",
            description="Helps with finding Buarque's availability for jam session",
            tags=["scheduling", "jam session"],
            examples=["Are you free to jam on Saturday?"],
        )
        agent_card = AgentCard(
            name="Buarquen Agent",
            description="Helps with scheduling jam session",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=BuarqueAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=BuarqueAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler(
            agent_executor=BuarqueAgentExecutor(),
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx_client),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
