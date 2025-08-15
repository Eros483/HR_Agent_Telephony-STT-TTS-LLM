# ----- handles llm client @src/services/llm_client.py -----

import openai
from src.core.config import settings
from utils.custom_exception import CustomException
from utils.logger import get_logger
from src.prompt_templates.calling_agent import get_system_prompt, get_question_list
import asyncio

logger=get_logger(__name__)

llm_client=openai.AsyncOpenAI(
    base_url=settings.VLLM_API_BASE,
    api_key="not needed"
)
logger.info("Initialised llm_client")

async def get_llm_response(conversation_history: list, system_prompt: dict, end_of_call_phrase: str, temperature: float=0.7, max_tokens: int=150):
    """
    Get response from the LLM using the provided messages.

    Args:
        conversation_history: List of messages from user and LLM.
        system_prompt: System prompt template to control LLM responses.
        end_of_call_phrase: The phrase to use as a stop sequence
        temperature: The temperature setting for response variability
        max_tokens: Maximum output length of LLM response

    Returns:
        str: The response from the llm
    """
    try:
        logger.info(f"Generating LLM response with {len(conversation_history)} messages")
        logger.info(f"vLLM base URL: {settings.VLLM_API_BASE}")
        logger.info(f"Model name: {settings.LLM_MODEL_NAME}")

        messages_to_send = [system_prompt] + conversation_history
        logger.info(f"Messages to send: {messages_to_send}")
        logger.info(f"Sending {len(messages_to_send)} messages to LLM")

        # ADD: Test connection first
        try:
            stream = await llm_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=messages_to_send,
                stream=True,
                stop=["\n", end_of_call_phrase],
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.info("Successfully created LLM stream")
        except Exception as e:
            logger.error(f"Failed to create LLM stream: {e}")
            raise

        chunk_count = 0
        async for chunk in stream:
            chunk_count += 1
            content = chunk.choices[0].delta.content
            if content:
                logger.debug(f"LLM chunk {chunk_count}: {repr(content[:50])}")
                logger.info(f"LLM chunk {chunk_count}: {content}")
                yield content

        logger.info(f"LLM stream finished with {chunk_count} chunks")
    
    except Exception as e:
        logger.error(f"LLM response generation failed: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        raise CustomException("failed to generate llm response", e)

async def main():
    """Main function to run a test of the LLM client."""

    candidate_details = "John Doe, 5 years experience, applying for SDE-2 role"
    questions = get_question_list()
    end_phrase = "END_OF_CALL"
    system_prompt = get_system_prompt(candidate_details, questions, end_phrase)

    conversation_history = []

    logger.info("Starting LLM stream test...")
    logger.info(f"System Prompt: {system_prompt['content']}")
    logger.info("--- Starting Simulated Conversation ---")

    try:
        logger.info("AI: ")
        ai_response = ""
        async for chunk in get_llm_response(conversation_history, system_prompt, end_phrase):
            print(chunk, end="", flush=True)
            logger.info(chunk)
            ai_response += chunk

        conversation_history.append({"role": "assistant", "content": ai_response})
        print("\n")

        # --- Turn 2: User Response ---
        user_reply = "Hi Alex, thanks for the call. Yes, now is a good time."
        print(f"User: {user_reply}\n")
        conversation_history.append({"role": "user", "content": user_reply})

        # --- Turn 3: AI Asks First Question ---
        print("AI: ", end="", flush=True)
        ai_response = ""
        async for chunk in get_llm_response(conversation_history, system_prompt, end_phrase):
            print(chunk, end="", flush=True)
            ai_response += chunk
        conversation_history.append({"role": "assistant", "content": ai_response})
        print("\n")
        logger.info("Final Conversation:")
        logger.info(conversation_history)

    except CustomException as e:
        logger.error(f"Stream test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())