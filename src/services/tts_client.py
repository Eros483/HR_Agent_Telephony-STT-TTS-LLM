# ----- setup of TTS client @src/services/tts_client.py -----

import asyncio
import os
import websockets
import base64
import json
from src.core.config import settings
from utils.logger import get_logger
from utils.custom_exception import CustomException

logger=get_logger(__name__)

ELEVENLABS_API_KEY=settings.ELEVENLABS_API_KEY

ELEVENLABS_VOICE_ID="P7vsEyTOpZ6YUTulin8m"
WEB_SOCKET_URL=f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream-input?model_id=eleven_turbo_v2"

class TextToSpeechClient:
    """
    Handles streaming LLM output, conversion to speech via ElevenLabs' Websocket API to be connected to Twilio
    """
    async def stream_audio(self, text_stream):
        """
        Args:
            text_stream: LLM yielded async text chunk generator

        Yields:
            bytes: Chunks of audio data in twilio compatible format
        """  
        if not ELEVENLABS_API_KEY:
            logger.error("ELEVENLABS API KEY UNAVAILABLE")
            raise ValueError("ELEVENLABS API KEY UNAVAILABLE")
        
        try:
            async with websockets.connect(WEB_SOCKET_URL) as websocket:
                connection_setup_message={
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                    "xi_api_key": ELEVENLABS_API_KEY,
                    "output_format": "ulaw_8000"
                }
                await websocket.send(json.dumps(connection_setup_message))

                async def send_text():
                    async for text_chunk in text_stream:
                        message={"text": text_chunk, "try_trigger_generation": True}
                        await websocket.send(json.dumps(message))
                    await websocket.send(json.dumps({"text": " ", "end_of_stream": True}))

                async def receive_audio():
                    while True:
                        try:
                            message_str = await websocket.recv()
                            message = json.loads(message_str)
                            
                            if message.get("audio"):
                                audio_chunk = base64.b64decode(message["audio"])
                                yield audio_chunk
                            
                            if message.get('isFinal'):
                                break
                        except websockets.exceptions.ConnectionClosed:
                            logger.info("ElevenLabs connection closed.")
                            break 

                send_task=asyncio.create_task(send_text())

                async for audio_chunk in receive_audio():
                    yield audio_chunk

                await send_task

        except Exception as e:
            logger.error(f"Error in ElevenLabs TTS streaming: {e}")
            raise CustomException("Failed to stream audio from ElevenLabs", e)
        
async def main():
    """Main function to run a test of the TTS client."""
    print("--- Testing ElevenLabs TTS Client ---")
    
    tts_client = TextToSpeechClient()

    #dummy text generator
    async def text_generator():
        text = "Hello, this is a test of the real-time text to speech system."
        for word in text.split():
            yield word + " "
            await asyncio.sleep(0.1)

    try:
        print("Testing audio stream data reception")
        audio_chunks_received = 0
        async for audio_chunk in tts_client.stream_audio(text_generator()):
            audio_chunks_received += 1
            if audio_chunks_received % 10 == 0:
                print(f"Received {audio_chunks_received} audio chunks...")
        
        print(f"\n✅ TTS stream test complete. Received a total of {audio_chunks_received} audio chunks.")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")

if __name__ == "__main__":
    if not ELEVENLABS_API_KEY:
        print("Please set your ELEVENLABS_API_KEY in a .env file to run this test.")
    else:
        asyncio.run(main())
