import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "claude" or "cosmos_ai"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
COSMOS_AI_API_KEY = os.getenv("COSMOS_AI_API_KEY", "")
COSMOS_AI_ENDPOINT = os.getenv("COSMOS_AI_ENDPOINT", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# FastAPI settings
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv("PORT", "8080"))  # Railway sets PORT env var

# Public URL for Mini App (set after Railway deploy)
WEBAPP_URL = os.getenv("WEBAPP_URL", f"http://localhost:{API_PORT}")
