import asyncio
import base64
import json
import sys
import websockets
import ssl
from src.core.config import settings
from utils.custom_exception import CustomException
from utils.logger import get_logger

logger = get_logger(__name__)

def sts_connect():
    """
    Estabilishes websocket connection
    """
    try:
        api_key = settings.DEEPGRAM_API_KEY
        if not api_key:
            logger.error("DEEPGRAM_API_KEY environment variable is not set")
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

        sts_ws = websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            subprotocols=["token", api_key]
        )
        logger.info("Connected to Deepgram STS")
        return sts_ws

    except Exception as e:
        logger.error(f"CustomException: {e}")
        raise CustomException("Failed to connect to deepgram", e)

def load_config():
    """
    Load deepgram configuration from src/config.json
    """
    try:
        with open("src/config.json", "r") as f:
            return json.load(f)

    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise CustomException("Failed to load config", e)

async def handle_barge_in(decoded, twilio_ws, streamsid):
    """
    Handles user barge-in events
    """
    try:
        if decoded["type"] == "UserStartedSpeaking":
            clear_message = {
                "event": "clear",
                "streamSid": streamsid
            }
            await twilio_ws.send(json.dumps(clear_message))
    except Exception as e:
        logger.error(f"Error handling barge-in: {e}")
        raise CustomException("Failed to handle barge-in", e)

async def sts_sender(sts_ws, audio_queue):
    """
    Sends audio chunks to deepgram service
    """
    logger.info("sts_sender started")
    try:
        while True:
            chunk = await audio_queue.get()
            await sts_ws.send(chunk)
    except Exception as e:
        logger.error(f"Error sending audio chunk: {e}")
        raise CustomException("Failed to send audio chunk", e)

async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid):
    await handle_barge_in(decoded, twilio_ws, streamsid)

async def sts_receiver(sts_ws, twilio_ws, streamsid_queue):
    """
    Receives message from deepgram and forwards audio
    """
    try:
        logger.info("sts_receiver started")
        streamsid = await streamsid_queue.get()

        async for message in sts_ws:
            if type(message) is str:
                logger.info(f"Received STS message: {message}")
                decoded = json.loads(message)
                await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
                continue

            raw_mulaw = message

            media_message = {
                "event": "media",
                "streamSid": streamsid,
                "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")}
            }

            await twilio_ws.send(json.dumps(media_message))
    except Exception as e:
        logger.error(f"Error in sts_receiver: {e}")
        raise CustomException("Failed in sts_receiver", e)

async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    try:
        BUFFER_SIZE = 20 * 160
        inbuffer = bytearray(b"")

        async for message in twilio_ws:
            try:
                data = json.loads(message)
                event = data["event"]

                if event == "start":
                    logger.info("get our streamsid")
                    start = data["start"]
                    streamsid = start["streamSid"]
                    streamsid_queue.put_nowait(streamsid)
                elif event == "connected":
                    continue
                elif event == "media":
                    media = data["media"]
                    chunk = base64.b64decode(media["payload"])
                    if media["track"] == "inbound":
                        inbuffer.extend(chunk)
                elif event == "stop":
                    break

                while len(inbuffer) >= BUFFER_SIZE:
                    chunk = inbuffer[:BUFFER_SIZE]
                    audio_queue.put_nowait(chunk)
                    inbuffer = inbuffer[BUFFER_SIZE:]
            except:
                break

    except Exception as e:
        logger.error(f"Error in twilio_receiver: {e}")
        raise CustomException("Failed in twilio_receiver", e)

async def twilio_handler(twilio_ws):
    try:
        audio_queue = asyncio.Queue()
        streamsid_queue = asyncio.Queue()

        async with sts_connect() as sts_ws:
            config_message = load_config()
            await sts_ws.send(json.dumps(config_message))

            await asyncio.wait(
                [
                    asyncio.ensure_future(sts_sender(sts_ws, audio_queue)),
                    asyncio.ensure_future(sts_receiver(sts_ws, twilio_ws, streamsid_queue)),
                    asyncio.ensure_future(twilio_receiver(twilio_ws, audio_queue, streamsid_queue)),
                ]
            )

            await twilio_ws.close()

    except Exception as e:
        logger.error(f"Error in twilio_handler: {e}")
        raise CustomException("Failed in twilio_handler", e)

async def main():
    await websockets.serve(twilio_handler, "localhost", 5000)
    logger.info("Started server.")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())