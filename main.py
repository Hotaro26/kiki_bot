import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import logging
import database
import keep_alive

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ace_bot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True # Required for tracking VC hours
intents.members = True # Required for looking up usernames

bot = commands.Bot(command_prefix=['!', '-'], intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')
    
    # Start the web server to keep Render happy
    await keep_alive.start_web_server()
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'Loaded cog: {filename}')
            except Exception as e:
                logger.error(f'Failed to load cog {filename}: {e}')

import database

async def main():
    async with bot:
        await database.setup_db()
        await load_cogs()
        if TOKEN and TOKEN != 'your_token_here':
            await bot.start(TOKEN)
        else:
            logger.error("Please set a valid DISCORD_TOKEN in your .env file.")

if __name__ == '__main__':
    asyncio.run(main())
