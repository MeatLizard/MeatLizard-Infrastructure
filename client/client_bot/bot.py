# client/client_bot/bot.py
import discord
from discord import app_commands
from discord.ext import commands
import os
import subprocess
from shared_lib.crypto import get_encryptor
from shared_lib.models import LlamaModel
from datetime import datetime
from shared_lib.metrics import ClientBotMetrics, GpuStats
import asyncio
import json

intents = discord.Intents.default()
intents.messages = True

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

bot = MyBot(command_prefix="!", intents=intents)
encryptor = get_encryptor()

class LlamaCPP:
    def __init__(self):
        self.models = {
            "vicuna": LlamaModel(
                name="vicuna",
                path="/path/to/your/vicuna.gguf",
                description="A chat-tuned model from LMSYS.",
            ),
            "llama2": LlamaModel(
                name="llama2",
                path="/path/to/your/llama2.gguf",
                description="A foundational model from Meta.",
            ),
        }
        self.current_model = self.models["vicuna"]

    def get_response(self, prompt):
        # In a real app, you would use the llama.cpp Python bindings
        # For now, we'll just echo
        return f"{self.current_model.name} says: {prompt}"

llama_cpp = LlamaCPP()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(send_metrics())

async def send_metrics():
    await bot.wait_until_ready()
    channel = bot.get_channel(int(os.getenv("METRICS_CHANNEL_ID")))
    while not bot.is_closed():
        # In a real app, you would collect actual GPU stats here
        gpu_stats = GpuStats(
            utilization=0.5,
            memory_free=8192,
            memory_used=8192,
            temperature=60.0,
        )
        metrics = ClientBotMetrics(
            timestamp=datetime.utcnow(),
            gpu_stats=gpu_stats,
            tokens_per_second=10.0,
            is_online=True,
        )
        encrypted_metrics = encryptor.encrypt(metrics.json())
        await channel.send(encrypted_metrics)
        await asyncio.sleep(60)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.name.startswith("session-"):
        decrypted_prompt = encryptor.decrypt(message.content)
        response = llama_cpp.get_response(decrypted_prompt)
        encrypted_response = encryptor.encrypt(response)
        await message.channel.send(encrypted_response)
    await bot.process_commands(message)

@bot.tree.command(name="set_model", description="Set the active LLM model.")
@app_commands.describe(model_name="The name of the model to use.")
async def set_model(interaction: discord.Interaction, model_name: str):
    if model_name in llama_cpp.models:
        llama_cpp.current_model = llama_cpp.models[model_name]
        await interaction.response.send_message(f"Model set to {model_name}", ephemeral=True)
    else:
        await interaction.response.send_message(f"Model {model_name} not found.", ephemeral=True)

def run():
    bot.run(os.getenv("CLIENT_BOT_TOKEN"))
