# ----- handles telephony client @src/services/telephony_client.py -----

from twilio.rest import Client
from src.core.config import settings
from utils.logger import get_logger
from utils.custom_exception import CustomException

logger = get_logger(__name__)

class TelephonyClient:
    """
    Handles interaction with Twilio to make outbound calls
    """
    def __init__(self):
        try:
            self.twilio_client=Client(settings.TWILIO_API_KEY_SID, settings.TWILIO_API_KEY_SECRET)
        except Exception as e:
            logger.error(f"Failed to initialize TelephonyClient: {e}")
            raise CustomException("TelephonyClient initialization failed", e)
        
    def make_call(self, to_number: str, call_id: str):
        """
        Creates outbound call to specified number

        Args:
            to_number (str): The phone number to call.
            call_id (str): The unique identifier for the call.
        """
        try:
            webhook_url = f"https://{settings.NGROK_URL.split('//')[1]}/twilio-voice-webhook/{call_id}"

            logger.info(f"Initiating call to {to_number} with webhook url : {webhook_url}")

            call=self.twilio_client.calls.create(
                to=to_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                url=webhook_url
            )
            logger.info(f"Call initiated successfully with SID: {call.sid}")
            return call.sid

        except Exception as e:
            logger.error(f"Failed to make call to {to_number}: {e} ")
            raise CustomException(f"Failed to make call to {to_number}", e)