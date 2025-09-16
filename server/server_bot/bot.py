# server/server_bot/bot.py
import discord
from discord.ext import commands
import os
import json
# This would be a real encryption utility in the final version
from shared_lib.encryption import AESGCMEncryptor # Assuming this exists

# --- Configuration ---
# In a real app, these would come from a config file or environment variables
DISCORD_BOT_TOKEN = os.getenv("SERVER_BOT_TOKEN")
CLIENT_BOT_ID = int(os.getenv("CLIENT_BOT_ID", "0"))
ENCRYPTION_KEY = os.getenv("PAYLOAD_ENCRYPTION_KEY") # Must be a 32-byte key for AES-256

# --- Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)

# --- Placeholder for Encryption ---
# In a real implementation, this would be a robust, well-tested module.
encryptor = AESGCMEncryptor(ENCRYPTION_KEY) if ENCRYPTION_KEY else None


@bot.event
async def on_ready():
    print(f"Server Bot logged in as {bot.user}")
    print("------")


@bot.event
async def on_message(message: discord.Message):
    """
    This is the core of the relay logic. It listens for responses
    from the client-bot.
    """
    # Ignore messages from itself or any bot other than the client-bot
    if message.author.id != CLIENT_BOT_ID:
        return

    # --- Placeholder Logic for handling client-bot responses ---
    print(f"Received message from Client Bot in channel {message.channel.id}")

    # 1. Identify if the message is an encrypted payload.
    #    This could be done by checking for a prefix, a specific format,
    #    or if the message has an attachment.
    if not message.content.startswith("enc_payload::"):
        return

    encrypted_payload_str = message.content.replace("enc_payload::", "")

    # 2. Decrypt the payload.
    try:
        if not encryptor:
            raise ValueError("Encryption key not configured.")
        decrypted_payload = encryptor.decrypt(encrypted_payload_str)
        response_data = json.loads(decrypted_payload)
        print(f"Decrypted response: {response_data}")
    except Exception as e:
        print(f"Error decrypting payload: {e}")
        # Optionally, notify an admin channel of the failure.
        return

    # 3. Process the response.
    #    - Look up the session_id and request_id in the database.
    #    - Forward the response content to the FastAPI app via an API call or Redis.
    #    - Save the AI's message to the database.
    #    - Log the metrics from the payload.

    session_id = response_data.get("session_id")
    response_text = response_data.get("response")

    # Example: Update the user via the web interface (pseudo-code)
    # await api_client.post(f"/internal/sessions/{session_id}/notify", json={"response": response_text})

    print(f"Successfully processed response for session {session_id}")


# --- Slash Command Skeletons ---

@bot.slash_command(name="ai-start", description="Starts a new AI chat session.")
async def ai_start(ctx, prompt: str = ""):
    """
    - Creates a private channel for the user.
    - Sends a welcome message.
    - If a prompt is provided, relays it to the client-bot.
    """
    await ctx.defer(ephemeral=True)

    # --- Placeholder Logic ---
    # 1. Create a new private channel (e.g., #ai-session-username-123).
    # 2. Grant the user and admins access.
    # 3. Create a new Session in the database.
    # 4. Send a welcome message to the new channel.
    # 5. If prompt, trigger the inference flow.

    await ctx.respond(f"Session started! Check the new private channel.", ephemeral=True)


@bot.slash_command(name="ai-end", description="Ends the current chat session.")
async def ai_end(ctx):
    """
    - Archives the channel.
    - Triggers transcript generation and upload to S3.
    - DMs the user a link to their transcript.
    """
    # Check if the command is used in a valid session channel
    if not ctx.channel.name.startswith("ai-session-"):
        await ctx.respond("This command can only be used in an AI session channel.", ephemeral=True)
        return

    await ctx.defer()

    # --- Placeholder Logic ---
    # 1. Mark the session as ended in the database.
    # 2. Make the channel read-only for the user.
    # 3. Start a background task (e.g., Celery) to generate the transcript.
    # 4. The task would fetch all messages from the DB, format them, and upload to S3.
    # 5. DM the user with a pre-signed S3 URL.

    await ctx.respond("Session ended. Archiving and creating transcript...")


# --- Admin Command Skeletons ---

@bot.slash_command(name="ai-admin-status", description="Shows the system status.")
@commands.has_role("AI Admin") # Restrict to a specific role
async def ai_admin_status(ctx):
    # --- Placeholder Logic ---
    # 1. Query the database for recent metrics.
    # 2. Check the last message timestamp from the client-bot.
    # 3. Format and display the status in an embed.
    await ctx.respond("Client Bot is ONLINE. 0 requests in queue.", ephemeral=True)


def run_bot():
    if not DISCORD_BOT_TOKEN:
        print("Error: SERVER_BOT_TOKEN environment variable not set.")
        return
    if not CLIENT_BOT_ID:
        print("Warning: CLIENT_BOT_ID not set. Response handling will fail.")
    if not ENCRYPTION_KEY:
        print("Warning: PAYLOAD_ENCRYPTION_KEY not set. Payloads will not be secure.")

    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    # For direct execution. In production, this would be managed by a process manager.
    # You would need to set the environment variables:
    # export SERVER_BOT_TOKEN="..."
    # export CLIENT_BOT_ID="..."
    # export PAYLOAD_ENCRYPTION_KEY="..."
    run_bot()
