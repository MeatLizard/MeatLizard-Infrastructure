import discord
from discord import app_commands
from discord.ext import commands
from server.shared_lib.config import settings
from server.shared_lib.crypto import encryptor
import uuid
import time

class SessionManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client_bot_user = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Cache the client bot user object when ready."""
        self.client_bot_user = await self.bot.fetch_user(settings.CLIENT_BOT_ID)
        if not self.client_bot_user:
            print(f"ERROR: Could not find client bot with ID {settings.CLIENT_BOT_ID}")
        else:
            print(f"Successfully found client bot: {self.client_bot_user.name}")

    @app_commands.command(name="ai", description="Start a new AI chat session.")
    async def start_session(self, interaction: discord.Interaction):
        """Starts a new private AI session for a user."""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        # Create a private channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add admin role if configured
        admin_role = discord.utils.get(guild.roles, name=settings.ADMIN_ROLE_NAME)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True)

        try:
            channel_name = f"ai-session-{user.name[:10]}-{uuid.uuid4().hex[:6]}"
            channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
            await interaction.followup.send(f"Your private session has been created: {channel.mention}", ephemeral=True)
            await channel.send(f"Welcome, {user.mention}! Your AI session is ready. Type your messages here.")
        except discord.Forbidden:
            await interaction.followup.send("I don't have permissions to create a private channel.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for messages and relays them to the client bot."""
        # Ignore messages from bots (including self) and not in a session channel
        if message.author.bot or not message.channel.name.startswith("ai-session-"):
            return

        # Ensure the client bot is available
        if not self.client_bot_user:
            await message.channel.send("Sorry, the AI client is not connected. Please try again later.")
            return
            
        async with message.channel.typing():
            # Construct the payload
            payload = {
                "type": "generate_request",
                "session_id": str(uuid.uuid4()), # This should come from a DB in the full version
                "prompt": [{"role": "user", "content": message.content}],
                "generation": {"max_tokens": 512, "temp": 0.7},
                "meta": {"requested_at": time.time(), "request_id": str(uuid.uuid4())}
            }
            
            encrypted_payload = encryptor.encrypt(payload)
            
            # Send to the dedicated comms channel
            comms_channel = self.bot.get_channel(settings.COMMS_CHANNEL_ID)
            if not comms_channel:
                print(f"ERROR: Comms channel {settings.COMMS_CHANNEL_ID} not found!")
                await message.channel.send("System configuration error: communication channel not found.")
                return

            await comms_channel.send(f"Request from {message.channel.id}\n{encrypted_payload}")
            print(f"Relayed request from channel {message.channel.id} to client bot.")

            # TODO: Add logic here to wait for the client bot's response in the comms channel
            # and then post it back to `message.channel`. This requires a more complex
            # request/response tracking system, likely using Redis. For now, this just sends.


async def setup(bot: commands.Bot):
    await bot.add_cog(SessionManager(bot))
