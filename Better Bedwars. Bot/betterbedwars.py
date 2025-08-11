import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import json
import random
from datetime import datetime, timedelta
import asyncio
import time

GUILD_ID = 817429755456258068  # Replace with your server ID

# === Load token from .env ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# === XP system ===
XP_FILE = "xp_data.json"
cooldowns = {}

# XP thresholds and associated rank roles
ROLE_REWARDS = {
    0:    ("<:Black:1080249084708925521>", "Black"),
    200:  ("<:Gray:1080245994958098474>", "Gray"),
    450:  ("<:LightGray:1080244962664390716>", "Light Gray"),
    750:  ("<:White:1080244243429335073>", "White"),
    1100: ("<:Purple:1080243221495562301>", "Purple"),
    1600: ("<:Magenta:1080110426077016064>", "Magenta"),
    2200: ("<:Pink:1080109695651549325>", "Pink"),
    2900: ("<:Blue:1080108451558076426>", "Blue"),
    3700: ("<:Cyan:1080106335053549658>", "Cyan"),
    4600: ("<:LightBlue:1079908537637027851>", "Light Blue"),
    5600: ("<:Green:1079901705048686652>", "Green"),
    6800: ("<:Lime:1079900191508938832>", "Lime"),
    8200: ("<:Yellow:1079898837742801037>", "Yellow"),
    9800: ("<:Orange:1079898354722549842>", "Orange"),
    11500:("<:Red:1079897267059818608>", "Red"),
    12000:("<a:Rainbow:1080253901288259626>", "Rainbow")  # animated emoji uses <a:...>
}

# Load XP data
if os.path.exists(XP_FILE):
    with open(XP_FILE, "r") as f:
        xp_data = json.load(f)
else:
    xp_data = {}

# === Setup Bot ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === Helper Functions ===
def calculate_level(xp: int) -> int:
    level = 0
    while xp >= 50 * (level + 1):
        level += 1
    return level

def save_xp():
    with open(XP_FILE, "w") as f:
        json.dump(xp_data, f, indent=4)

async def check_and_assign_role(member: discord.Member, xp: int):
    guild = member.guild
    if not guild:
        return

    # Determine highest role user qualifies for
    qualified_roles = [name for req_xp, (emoji, name) in ROLE_REWARDS.items() if xp >= req_xp]
    highest_role_name = qualified_roles[-1] if qualified_roles else None

    if highest_role_name:
        new_role = discord.utils.get(guild.roles, name=highest_role_name)

        # Remove old rank roles correctly
        for _, (_, role_name) in ROLE_REWARDS.items():
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role in member.roles and role.name != highest_role_name:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    print(f"⚠️ Cannot remove role {role.name} from {member}")

        # Add new highest role if not present
        if new_role and new_role not in member.roles:
            try:
                await member.add_roles(new_role)
                try:
                    await member.send(f"🎖️ You earned the **{highest_role_name}** role in **{guild.name}**!")
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                print(f"⚠️ Cannot assign role {highest_role_name} to {member.name}")

# === Events ===
@bot.event
async def on_ready():
    # This clears all global slash commands by syncing with no guild
    await bot.tree.sync()
    print("✅ Cleared all global commands")

    # Then sync guild commands normally if you want
    for guild in bot.guilds:
        try:
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} command(s) to guild {guild.name} ({guild.id})")
        except Exception as e:
            print(f"❌ Failed to sync commands to guild {guild.name}: {e}")

    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user_id = str(message.author.id)
    now = datetime.utcnow()

    if user_id in cooldowns and now < cooldowns[user_id]:
        return
    cooldowns[user_id] = now + timedelta(seconds=60)

    if user_id not in xp_data:
        xp_data[user_id] = {"xp": 0, "level": 0, "rank": None}  # add 'rank' key

    xp_earned = random.randint(5, 15)
    xp_data[user_id]["xp"] += xp_earned

    # Calculate current rank based on XP
    qualified_roles = [name for req_xp, (emoji, name) in ROLE_REWARDS.items() if xp_data[user_id]["xp"] >= req_xp]
    current_rank = qualified_roles[-1] if qualified_roles else "Unranked"

    # Announce only if rank changed
    if xp_data[user_id].get("rank") != current_rank:
        xp_data[user_id]["rank"] = current_rank
        await message.channel.send(f"🎉 {message.author.mention} You have reached **{current_rank}** rank!")

    await check_and_assign_role(message.author, xp_data[user_id]["xp"])

    save_xp()
    await bot.process_commands(message)

