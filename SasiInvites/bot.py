import os
from dotenv import load_dotenv

load_dotenv()
from keep_alive import keep_alive
import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.invites = True

bot = commands.Bot(command_prefix="!", intents=intents)

invites_cache = {}
baseline_invites = {}
leaderboard_messages = {}

async def update_invites_cache(guild):
    try:
        invites_cache[guild.id] = await guild.invites()
    except discord.Forbidden:
        print(f"לבוט אין הרשאה לקרוא קישורים בשרת: {guild.name}")

async def get_user_contest_invites(guild, user_id):
    total = 0
    try:
        guild_invites = await guild.invites()
        for inv in guild_invites:
            if inv.inviter and inv.inviter.id == user_id:
                total += inv.uses
    except discord.Forbidden:
        pass
    
    baseline = baseline_invites.get(user_id, 0)
    return max(0, total - baseline)

async def refresh_live_leaderboard(guild):
    if guild.id not in leaderboard_messages:
        return

    channel_id, msg_id = leaderboard_messages[guild.id]
    channel = guild.get_channel(channel_id)
    if not channel:
        return

    try:
        msg = await channel.fetch_message(msg_id)
        guild_invites = await guild.invites()
        
        # איסוף נתונים מהקישורים
        raw_counts = {}
        for inv in guild_invites:
            if inv.inviter:
                raw_counts[inv.inviter] = raw_counts.get(inv.inviter, 0) + inv.uses

        contest_dict = {}
        for user, raw_uses in raw_counts.items():
            base = baseline_invites.get(user.id, 0)
            score = max(0, raw_uses - base)
            contest_dict[user] = (score, raw_uses)

        # השלמה ל-10 חברים אם חסרים
        for member in guild.members:
            if not member.bot and member not in contest_dict:
                contest_dict[member] = (0, 0)

        sorted_board = sorted(contest_dict.items(), key=lambda x: (x[1][0], x[1][1]), reverse=True)

        embed = discord.Embed(
            title="🎁 תחרות NITRO BOOST - לוח המובילים 🎁",
            description="🏆 **טופ 10 המזמינים בשרת** (הניקוד מתעדכן בלייב!):",
            color=discord.Color.purple()
        )

        medals = ["🥇", "🥈", "🥉"]
        for index, (user, (contest_score, total_uses)) in enumerate(sorted_board[:10], start=1):
            icon = medals[index-1] if index <= 3 else f"**#{index}**"
            embed.add_field(
                name=f"{icon} {user.display_name}",
                value=f"✨ הזמנות בתחרות: **{contest_score}**",
                inline=False
            )

        await msg.edit(embed=embed)
    except Exception as e:
        print(f"שגיאה בעדכון ה-Leaderboard: {e}")

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await update_invites_cache(guild)
    print(f'הבוט {bot.user.name} מחובר בהצלחה!')

@bot.event
async def on_member_join(member):
    guild = member.guild
    try:
        new_invites = await guild.invites()
        invites_cache[guild.id] = new_invites
    except discord.Forbidden:
        return

    await refresh_live_leaderboard(guild)

# -------------------------------------------------------------
# פקודות ניהול
# -------------------------------------------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def reset_contest(ctx):
    """מאפס את התחרות ומקפיא את הניקוד מחדש ל-0"""
    global baseline_invites
    try:
        guild_invites = await ctx.guild.invites()
        baseline_invites = {}
        for inv in guild_invites:
            if inv.inviter:
                baseline_invites[inv.inviter.id] = baseline_invites.get(inv.inviter.id, 0) + inv.uses
        
        await ctx.send("✅ **התחרות אופסה בהצלחה!** המונים בתחרות חזרו ל-0.")
        await refresh_live_leaderboard(ctx.guild)
    except discord.Forbidden:
        await ctx.send("❌ לבוט אין הרשאות לצפות בהזמנות.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_leaderboard(ctx):
    """מציג את טבלת ה-Top 10 המתעדכנת בלייב"""
    embed = discord.Embed(
        title="🎁 תחרות NITRO BOOST - לוח המובילים 🎁",
        description="טוען נתונים...",
        color=discord.Color.purple()
    )
    msg = await ctx.send(embed=embed)
    leaderboard_messages[ctx.guild.id] = (ctx.channel.id, msg.id)
    await refresh_live_leaderboard(ctx.guild)
    try:
        await ctx.message.delete()
    except:
        pass

# -------------------------------------------------------------
# פקודות למשתמשים
# -------------------------------------------------------------

@bot.command()
async def invites(ctx, member: discord.Member = None):
    """בדיקת הזמנות אישיות בתחרות"""
    target = member or ctx.author
    score = await get_user_contest_invites(ctx.guild, target.id)

    if target == ctx.author:
        await ctx.send(f'🏆 {ctx.author.mention}, יש לך **{score}** הזמנות בתחרות הנוכחית!')
    else:
        await ctx.send(f'📊 ל-**{target.display_name}** יש **{score}** הזמנות בתחרות הנוכחית.')

@bot.command(name="top")
async def leaderboard_cmd(ctx):
    """הצגת טבלת המובילים (פקודה: !top)"""
    try:
        guild_invites = await ctx.guild.invites()
        raw_counts = {}
        for inv in guild_invites:
            if inv.inviter:
                raw_counts[inv.inviter] = raw_counts.get(inv.inviter, 0) + inv.uses

        contest_dict = {}
        for user, raw_uses in raw_counts.items():
            base = baseline_invites.get(user.id, 0)
            score = max(0, raw_uses - base)
            contest_dict[user] = (score, raw_uses)

        for member in ctx.guild.members:
            if not member.bot and member not in contest_dict:
                contest_dict[member] = (0, 0)

        sorted_board = sorted(contest_dict.items(), key=lambda x: (x[1][0], x[1][1]), reverse=True)

        embed = discord.Embed(title="🏆 לוח המובילים בתחרות 🏆", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]
        for index, (user, (contest_score, total_uses)) in enumerate(sorted_board[:10], start=1):
            icon = medals[index-1] if index <= 3 else f"**#{index}**"
            embed.add_field(name=f"{icon} {user.display_name}", value=f"הזמנות בתחרות: **{contest_score}**", inline=False)

        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ לבוט אין הרשאות לצפות בהזמנות בשרת זה.")
keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))

