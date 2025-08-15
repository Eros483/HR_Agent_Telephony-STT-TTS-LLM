# ----- handles tts client @src/services/tts_client.py -----

import asyncio
import os
import websockets
import base64
import json
from dotenv import load_dotenv
from utils.custom_exception import CustomException
from utils.logger import get_logger

# --- Setup ---
load_dotenv()
logger = get_logger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# This is the WebSocket URL for ElevenLabs' Text-to-Speech service.
# You can find other voice IDs in your ElevenLabs Voice Lab.
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM" # Rachel
WEBSOCKET_URL = f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream-input?model_id=eleven_turbo_v2"

class TextToSpeechClient:
    """
    Handles real-time Text-to-Speech conversion using ElevenLabs' WebSocket API.
    """

    async def stream_audio(self, text_stream):
        """
        Connects to ElevenLabs, sends text from a stream, and yields audio chunks.

        Args:
            text_stream: An async generator that yields text chunks (from the LLM).
        Yields:
            bytes: Chunks of audio data in µ-law format.
        """
        if not ELEVENLABS_API_KEY:
            logger.error("ELEVENLABS_API_KEY not set.")
            raise ValueError("ElevenLabs API key is not set.")

        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                # 1. Send the initial connection message with better voice settings
                connection_setup_message = {
                    "text": " ",
                    "voice_settings": {
                        "stability": 0.5, 
                        "similarity_boost": 0.8,
                        "style": 0.0,
                        "use_speaker_boost": True
                    },
                    "xi_api_key": ELEVENLABS_API_KEY,
                    "output_format": "ulaw_8000"  # Correct format for Twilio
                }
                await websocket.send(json.dumps(connection_setup_message))
                logger.info("Connected to ElevenLabs with ulaw_8000 format")

                # 2. Asynchronously send text to ElevenLabs
                async def send_text():
                    try:
                        # Send text chunks as they come in
                        async for text_chunk in text_stream:
                            if text_chunk and text_chunk.strip():  # Only send non-empty chunks
                                message = {
                                    "text": text_chunk.strip() + " ",  # Add space for better flow
                                    "try_trigger_generation": True
                                }
                                await websocket.send(json.dumps(message))
                                logger.debug(f"Sent text chunk to ElevenLabs: '{text_chunk.strip()}'")
                        
                        # Signal end of text
                        await websocket.send(json.dumps({"text": ""}))
                        logger.info("Finished sending text to ElevenLabs.")
                        
                    except Exception as e:
                        logger.error(f"Error sending text to ElevenLabs: {e}")

                # 3. Asynchronously receive audio from ElevenLabs
                async def receive_audio():
                    audio_chunks_received = 0
                    total_audio_size = 0
                    
                    try:
                        while True:
                            message_str = await websocket.recv()
                            message = json.loads(message_str)
                            
                            # Handle audio data
                            if audio_data := message.get("audio"):
                                audio_chunk = base64.b64decode(audio_data)
                                audio_chunks_received += 1
                                total_audio_size += len(audio_chunk)
                                
                                # Log every 10th chunk to track progress
                                if audio_chunks_received % 10 == 0:
                                    logger.info(f"Received {audio_chunks_received} audio chunks from ElevenLabs, total: {total_audio_size} bytes")
                                
                                yield audio_chunk
                            
                            # Check for completion
                            if message.get('isFinal'):
                                logger.info(f"ElevenLabs finished. Total audio chunks: {audio_chunks_received}, total size: {total_audio_size} bytes")
                                break
                                
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("ElevenLabs connection closed during receive.")
                    except Exception as e:
                        logger.error(f"Error receiving audio from ElevenLabs: {e}")
                
                # Run both tasks concurrently
                send_task = asyncio.create_task(send_text())
                
                audio_yielded = 0
                async for audio_chunk in receive_audio():
                    audio_yielded += 1
                    yield audio_chunk

                logger.info(f"Total audio chunks yielded: {audio_yielded}")
                await send_task  # Ensure the send task is complete

        except Exception as e:
            logger.error(f"Error in TTS streaming: {e}")
            raise CustomException("Failed to stream TTS audio", e)