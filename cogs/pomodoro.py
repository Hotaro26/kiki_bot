import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import database

logger = logging.getLogger('kiki_bot.pomodoro')

class StopConfirmView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id

    @discord.ui.button(label="Yes, give up", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your timer!", ephemeral=True)
            return
            
        if self.user_id in self.cog.active_timers:
            self.cog.active_timers.remove(self.user_id)
            await interaction.response.edit_message(content="🛑 Pomodoro stopped. Don't give up next time!", view=None)
        else:
            await interaction.response.edit_message(content="❌ You don't have an active timer.", view=None)
        self.stop()

    @discord.ui.button(label="No, keep going!", style=discord.ButtonStyle.success)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your timer!", ephemeral=True)
            return
            
        await interaction.response.edit_message(content="💪 That's the spirit! Keep working!", view=None)
        self.stop()

class Pomodoro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Prevent users from starting multiple timers at once
        self.active_timers = set()

    @app_commands.command(name='pomodoro', description='Start a custom pomodoro timer')
    @app_commands.describe(work_min="Focus time in minutes", break_min="Break time in minutes", cycles="Number of work/break cycles to run")
    async def pomodoro(self, interaction: discord.Interaction, work_min: int = 25, break_min: int = 5, cycles: int = 1):
        user_id = interaction.user.id
        
        if user_id in self.active_timers:
            await interaction.response.send_message("❌ You already have an active pomodoro timer running!", ephemeral=True)
            return

        # Minimum bounds checking
        if work_min <= 0 or break_min <= 0 or cycles <= 0:
            await interaction.response.send_message("❌ Please enter valid numbers (greater than 0).", ephemeral=True)
            return

        self.active_timers.add(user_id)
        
        def make_progress_bar(current, total):
            if total <= 1: return ""
            return f"\nProgress: `[{'🍅' * current}{'⚪' * (total - current)}]` ({current}/{total})"

        # Start message
        cycle_text = f" for **{cycles} cycle{'s' if cycles > 1 else ''}**"
        start_bar = make_progress_bar(0, cycles)
        
        await interaction.response.send_message(
            f"🍅 **Pomodoro Started!**\nFocus for **{work_min} minutes**, then take a **{break_min} minute** break{cycle_text}. I'll ping you!{start_bar}"
        )

        async def send_ping(message):
            member = interaction.guild.get_member(user_id) if interaction.guild else interaction.user
            if hasattr(member, 'voice') and member.voice and member.voice.channel:
                try:
                    await member.voice.channel.send(message)
                    return
                except discord.Forbidden:
                    pass
            await interaction.channel.send(message)

        try:
            for current_cycle in range(1, cycles + 1):
                # Wait for work session
                await asyncio.sleep(work_min * 60)
                
                # Check if cancelled
                if user_id not in self.active_timers:
                    return
                    
                # Log the focus session to the database!
                await database.add_study_time(user_id, work_min / 60.0)
                
                progress_bar = make_progress_bar(current_cycle, cycles)
                
                if current_cycle == cycles:
                    await send_ping(f"🎉 {interaction.user.mention} Incredible job! You finished your final {work_min}-minute focus session. All cycles complete! 🏆{progress_bar}")
                    break
                else:
                    await send_ping(f"🔔 {interaction.user.mention} Cycle {current_cycle} complete! Take a {break_min}-minute break. ☕{progress_bar}")
                
                # Wait for break session
                await asyncio.sleep(break_min * 60)
                
                # Check if cancelled
                if user_id not in self.active_timers:
                    return
                    
                await send_ping(f"⏰ {interaction.user.mention} Break is over! Time for cycle {current_cycle + 1} of {cycles}. Get back to work!{progress_bar}")
            
        except Exception as e:
            logger.error(f"Error in pomodoro timer for user {user_id}: {e}")
        finally:
            if user_id in self.active_timers:
                self.active_timers.remove(user_id)

    @app_commands.command(name='stop_pomodoro', description='Stop your current pomodoro timer')
    async def stop_pomodoro(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.active_timers:
            view = StopConfirmView(self, user_id)
            await interaction.response.send_message("Are you sure you want to give up on your pomodoro session? 🥺", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("❌ You don't have an active pomodoro timer.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Pomodoro(bot))
