# server/server_bot/bot.py
import discord
from discord import app_commands, SelectOption, ui
from discord.ext import commands
import os
import asyncio
import json
import io
import uuid
import subprocess
from shared_lib.crypto import get_encryptor
from shared_lib.s3 import get_s3_client
from shared_lib.gdpr import anonymize_user_data
from shared_lib.metrics import ClientBotMetrics
from shared_lib.db import get_db_session, Metric
from shared_lib.transcripts import generate_csv_transcript

# Import for database session factory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "web"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.db_session_factory = None

    async def setup_hook(self):
        # Setup database session factory
        await self._setup_database()
        
        # Load cogs
        await self._load_cogs()
        
        # Sync commands
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
    
    async def _setup_database(self):
        """Setup database connection and session factory"""
        database_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://test:test@localhost:5432/test')
        
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True
        )
        
        self.db_session_factory = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def _load_cogs(self):
        """Load bot cogs"""
        try:
            # Load media import cog
            await self.load_extension('cogs.media_import')
            print("Loaded media import cog")
        except Exception as e:
            print(f"Failed to load media import cog: {e}")

bot = MyBot(command_prefix="!", intents=intents)
message_queue = None
response_queues = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(process_message_queue())

async def process_message_queue():
    global message_queue
    while True:
        if message_queue:
            message = await message_queue.get()
            if message["action"] == "create_session":
                guild = bot.get_guild(int(os.getenv("DISCORD_GUILD_ID")))
                session_id = message["session_id"]
                channel_name = f"session-{session_id}"
                category_name = os.getenv("CHAT_CATEGORY_NAME", "AI Chat Sessions")
                category = discord.utils.get(guild.categories, name=category_name)
                if not category:
                    category = await guild.create_category(category_name)
                channel = await guild.create_text_channel(
                    channel_name, category=category
                )
                print(f"Created channel {channel.name} for session {session_id}")
            elif message["action"] == "send_message":
                session_id = message["session_id"]
                encrypted_prompt = message["prompt"]
                channel_name = f"session-{session_id}"
                channel = discord.utils.get(
                    bot.get_all_channels(), name=channel_name
                )
                if channel:
                    await channel.send(encrypted_prompt)
        else:
            await asyncio.sleep(1)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.name.startswith("session-"):
        session_id = message.channel.name.split("-")[1]
        if session_id in response_queues:
            encryptor = get_encryptor()
            decrypted_response = encryptor.decrypt(message.content)
            await response_queues[session_id].put(decrypted_response)
    elif message.channel.name == "ai-metrics" and message.author != bot.user:
        db = get_db_session()
        encryptor = get_encryptor()
        decrypted_metrics = encryptor.decrypt(message.content)
        metrics = ClientBotMetrics.parse_raw(decrypted_metrics)
        db_metric = Metric(
            client_bot_id=message.author.id,
            metric_type="client_bot_metrics",
            metric_data=metrics.dict()
        )
        db.add(db_metric)
        db.commit()
        print(f"Stored metrics from {message.author.name}")
    await bot.process_commands(message)

@bot.tree.command(name="start", description="Start a new AI chat session.")
async def start(interaction: discord.Interaction):
    session_id = uuid.uuid4()
    guild = interaction.guild
    channel_name = f"session-{session_id}"
    category_name = os.getenv("CHAT_CATEGORY_NAME", "AI Chat Sessions")
    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        category = await guild.create_category(category_name)
    channel = await guild.create_text_channel(
        channel_name,
        category=category,
        overwrites={
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True),
        },
    )
    await interaction.response.send_message(f"Session started in {channel.mention}", ephemeral=True)

@bot.tree.command(name="set_system", description="Set the system prompt for the current session.")
@app_commands.describe(prompt="The system prompt to use.")
async def set_system(interaction: discord.Interaction, prompt: str):
    if interaction.channel.name.startswith("session-"):
        # In a real app, you would store this in the database
        await interaction.response.send_message(f"System prompt set to: {prompt}", ephemeral=True)
    else:
        await interaction.response.send_message("This command can only be used in a session channel.", ephemeral=True)

