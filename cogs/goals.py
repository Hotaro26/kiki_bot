import discord
from discord.ext import commands
import logging

logger = logging.getLogger('kiki_bot.goals')

class Goals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setgoal')
    async def set_goal(self, ctx, hours: float, period: str = "weekly"):
        """Set a study goal (e.g., !setgoal 10 weekly)"""
        # TODO: Store the goal in the database
        await ctx.send(f"Awesome! I've set your {period} goal to {hours} hours.")

    @commands.command(name='goal')
    async def check_goal(self, ctx):
        """Check your progress towards your goal."""
        # TODO: Retrieve goal and current hours, calculate progress
        await ctx.send("Goal tracking is under construction!")

async def setup(bot):
    await bot.add_cog(Goals(bot))
