# ----- FastAPI backend for linking together clients @ src/main.py -----
import base64
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Connect
import asyncio

from src.core.config import settings
from utils.logger import get_logger
from utils.custom_exception import CustomException

from src.services.llm_client import get_llm_response
from src.prompt_templates.calling_agent import get_system_prompt, get_question_list
from src.services.stt_client import SpeechToTextClient
from src.services.tts_client import TextToSpeechClient

from src.workers.tasks import initiate_call_task

app = FastAPI()
logger = get_logger(__name__)

active_calls={}

#API endpoints

@app.on_event("startup")
async def validate_config():
    """Validate all required configuration on startup"""
    required_settings = [
        'DEEPGRAM_API_KEY',
        'ELEVENLABS_API_KEY', 
        'VLLM_API_BASE',
        'LLM_MODEL_NAME',
        'TWILIO_API_KEY_SID',
        'TWILIO_API_KEY_SECRET',
        'TWILIO_PHONE_NUMBER',
        'NGROK_URL'
    ]
    
    for setting in required_settings:
        value = getattr(settings, setting, None)
        if not value:
            logger.error(f"Missing required setting: {setting}")
        else:
            logger.info(f"✓ {setting} is configured")
    
    # Test vLLM connection
    try:
        logger.info("Testing vLLM connection...")
        # Add a simple test call here
    except Exception as e:
        logger.error(f"vLLM connection test failed: {e}")

@app.post("/start-interview/{phone_number}")
async def start_interview(phone_number: str):
    """
    API endpoint to trigger a new interview call
    It creates a background task to initiate the call

    Args:
        phone_number: The number to be called
    """
    try:
        logger.info(f"Starting interview for {phone_number}")
        if not phone_number.startswith("+"):
            return {"status": "error", "message": "Phone number must be in E.164 format (e.g., +14155552671)"}

        call_id=str(uuid.uuid4())
        logger.info(f"Initiaing interview call to {phone_number} with call_id: {call_id}")

        initiate_call_task.delay(phone_number, call_id)
        return {"status": "success", "message": "Interview started successfully", "call_id": call_id}

    except Exception as e:
        logger.error(f"Failed to start interview for {phone_number}: {e}")
        raise CustomException("Failed to start interview", e)
    

@app.post("/twilio-voice-webhook/{call_id}")
async def twilio_voice_webhook(call_id: str, request: Request):
    """
    Webhook that provides TwiML instructions to Twilio when a call connects.
    This tells Twilio to open a bidirectional audio stream to our WebSocket server.
    """
    logger.info(f"Received Twilio voice webhook for call_id: {call_id}")
    response = VoiceResponse()
    connect = Connect()
    
    # The wss:// URL must point to our public ngrok address
    hostname = settings.NGROK_URL.split("://")[1]
    websocket_url = f"wss://{hostname}/ws/{call_id}"
    connect.stream(url=websocket_url)
    response.append(connect)
    
    logger.info(f"Responding with TwiML to stream audio to: {websocket_url}")
    return Response(content=str(response), media_type="text/xml")

