import os
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
TOKEN = os.getenv("TOKEN")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
INITMODEL = os.getenv("INITMODEL", "llama3.1")