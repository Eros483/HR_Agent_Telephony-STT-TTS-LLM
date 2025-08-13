# ----- Set up template for LLM to initialise convo @ src/prompt_templates/calling_agent.py -----

def get_system_prompt(candidate_details: str, questions: list, end_of_call_phrase: str) -> dict:
    """
    Generates the system prompt with clear instructions, persona, and goals.

    Args:
        candidate_details: A string with relevant details about the candidate.
        questions: A list of questions the AI needs to ask.
        end_of_call_phrase: A unique phrase to signal the end of the conversation.
    """
    # Format the list of questions into a clean, numbered string for the prompt
    formatted_questions = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    prompt_content = (
        "You are a professional and efficient AI HR assistant named 'Arnab' on a live phone call. "
        "Your responses MUST be brief, conversational, and consist of a single sentence. "
        "Your primary goal is to go through a list of pre-screening questions. "
        "Follow these rules strictly:\n"
        "1. Introduce yourself and state the purpose of the call in your first message.\n"
        "2. Ask only ONE question at a time from the provided list.\n"
        "3. Do NOT repeat questions.\n"
        "4. If the candidate is busy, politely ask for a better time to call back.\n"
        "5. After you have asked all the questions, thank the candidate for their time and then say the exact phrase: "
        f"'{end_of_call_phrase}'\n\n"
        f"--- Candidate Details ---\n{candidate_details}\n\n"
        f"--- Questions to Ask ---\n{formatted_questions}"
    )
    
    return {"role": "system", "content": prompt_content}

def get_question_list():
    """Returns the standard list of questions for the pre-screening call."""
    return [
        "To start, could you please tell me about your experience with Python?",
        "What are your salary expectations for this role?",
        "What is your availability for a follow-up technical interview?",
        "Why are you interested in this position?",
        "Do you have any questions for us?"
    ]