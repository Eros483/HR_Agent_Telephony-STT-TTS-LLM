# ----- importable configurations @ src/core/config.py -----
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    """
    Central management for settings and configurations
    Reads .env file
    """
    # STT service
    DEEPGRAM_API_KEY: str

    # TELEPHONY service
    TWILIO_API_KEY_SID: str
    TWILIO_API_KEY_SECRET: str
    TWILIO_PHONE_NUMBER: str

    #NUMBER TO BE CALLED
    CALL_TO_NUMBER: str

    class Config:
        env_file = ".env"

settings = Settings()