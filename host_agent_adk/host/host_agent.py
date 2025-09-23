
"""Coordinator agent that bridges Google's ADK runner with remote friend agents.

This module wires together the Google Agent Development Kit (ADK) components with
our custom remote-agent protocol. The goal is to make it easy to understand how
messages flow between the host agent, the ADK runtime, and external friends.
"""

import json
import uuid
from datetime import datetime
from textwrap import dedent
from typing import Any, AsyncIterable

import httpx

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from .config import (
    AGENT_ID,
    AGENT_THINKING_MESSAGE,
    DEFAULT_LLM_MODEL,
    REMOTE_AGENT_TIMEOUT_SECONDS,
)
from .jam_session_tools import (
    book_jam_session,
    list_jam_spot_availabilities,
)
from .remote_agent_connection import RemoteAgentConnections


AgentConnectionMap = dict[str, RemoteAgentConnections]
AgentCardMap = dict[str, AgentCard]


class HostAgent:
    """The Host agent responsible for coordinating jam sessions."""
    _USER_ID = AGENT_ID

    def __init__(
        self,
    ):
        # Remote connections are lazily populated once we discover friend cards.
        self.remote_agent_connections: AgentConnectionMap = {}
        self.cards: AgentCardMap = {}
        self.agents: str = ""
        self._agent = self.create_agent()
        self._runner = self._create_runner()

    async def _async_init_components(self, remote_agent_addresses: list[str]) -> None:
        """Populate remote agent connections and build the friend directory."""

        # The ADK executes tools asynchronously, so we mirror that pattern and
        # reuse a single HTTP client while we gather cards from remote friends.
        async with httpx.AsyncClient(timeout=REMOTE_AGENT_TIMEOUT_SECONDS) as client:
            for address in remote_agent_addresses:
                await self._register_remote_agent(client, address)

        self._refresh_agent_directory()

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: list[str],
    ) -> "HostAgent":
        """Factory that prepares an instance with remote connections primed."""

        instance = cls()
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        """Instantiate the underlying Google ADK agent."""

        return Agent(
            model=LiteLlm(model=DEFAULT_LLM_MODEL),
            name="Host_Agent",
            instruction=self.root_instruction,
            description="This Host agent orchestrates scheduling jam sessions with friends.",
            tools=[
                self.send_message,
                book_jam_session,
                list_jam_spot_availabilities,
            ],
        )

    def _create_runner(self) -> Runner:
        """Build the runner that mediates sessions and tool execution."""
        # The runner owns session state, memory, and persistence. We plug in
        # simple in-memory services so the example stays lightweight.
        return Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        """Provide the root instruction prompt for the agent."""

        del context
        instruction = f"""
        **Role:** You are the Host Agent, an expert scheduler for jam sessions. Your primary function is to coordinate with friend agents to find a suitable time to play and then book time.

        **Core Directives:**

        *   **Initiate Planning:** When asked to schedule a session, first determine who to invite and the desired date range from the user.
        *   **Task Delegation:** Use the `send_message` tool to ask each friend for their availability.
            *   Frame your request clearly (e.g., "Are you available for jam session between 2024-08-01 and 2024-08-03?").
            *   Make sure you pass in the official name of the friend agent for each message request.
        *   **Analyze Responses:** Once you have availability from all friends, analyze the responses to find common timeslots.
        *   **Check Friends Availability:** Before proposing times to the user, use the `list_jam_spot_availabilities` tool to ensure the friends is also free at the common timeslots.
        *   **Propose and Confirm:** Present the common, jam spot available timeslots to the user for confirmation.
        *   **Book the jam spot:** After the user confirms a time, use the `book_jam_session` tool to make the reservation. This tool requires a `start_time` and an `end_time`.
        *   **Transparent Communication:** Relay the final booking confirmation, including the booking ID, to the user. Do not ask for permission before contacting friend agents.
        *   **Tool Reliance:** Strictly rely on available tools to address user requests. Do not generate responses based on assumptions.
        *   **Readability:** Make sure to respond in a concise and easy to read format (bullet points are good).
        *   Each available agent represents a friend. So Bob_Agent represents Bob.
        *   When asked for which friends are available, you should return the names of the available friends (aka the agents that are active).
        *   When get

        **Today's Date (YYYY-MM-DD):** {datetime.now().strftime("%Y-%m-%d")}

        <Available Agents>
        {self.agents or "No friends found"}
        </Available Agents>
        """

        return dedent(instruction).strip()

    async def stream(
        self, query: str, session_id: str
    ) -> AsyncIterable[dict[str, Any]]:
        """Stream the agent's response to a given query."""

        session = await self._get_or_create_session(session_id)
        content = self._build_user_content(query)

        async for event in self._runner.run_async(
            user_id=AGENT_ID, session_id=session.id, new_message=content
        ):
            if event.is_final_response():
                response = self._extract_response_text(event.content)
                yield {
                    "is_task_complete": True,
                    "content": response,
                }
                continue

            yield {
                "is_task_complete": False,
                "updates": AGENT_THINKING_MESSAGE,
            }

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ) -> list[dict[str, Any]] | None:
        """Send a task to a remote friend agent and return any artifact parts."""

        client = self.remote_agent_connections.get(agent_name)
        if client is None:
            raise ValueError(f"Agent {agent_name} not found")

        # The remote API expects a stable task/context ID pair. 
        # We reuse any values stored in the tool context so multi-turn workflows stay linked.
        message_id, task_id, context_id = self._resolve_message_identifiers(tool_context)
        payload = self._build_message_payload(task, message_id, task_id, context_id)

        # Sending message
        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(message_request)
        print("send_response", send_response)

        if not isinstance(
            send_response.root, SendMessageSuccessResponse
        ) or not isinstance(send_response.root.result, Task):
            print("Received a non-success or non-task response. Cannot proceed.")
            return None

        response_content = send_response.root.model_dump_json(exclude_none=True)
        json_content = json.loads(response_content)
        artifacts = json_content.get("result", {}).get("artifacts", [])

        responses: list[dict[str, Any]] = []
        for artifact in artifacts:
            responses.extend(artifact.get("parts", []))

        return responses

    async def _register_remote_agent(
        self, client: httpx.AsyncClient, address: str
    ) -> None:
        """Fetch a remote agent card and register the connection."""

        card_resolver = A2ACardResolver(client, address)
        try:
            card = await card_resolver.get_agent_card()
        except httpx.ConnectError as error:
            print(f"ERROR: Failed to get agent card from {address}: {error}")
            return
        except Exception as error:
            print(f"ERROR: Failed to initialize connection for {address}: {error}")
            return

        # Cards tell us who the friend is and which URL to use for messaging.
        remote_connection = RemoteAgentConnections(agent_card=card, agent_url=address)
        self.remote_agent_connections[card.name] = remote_connection
        self.cards[card.name] = card

    def _refresh_agent_directory(self) -> None:
        """Update the formatted list of available friends for instructions."""

        agent_info = [
            json.dumps({"name": card.name, "description": card.description})
            for card in self.cards.values()
        ]
        print("agent_info:", agent_info)
        self.agents = "\n".join(agent_info) if agent_info else "No friends found"

    async def _get_or_create_session(self, session_id: str):
        """Return an existing session or create a new one for the given id."""

        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=AGENT_ID,
            session_id=session_id,
        )
        if session is not None:
            return session

        return await self._runner.session_service.create_session(
            app_name=self._agent.name,
            user_id=AGENT_ID,
            state={},
            session_id=session_id,
        )

    @staticmethod
    def _build_user_content(query: str) -> types.Content:
        """Construct the GenAI content payload from a user query."""

        return types.Content(role="user", parts=[types.Part.from_text(text=query)])

    @staticmethod
    def _extract_response_text(content: types.Content | None) -> str:
        """Collect text parts from the final response event."""

        if content is None or not getattr(content, "parts", None):
            return ""

        return "\n".join(
            part.text for part in content.parts if getattr(part, "text", None)
        )

    @staticmethod
    def _resolve_message_identifiers(
        tool_context: ToolContext,
    ) -> tuple[str, str, str]:
        """Return message, task, and context identifiers for remote calls."""

        state = getattr(tool_context, "state", {}) or {}
        task_id = state.get("task_id") or str(uuid.uuid4())
        context_id = state.get("context_id") or str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        return message_id, task_id, context_id

    @staticmethod
    def _build_message_payload(
        task: str, message_id: str, task_id: str, context_id: str
    ) -> dict[str, Any]:
        """Compose the payload expected by the remote send_message endpoint."""
        # Remote friends use the A2A schema, so we mirror its structure rather
        # than constructing lower-level HTTP requests by hand.
        return {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": task}],
                "messageId": message_id,
                "taskId": task_id,
                "contextId": context_id,
            },
        }
