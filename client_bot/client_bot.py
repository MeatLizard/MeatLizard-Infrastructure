"""
Main discord.py bot for the client-side inference engine.
"""
import discord
from discord.ext import commands
import os
import json
import uuid
from shared_lib.crypto import AESCipher
from llama_cpp_wrapper import LlamaCppWrapper

# Load from a secure config
PAYLOAD_SECRET_KEY = os.getenv("PAYLOAD_SECRET_KEY").encode()
INFERENCE_CHANNEL_ID = int(os.getenv("INFERENCE_CHANNEL_ID"))
RESPONSE_CHANNEL_ID = int(os.getenv("RESPONSE_CHANNEL_ID"))
LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
cipher = AESCipher(key=PAYLOAD_SECRET_KEY)
llama_wrapper = LlamaCppWrapper(model_path=LLAMA_MODEL_PATH)

@bot.event
async def on_ready():
    print(f'Client-Bot logged in as {bot.user}')
    bot.inference_channel = bot.get_channel(INFERENCE_CHANNEL_ID)
    bot.response_channel = bot.get_channel(RESPONSE_CHANNEL_ID)
    if not bot.inference_channel or not bot.response_channel:
        print("Error: Could not find inference or response channels.")

@bot.listen()
async def on_message(message):
    if message.channel.id == INFERENCE_CHANNEL_ID and message.author != bot.user:
        try:
            encrypted_data = json.loads(message.content)
            decrypted_payload = cipher.decrypt(encrypted_data)
            request_data = json.loads(decrypted_payload)
            
            prompt = request_data.get("prompt")
            print(f"Received inference request {request_data.get('request_id')}")

            # Perform inference
            response_text = llama_wrapper.generate(prompt)

            if response_text:
                response_payload = {
                    "request_id": request_data.get("request_id"),
                    "session_id": request_data.get("session_id"),
                    "response": response_text,
                    "status": "success",
                    "metrics": {"tokens_per_sec": 0} # Placeholder
                }
            else:
                raise ValueError("Inference returned no text.")

        except Exception as e:
            print(f"Error processing inference request: {e}")
            response_payload = {
                "request_id": request_data.get("request_id"),
                "session_id": request_data.get("session_id"),
                "error_code": "inference_failed",
                "error_message": str(e)
            }

        # Send response
        encrypted_response = cipher.encrypt(json.dumps(response_payload))
        await bot.response_channel.send(json.dumps(encrypted_response))

def run():
    bot.run(os.getenv("CLIENT_DISCORD_TOKEN"))

if __name__ == "__main__":
    run()
