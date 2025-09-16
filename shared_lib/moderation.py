# shared_lib/moderation.py

def moderate_prompt(prompt: str) -> bool:
    """
    A simple content moderation filter.
    Returns True if the prompt is clean, False otherwise.
    """
    banned_words = ["badword1", "badword2"]
    for word in banned_words:
        if word in prompt.lower():
            return False
    return True
