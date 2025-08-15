# ----- importable configurations @ src/core/config.py -----
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    """
    Central management for settings and configurations
    Reads .env file
    """
    # LLM settings
    VLLM_API_BASE: str
    LLM_MODEL_NAME: str

    # STT service
    DEEPGRAM_API_KEY: str

    # TELEPHONY service
    TWILIO_API_KEY_SID: str
    TWILIO_API_KEY_SECRET: str
    TWILIO_PHONE_NUMBER: str

    # TTS service
    ELEVENLABS_API_KEY: str

    # Base url for application
    NGROK_URL: str

    class Config:
        env_file = ".env"

settings = Settings()