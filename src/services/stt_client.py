# ----- handles STT client @src/services/stt_client.py -----
from deepgram import (
    DeepgramClient,
    LiveOptions,
    LiveTranscriptionEvents,
)
from utils.custom_exception import CustomException
from utils.logger import get_logger
from src.core.config import settings

logger = get_logger(__name__)

class SpeechToTextClient:
    """
    Handles STT service, for intermediary between Twilio and LLM
    """
    def __init__(self, on_message_callback):
        """
        Initialises STT client

        Args:
            on_message_callback: A async function called to determine final transcript state
        """
        if not settings.DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM API KEY UNAVAILABLE")
        
        self.deepgram_client = DeepgramClient(settings.DEEPGRAM_API_KEY)
        self.dg_connection = None
        self.on_message_callback = on_message_callback
        self.full_transcript = [] 

    async def start(self):
        """
        Initialises Deepgram connection and event handlers
        """
        try:
            self.dg_connection = self.deepgram_client.listen.asyncwebsocket.v("1")

            self.dg_connection.on(LiveTranscriptionEvents.Open, self.on_open)
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_message)
            self.dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)
            self.dg_connection.on(LiveTranscriptionEvents.Close, self.on_close)

            options = LiveOptions(
                model="nova-2-phonecall",
                language="en-US",
                channels=1,
                endpointing=500,
                interim_results=True,
                smart_format=True,
                punctuate=True,
            )

            logger.info("Connecting to Deepgram...")
            success = await self.dg_connection.start(options)
            if not success:
                logger.error("Failed to connect to Deepgram")
                return False
            return True
        except Exception as e:
            logger.error(f"Error starting Deepgram connection: {e}")
            return False

    async def on_open(self, connection, open, **kwargs):
        """
        Called when the connection to Deepgram is opened
        Args:
            connection: The websocket connection
            open: Open event data
        """
        logger.info("Connected to Deepgram.")

    async def on_message(self, connection, result, **kwargs):
        """
        Handles incoming transcript of audio from twilio and calls the callback on final results.
        Args:
            connection: The websocket connection
            result: The transcription result
        """
        try:
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return

            if result.is_final:
                logger.info(f"Final transcript received: '{sentence}'")
                self.full_transcript.append(sentence)  # Store final transcripts
                await self.on_message_callback(sentence)
            else:
                logger.debug(f"Interim transcript: '{sentence}'")
                
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")

    async def on_error(self, connection, error, **kwargs):
        """
        Called when an error occurs with the Deepgram connection.
        Args:
            connection: The websocket connection
            error: The error object
        """
        logger.error(f"Deepgram error: {error}")

    async def on_close(self, connection, close, **kwargs):
        """
        Called when the connection to Deepgram is closed.
        Args:
            connection: The websocket connection
            close: Close event data
        """
        logger.info("Connection to Deepgram closed.")

    async def send_audio(self, audio_chunk):
        """
        Sends audio data to Deepgram for transcription.
        Args:
            audio_chunk: Raw audio data (bytes)
        """
        try:
            if self.dg_connection and hasattr(self.dg_connection, 'send'):
                await self.dg_connection.send(audio_chunk)
            else:
                logger.warning("Deepgram connection not available for sending audio")

        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")

    async def finish(self):
        """
        Closes the Deepgram connection gracefully.
        """
        try:
            if self.dg_connection:
                await self.dg_connection.finish()
                logger.info("Deepgram connection finished.")
                if self.full_transcript:
                    logger.info(f"Final full transcript: {' '.join(self.full_transcript)}")
        
        except Exception as e:
            logger.error(f"Error finishing Deepgram connection: {e}")