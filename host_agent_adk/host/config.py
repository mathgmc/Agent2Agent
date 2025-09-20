import os
from dotenv import load_dotenv


load_dotenv()


# Host Agent Constants
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "openai/gpt-4o-mini")
REMOTE_AGENT_TIMEOUT_SECONDS = int(os.getenv("REMOTE_AGENT_TIMEOUT_SECONDS", "30"))
AGENT_THINKING_MESSAGE = os.getenv("AGENT_THINKING_MESSAGE", "The host agent is thinking...")
AGENT_ID = os.getenv("AGENT_ID", "host_agent")

# Friend's Addr
CARTOLA_AGENT_ADDR = os.getenv("CARTOLA_AGENT_ADDR", "http://localhost:10002")
DILERMANO_AGENT_ADDR = os.getenv("DILERMANO_AGENT_ADDR", "http://localhost:10003")
BUARQUE_AGENT_ADDR = os.getenv("BUARQUE_AGENT_ADDR", "http://localhost:10004")