@bot.tree.command(name="set_temp", description="Set the temperature for the current session.")
@app_commands.describe(temperature="The temperature to use (0.0-1.0).")
async def set_temp(interaction: discord.Interaction, temperature: float):
    if interaction.channel.name.startswith("session-"):
        # In a real app, you would store this in the database
        await interaction.response.send_message(f"Temperature set to: {temperature}", ephemeral=True)
    else:
        await interaction.response.send_message("This command can only be used in a session channel.", ephemeral=True)

@bot.tree.command(name="prompt", description="Select a prompt from the library.")
async def prompt(interaction: discord.Interaction):
    with open("docs/PROMPT_LIBRARY.md", "r") as f:
        prompts = f.read().split("\n\n")
    
    options = []
    for p in prompts:
        if p.startswith("-"):
            name = p.split('"')[1]
            options.append(SelectOption(label=name, value=name))

    select = ui.Select(
        placeholder="Choose a prompt...",
        options=options,
        custom_id="prompt_select"
    )
    
    async def select_callback(interaction: discord.Interaction):
        # In a real app, you would set the system prompt for the session
        await interaction.response.send_message(
            f"Prompt set to: {select.values[0]}",
            ephemeral=True
        )

    select.callback = select_callback
    view = ui.View()
    view.add_item(select)
    await interaction.response.send_message(
        "Select a prompt:",
        view=view,
        ephemeral=True
    )

@bot.tree.command(name="end", description="End the current AI chat session.")
async def end(interaction: discord.Interaction):
    if interaction.channel.name.startswith("session-"):
        session_id = interaction.channel.name.split("-")[1]
        messages = []
        async for message in interaction.channel.history(limit=None):
            messages.append({
                "author": message.author.name,
                "content": message.content,
                "timestamp": message.created_at.isoformat()
            })
        
        # Save JSON transcript to S3
        transcript_json = json.dumps(messages, indent=4)
        s3_client = get_s3_client()
        s3_client.upload_fileobj(
            io.BytesIO(transcript_json.encode("utf-8")),
            s3_client.bucket_name,
            f"transcripts/{session_id}.json"
        )

        # Generate CSV transcript and DM to user
        transcript_csv = generate_csv_transcript(messages)
        await interaction.user.send(
            "Here is your transcript:",
            file=discord.File(io.StringIO(transcript_csv), f"{session_id}.csv")
        )

        await interaction.channel.delete()
        print(f"Closed session {session_id} and saved transcript to S3")

@bot.tree.command(name="gdpr_anonymize", description="Anonymize your user data.")
async def gdpr_anonymize(interaction: discord.Interaction):
    anonymize_user_data(interaction.user.id)
    await interaction.response.send_message("Your data has been anonymized.", ephemeral=True)

@bot.tree.command(name="backup", description="Create a backup of the database.")
@app_commands.checks.has_permissions(administrator=True)
async def backup(interaction: discord.Interaction):
    db_url = os.getenv("DATABASE_URL")
    db_name = db_url.split("/")[-1]
    backup_file = f"/tmp/{db_name}-{datetime.utcnow().isoformat()}.sql"
    
    process = await asyncio.create_subprocess_shell(
        f"pg_dump {db_url} > {backup_file}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        s3_client = get_s3_client()
        s3_client.upload_file(
            file_path=backup_file,
            object_name=f"backups/{os.path.basename(backup_file)}"
        )
        await interaction.response.send_message("Backup created and uploaded to S3.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Backup failed: {stderr.decode()}", ephemeral=True)

def run_bot_with_queue(queue, res_queues, token):
    global message_queue, response_queues
    message_queue = queue
    response_queues = res_queues
    bot.run(token)