@app.websocket("/ws/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    """
    The main WebSocket endpoint for handling the live, bidirectional audio stream.
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for call_id: {call_id}")

    conversation_history = []
    stt_client = None
    tts_client = TextToSpeechClient()
    stream_sid = None  # Track the stream SID

    try:
        # This function will be the callback for the STT client.
        # It gets triggered when a final transcript is ready.
        async def on_final_transcript(transcript: str):
            nonlocal conversation_history, stream_sid
            logger.info(f"Handling final transcript for call {call_id}: '{transcript}'")
            conversation_history.append({"role": "user", "content": transcript})

            try:
                candidate_details = "John Doe, SDE-2 Applicant"
                questions = get_question_list()
                end_phrase = "END_OF_CALL"
                system_prompt = get_system_prompt(candidate_details, questions, end_phrase)
                llm_stream = get_llm_response(conversation_history, system_prompt, end_phrase)
                
                logger.info("Starting TTS audio generation...")
                audio_stream = tts_client.stream_audio(llm_stream)

                await send_audio_to_twilio(audio_stream, stream_sid, websocket, call_id)
                
            except Exception as e:
                logger.error(f"Error during LLM/TTS processing for call {call_id}: {e}")

        async def send_audio_to_twilio(audio_stream, stream_sid, websocket, call_id):
            """Helper function to send audio to Twilio with proper error handling"""
            if not stream_sid:
                logger.error("Cannot send audio: stream_sid is None")
                return
                
            audio_chunks_sent = 0
            total_audio_size = 0
            
            try:
                async for audio_chunk in audio_stream:
                    if audio_chunk and len(audio_chunk) > 0:  # Ensure non-empty audio
                        audio_chunks_sent += 1
                        total_audio_size += len(audio_chunk)
                        
                        # Create the media message for Twilio
                        media_message = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": base64.b64encode(audio_chunk).decode("utf-8")
                            }
                        }
                        
                        # Send to Twilio
                        await websocket.send_text(json.dumps(media_message))
                        
                        # Log progress every 20 chunks to avoid spam
                        if audio_chunks_sent % 20 == 0:
                            logger.info(f"[{call_id}] Sent {audio_chunks_sent} audio chunks to Twilio, total size: {total_audio_size} bytes")
                        
                        # Small delay to prevent overwhelming Twilio
                        if audio_chunks_sent % 5 == 0:
                            await asyncio.sleep(0.001)  # 1ms delay every 5 chunks
                
                logger.info(f"[{call_id}] Finished sending audio to Twilio. Total chunks: {audio_chunks_sent}, total size: {total_audio_size} bytes")
                
            except Exception as e:
                logger.error(f"Error sending audio to Twilio for call {call_id}: {e}")

        # Main loop to process incoming messages from the Twilio WebSocket
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data['event'] == 'start':
                # IMPORTANT: Capture the stream SID from Twilio
                stream_sid = data['start']['streamSid']
                logger.info(f"Twilio stream started for call {call_id} with streamSid: {stream_sid}")
                
                # Send an initial greeting from the AI FIRST
                logger.info("Sending initial greeting...")
                candidate_details = "John Doe, SDE-2 Applicant"
                questions = get_question_list()
                end_phrase = "END_OF_CALL"
                system_prompt = get_system_prompt(candidate_details, questions, end_phrase)
                
                # Start with an empty history to get the AI's introduction
                llm_stream = get_llm_response([], system_prompt, end_phrase)
                audio_stream = tts_client.stream_audio(llm_stream)
                
                await send_audio_to_twilio(audio_stream, stream_sid, websocket, call_id)
                logger.info("Initial greeting sent successfully")
                
                # Small delay before starting STT to ensure greeting is processed
                await asyncio.sleep(0.5)
                
                # NOW initialize the STT client AFTER the greeting is sent
                logger.info("Initializing STT client after greeting.")
                stt_client = SpeechToTextClient(on_message_callback=on_final_transcript)
                stt_success = await stt_client.start()
                if stt_success:
                    active_calls[call_id] = stt_client
                    logger.info("STT client successfully initialized and started")
                else:
                    logger.error("Failed to initialize STT client")

            elif data['event'] == 'media':
                # Only process media if the STT client has been initialized
                if stt_client:
                    try:
                        payload = data['media']['payload']
                        audio_chunk = base64.b64decode(payload)
                        await stt_client.send_audio(audio_chunk)
                    except Exception as e:
                        logger.warning(f"Error sending audio to STT client: {e}")

            elif data['event'] == 'stop':
                logger.info(f"Twilio stream stopped for call {call_id}")
                break

    except WebSocketDisconnect:
        logger.warning(f"WebSocket disconnected for call {call_id}")
    except Exception as e:
        logger.error(f"An error occurred in WebSocket for call {call_id}: {e}")
    finally:
        logger.info(f"Cleaning up resources for call {call_id}")
        if call_id in active_calls:
            stt_client = active_calls.pop(call_id)
            if stt_client:
                await stt_client.finish()