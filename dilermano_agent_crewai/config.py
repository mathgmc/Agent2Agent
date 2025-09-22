import os
from dotenv import load_dotenv


load_dotenv()

HOST_URL = os.getenv("HOST_URL", "localhost")
HOST_PORT = int(os.getenv("HOST_PORT", "10003"))
HOST_ADDR = f"http://{HOST_URL}:{HOST_PORT}/"
