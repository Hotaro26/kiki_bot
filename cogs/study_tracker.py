import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timezone
import datetime as dt
import os
import pytz
import database

logger = logging.getLogger('kiki_bot.study_tracker')

class StudyTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Maps user_id to datetime when they joined VC
        self.active_sessions = {}
        
        # Hardcoded leaderboard channel from user
        self.leaderboard_channel_id = 1539850416387264542
        self.daily_announcement.start()

    @commands.Cog.listener()
    async def on_ready(self):
        # When bot restarts, find everyone already in a voice channel and start tracking them
        count = 0
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if not member.bot and member.id not in self.active_sessions:
                        self.active_sessions[member.id] = datetime.now()
                        count += 1
        if count > 0:
            logger.info(f"Recovered tracking for {count} users already in VC.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
            
        user_id = member.id

        # User joined a voice channel OR switched channels but wasn't being tracked
        if after.channel is not None and user_id not in self.active_sessions:
            self.active_sessions[user_id] = datetime.now()
            logger.info(f"{member.name} joined VC or was recovered. Started tracking.")

        # User completely left all voice channels
        elif before.channel is not None and after.channel is None:
            if user_id in self.active_sessions:
                join_time = self.active_sessions.pop(user_id)
                leave_time = datetime.now()
                
                duration = leave_time - join_time
                hours_studied = duration.total_seconds() / 3600.0
                
                # Save to database
                await database.add_study_time(user_id, hours_studied)
                logger.info(f"{member.name} left VC. Logged {hours_studied:.4f} hours.")
                
                # Optionally, we can send a DM or a message in a specific channel
                # try:
                #    await member.send(f"You studied for {hours_studied:.2f} hours!")
                # except: pass

    @commands.command(name='p')
    async def profile(self, ctx, member: discord.Member = None):
        """Show study profile embed for yourself or another user."""
        target_member = member or ctx.author
        user_data = await database.get_user_data(target_member.id)
        
        total_hours_float = user_data['total_hours'] if user_data else 0.0
        timezone = user_data['timezone'] if user_data and 'timezone' in user_data else 'Asia/Kolkata'
        
        # Get actual daily and monthly stats from database
        today_hours, month_hours = await database.get_study_stats(target_member.id, timezone)
        
        # Add live session time if currently in VC
        if target_member.id in self.active_sessions:
            join_time = self.active_sessions[target_member.id]
            live_duration_hours = (datetime.now() - join_time).total_seconds() / 3600.0
            
            total_hours_float += live_duration_hours
            today_hours += live_duration_hours
            month_hours += live_duration_hours
        
        def format_time(hours_float):
            total_sec = int(hours_float * 3600)
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            s = total_sec % 60
            if h > 0 or m > 0:
                return f"{h}h {m}m"
            return f"{s}s"

        time_str = format_time(total_hours_float)
        today_str = format_time(today_hours)
        month_str = format_time(month_hours)

        embed = discord.Embed(
            title=f"Banked {time_str}",
            description=f"{target_member.name}",
            color=0x2ecc71 # Green color matching the sidebar
        )
        
        if target_member.avatar:
            embed.set_thumbnail(url=target_member.avatar.url)
            
        embed.add_field(name="Today", value=today_str, inline=False)
        embed.add_field(name="This month", value=month_str, inline=False)
        embed.add_field(name="All time", value=time_str, inline=False)
        embed.add_field(name="Resets", value="`in 7 days`", inline=False)
        
        embed.set_footer(text=f"cozy study café ☕ ‧₊˚ 💻 ｡°.*  | {timezone}")
        
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name='lb', aliases=['leaderboard'])
    async def leaderboard(self, ctx, period: str = 'weekly'):
        """Show the study leaderboard. Usage: -lb daily, -lb weekly, -lb alltime"""
        period = period.lower()
        if period not in ['daily', 'weekly', 'alltime']:
            await ctx.reply("❌ Invalid period! Use `daily`, `weekly`, or `alltime`.", mention_author=False)
            return

        db_data = await database.get_leaderboard(period)
        
        # Convert to dictionary to add live times
        lb_dict = {user_id: hours for user_id, hours in db_data}
        
        # Add live session times
        now = datetime.now()
        for uid, join_time in self.active_sessions.items():
            live_duration = (now - join_time).total_seconds() / 3600.0
            lb_dict[uid] = lb_dict.get(uid, 0.0) + live_duration
            
        # Re-sort and take top 10
        sorted_lb = sorted(lb_dict.items(), key=lambda x: x[1], reverse=True)[:10]
        
        if not sorted_lb:
            empty_embed = discord.Embed(
                title=f"🏆 {period.capitalize()} Leaderboard",
                description="*No study sessions found for this period yet!*",
                color=0xf1c40f
            )
            await ctx.reply(embed=empty_embed, mention_author=False)
            return

        embeds = []
        colors = [0xffd700, 0xc0c0c0, 0xcd7f32] # Gold, Silver, Bronze
        medals = ["🥇", "🥈", "🥉"]
        
        # Create an embed for each of the Top 3
        spacer = "⠀" * 45 # 45 Braille spaces to force uniform embed width
        for i in range(min(3, len(sorted_lb))):
            user_id, hours = sorted_lb[i]
            
            total_sec = int(hours * 3600)
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            time_str = f"{h}h {m}m" if h > 0 or m > 0 else f"{total_sec}s"
            
            member = ctx.guild.get_member(user_id) if ctx.guild else None
            
            embed = discord.Embed(color=colors[i])
            if i == 0:
                embed.title = f"🏆 {period.capitalize()} Leaderboard\n✨ **Top 3 Scholars** ✨"
                
            # Add spacer at the end of description to stretch width
            embed.description = f"{medals[i]} <@{user_id}>\n ↳ ⌛ **{time_str}**\n\n{spacer}"
            
            if member and member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
                
            embeds.append(embed)

        # Create a final embed for runner ups
        if len(sorted_lb) > 3:
            runner_ups = []
            for i in range(3, len(sorted_lb)):
                user_id, hours = sorted_lb[i]
                
                total_sec = int(hours * 3600)
                h = total_sec // 3600
                m = (total_sec % 3600) // 60
                time_str = f"{h}h {m}m" if h > 0 or m > 0 else f"{total_sec}s"
                
                runner_ups.append(f"`#{i+1:02}` <@{user_id}> ─ {time_str}")
                
            runner_embed = discord.Embed(color=0x2ecc71, description="━━━━━━━━━━━━━━━━━━━━\n**Runner Ups**\n" + "\n".join(runner_ups) + f"\n\n{spacer}")
            # If no runner ups, put footer on the last top 3 embed
            if embeds:
                embeds[-1].set_footer(text="cozy study café ☕ ‧₊˚ 💻 ｡°.*")

        await ctx.reply(embeds=embeds, mention_author=False)

    @discord.app_commands.command(name='timezone', description='Set your local timezone')
    async def set_timezone(self, interaction: discord.Interaction, timezone: str):
        if timezone not in pytz.all_timezones:
            await interaction.response.send_message("❌ Invalid timezone selected.", ephemeral=True)
            return
            
        await database.set_user_timezone(interaction.user.id, timezone)
        await interaction.response.send_message(f"✅ Your timezone has been updated to **{timezone}**!", ephemeral=True)

    @set_timezone.autocomplete('timezone')
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        # Provide up to 25 suggestions based on user input
        matches = [tz for tz in pytz.common_timezones if current.lower() in tz.lower()]
        return [discord.app_commands.Choice(name=match, value=match) for match in matches[:25]]

