# ----- Celery handled tasks @ src/workers/tasks.py -----

from src.workers.celery_app import celery_app
from src.services.telephony_client import TelephonyClient
from utils.logger import get_logger

logger=get_logger(__name__)

@celery_app.task
def initiate_call_task(phone_number: str, call_id: str):
    """
    Celery task for initiating call

    Args:
        phone_number (str): The destination phone number
        call_id (str): uuid for call session
    """
    try:
        logger.info(f"Initiating call to {phone_number} with call_id: {call_id} via celery")
        telephony_client=TelephonyClient()
        call_sid=telephony_client.make_call(phone_number, call_id)
        return {
            "status": "success",
            "call_sid": call_sid
        }

    except Exception as e:
        logger.error(f"Error initiating call to {phone_number} with call_id: {call_id} via celery: {e}")
        return {
            "status": "error",
            "message": str(e)
        }