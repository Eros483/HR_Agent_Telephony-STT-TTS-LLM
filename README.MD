# HR_Agent_Telephony-STT-TTS-LLM
Sets up a phone number that can be called, with a pipeline based on Twilio, Ngrok and Deepgram.

Guides to follow and understand:

- [Github Repo](https://github.com/techwithtim/DeepgramVoiceAgent/tree/main)
- [Deepgram Docs](https://developers.deepgram.com/docs/twilio-and-deepgram-voice-agent)

## Installation Instructions
1. Clone repository from [Github](https://github.com/Eros483/HR_Agent_Telephony-STT-TTS-LLM)
2. Setup environment using 
    - `pip install -r requirements.txt` and 
    - `pip install -e .`
3. Setup `.env` file as per specified at `src\core\config.py`.
    - Need Deepgram API key.
    - Need to set up twilio as provided in deepgram docs (linked above).
4. Run `python src/main.py`