async def setup(bot):
    await bot.add_cog(StudyTracker(bot))

    @tasks.loop(time=dt.time(hour=0, minute=0, tzinfo=timezone.utc))
    async def daily_announcement(self):
        """Announce daily/weekly winners at Midnight UTC."""
        channel = self.bot.get_channel(self.leaderboard_channel_id)
        if not channel:
            return
            
        today = datetime.now(timezone.utc)
        is_monday = (today.weekday() == 0) # 0 is Monday
        
        # Post Daily Winner for YESTERDAY (offset_days=1)
        await self._post_announcement(channel, 'daily', 1)
        
        if is_monday:
            # Post Weekly Winner for LAST WEEK (offset_days=7)
            await self._post_announcement(channel, 'weekly', 7)
            
    async def _post_announcement(self, channel, period: str, offset_days: int):
        db_data = await database.get_leaderboard(period, offset_days=offset_days)
        if not db_data:
            return # Nobody studied
            
        embeds = []
        colors = [0xffd700, 0xc0c0c0, 0xcd7f32]
        medals = ["🥇", "🥈", "🥉"]
        spacer = "⠀" * 45
        
        for i in range(min(3, len(db_data))):
            user_id, hours = db_data[i]
            total_sec = int(hours * 3600)
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            time_str = f"{h}h {m}m" if h > 0 or m > 0 else f"{total_sec}s"
            
            member = channel.guild.get_member(user_id)
            if not member:
                try:
                    member = await self.bot.fetch_user(user_id)
                except:
                    pass
            
            embed = discord.Embed(color=colors[i])
            if i == 0:
                title_prefix = "🌟 Yesterday's" if period == 'daily' else "👑 Last Week's"
                embed.title = f"📢 {title_prefix} {period.capitalize()} Winners!\n✨ **Top 3 Scholars** ✨"
                
            embed.description = f"{medals[i]} <@{user_id}>\n ↳ ⌛ **{time_str}**\n\n{spacer}"
            if member and getattr(member, 'avatar', None):
                embed.set_thumbnail(url=member.avatar.url)
            embeds.append(embed)
            
        if len(db_data) > 3:
            runner_ups = []
            for i in range(3, len(db_data)):
                user_id, hours = db_data[i]
                total_sec = int(hours * 3600)
                h = total_sec // 3600
                m = (total_sec % 3600) // 60
                time_str = f"{h}h {m}m" if h > 0 or m > 0 else f"{total_sec}s"
                runner_ups.append(f"`#{i+1:02}` <@{user_id}> ─ {time_str}")
                
            runner_embed = discord.Embed(color=0x2ecc71, description="━━━━━━━━━━━━━━━━━━━━\n**Runner Ups**\n" + "\n".join(runner_ups) + f"\n\n{spacer}")
            embeds.append(runner_embed)
            
        await channel.send(f"Attention everyone! The {period} study results are in! 🎉", embeds=embeds)
