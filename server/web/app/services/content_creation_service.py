import openai

class ContentCreationService:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    def generate_caption(self, text: str) -> str:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Generate a witty caption for the following text:\n\n{text}",
            max_tokens=50
        )
        return response.choices[0].text.strip()

    def rewrite_text(self, text: str) -> str:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Rewrite the following text in a more engaging way:\n\n{text}",
            max_tokens=len(text.split()) + 50
        )
        return response.choices[0].text.strip()

