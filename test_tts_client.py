# ----- Test script for src/services/tts_client.py -----

import asyncio
import os
import wave
from dotenv import load_dotenv

# We need to import the client we want to test
from src.services.tts_client import TextToSpeechClient
# Import the module itself to access its constants
import src.services.tts_client as tts_client_module
from utils.logger import get_logger

# --- Setup ---
load_dotenv()
logger = get_logger(__name__)

# --- Main Test Function ---
async def main():
    """
    Main function to run an isolated test of the TextToSpeechClient.
    It streams audio from ElevenLabs and saves it to a local .wav file.
    """
    logger.info("--- Starting TTS Client Test ---")
    
    # Ensure the API key is available
    if not os.getenv("ELEVENLABS_API_KEY"):
        logger.error("ELEVENLABS_API_KEY not set in .env file. Aborting test.")
        return

    tts_client = TextToSpeechClient()

    # A simple async generator to simulate the LLM's text stream
    async def text_generator():
        text = "Hello, this is a test of the real-time text to speech system. If you can hear this clearly, then the audio generation is working correctly."
        for word in text.split():
            yield word + " "
            await asyncio.sleep(0.1)

    # Store the original URL so we can restore it later
    original_url = tts_client_module.WEBSOCKET_URL
    
    try:
        logger.info("Requesting audio stream from ElevenLabs...")
        audio_chunks = []
        
        # For this test, we temporarily override the module's URL constant 
        # to request playable PCM audio instead of µ-law.
        tts_client_module.WEBSOCKET_URL = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{tts_client_module.ELEVENLABS_VOICE_ID}"
            f"/stream-input?model_id=eleven_turbo_v2&output_format=pcm_16000"
        )

        # Collect all audio chunks from the stream
        async for chunk in tts_client.stream_audio(text_generator()):
            if chunk:
                audio_chunks.append(chunk)

        if not audio_chunks:
            logger.error("Test failed: No audio chunks were received from ElevenLabs.")
            return

        logger.info(f"Stream finished. Received {len(audio_chunks)} audio chunks.")
        
        # --- Save the audio to a .wav file ---
        # The audio is now in uncompressed PCM format, which the wave library supports.
        output_filename = "tts_output.wav"
        logger.info(f"Saving received audio to '{output_filename}'...")

        with wave.open(output_filename, 'wb') as wf:
            wf.setnchannels(1)      # Mono
            wf.setsampwidth(2)      # 16-bit PCM = 2 bytes
            wf.setframerate(16000)  # 16000Hz sample rate
            
            # Join all the chunks and write them to the file
            wf.writeframes(b''.join(audio_chunks))

        logger.info(f"✅ Test successful! Audio saved to '{output_filename}'.")
        print(f"\nPlease play the '{output_filename}' file to check the audio quality.")

    except Exception as e:
        logger.error(f"An error occurred during the TTS test: {e}")
        print(f"\n❌ Test Failed: {e}")
    finally:
        # Restore the original URL to avoid side effects
        tts_client_module.WEBSOCKET_URL = original_url
        logger.info("Restored original WebSocket URL.")


if __name__ == "__main__":
    asyncio.run(main())