# === Slash Commands ===
@bot.tree.command(name="rank", description="Check your current XP and rank", guild=discord.Object(id=GUILD_ID))
async def rank(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    data = xp_data.get(user_id, {"xp": 0})
    current_xp = data["xp"]

    sorted_rewards = sorted(ROLE_REWARDS.items())
    current_rank = "Unranked"
    next_rank = None

    for xp_required, rank_name in sorted_rewards:
        if current_xp >= xp_required:
            current_rank = rank_name
        elif current_xp < xp_required and not next_rank:
            next_rank = (rank_name, xp_required - current_xp)
            break

    if next_rank:
        next_rank_text = f"➡️ Next rank: **{next_rank[0]}**, in **{next_rank[1]} XP**."
    else:
        next_rank_text = "🏁 You have reached the highest rank!"

    await interaction.response.send_message(
        f"📊 {interaction.user.mention}, you have **{current_xp} XP**.\n"
        f"🎖️ Current rank: **{current_rank}**.\n"
        f"{next_rank_text}",
        ephemeral=True
    )

@bot.tree.command(name="ranklist", description="Show all rank roles and their XP requirements")
async def ranklist(interaction: discord.Interaction):
    lines = []
    sorted_ranks = sorted(ROLE_REWARDS.items(), key=lambda x: x[0])
    for xp, (emoji_name, rank_name) in sorted_ranks:
        lines.append(f"{emoji_name} **{rank_name}** — {xp} XP")

    await interaction.response.send_message(
        "**__<a:Trophy:1397018196594393329> Rank Ladder:__**\n" + "\n".join(lines),
        ephemeral=True
    )

@bot.tree.command(name="ping", description="Returns the ping of the bot and server latency", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    start = time.perf_counter()
    await interaction.response.defer(ephemeral=False)  # Make initial ack public
    end = time.perf_counter()

    bot_latency_ms = round(bot.latency * 1000)
    server_latency_ms = round((end - start) * 1000)

    await interaction.followup.send(
        f"🏓 Pong! Latency is {server_latency_ms}ms. Bot Latency is {bot_latency_ms}ms",
        ephemeral=False  # Public message
    )

@bot.tree.command(name="xprebuild", description="Rebuild XP from past messages and update roles", guild=discord.Object(id=GUILD_ID))
async def xprebuild(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Starting XP rebuild. This may take some time...", ephemeral=True)
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await interaction.followup.send("❌ Guild not found!", ephemeral=True)
        return

    global xp_data
    xp_data = {}

    total_messages = 0
    users_seen = set()

    for channel in guild.text_channels:
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                if message.author.bot:
                    continue
                user_id = str(message.author.id)
                users_seen.add(user_id)

                if user_id not in xp_data:
                    xp_data[user_id] = {"xp": 0, "level": 0}

                xp_earned = random.randint(5, 15)
                xp_data[user_id]["xp"] += xp_earned
                total_messages += 1

                if total_messages % 500 == 0:
                    print(f"Processed {total_messages} messages so far...")

        except (discord.Forbidden, discord.HTTPException):
            print(f"⚠️ Can't access history for channel {channel.name}. Skipping.")

    # Update roles based on rebuilt XP
    for user_id in users_seen:
        member = guild.get_member(int(user_id))
        if member:
            xp = xp_data[user_id]["xp"]
            await check_and_assign_role(member, xp)

    save_xp()

    await interaction.followup.send(f"✅ Done! Processed {total_messages} messages from {len(users_seen)} users.", ephemeral=True)

# === Leaderboard Command ===
@bot.tree.command(name="leaderboard", description="Show top 10 users by XP", guild=discord.Object(id=GUILD_ID))
async def leaderboard(interaction: discord.Interaction):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await interaction.response.send_message("❌ Guild not found!", ephemeral=True)
        return

    # Sort users by XP descending and get top 10
    sorted_xp = sorted(xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]

    lines = []
    for i, (user_id, data) in enumerate(sorted_xp, start=1):
        member = guild.get_member(int(user_id))
        if not member:
            continue

        xp = data["xp"]
        # Find rank emoji for this user's XP
        rank_emoji = ""
        for req_xp, (emoji, name) in sorted(ROLE_REWARDS.items()):
            if xp >= req_xp:
                rank_emoji = emoji
            else:
                break

        lines.append(f"**{i}.** {member.mention} — {xp} XP ⠀•⠀ **Rank:** {rank_emoji}")

    if not lines:
        lines.append("No XP data found.")

    embed = discord.Embed(
        title="__**<a:Trophy:1397018196594393329> Top 10 XP Leaderboard**__",
        description="\n".join(lines),
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# === Run Bot ===
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN not found in .env file!")
