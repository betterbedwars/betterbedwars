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
from difflib import SequenceMatcher
import re  # <-- Added for gibberish detection

GUILD_ID = 817429755456258068  # Replace with your server ID

# === Load token from .env ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# === XP system ===
XP_FILE = "xp_data.json"
THRESHOLD_FILE = "similarity_threshold.json"
cooldowns = {}
recent_messages = {}  # Tracks last few messages per user
default_similarity_threshold = 0.8

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
    12000:("<a:Rainbow:1080253901288259626>", "Rainbow")
}

# Load XP data
if os.path.exists(XP_FILE):
    with open(XP_FILE, "r") as f:
        xp_data = json.load(f)
else:
    xp_data = {}

# Load similarity thresholds
if os.path.exists(THRESHOLD_FILE):
    with open(THRESHOLD_FILE, "r") as f:
        similarity_thresholds = json.load(f)
else:
    similarity_thresholds = {}

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

def save_thresholds():
    with open(THRESHOLD_FILE, "w") as f:
        json.dump(similarity_thresholds, f, indent=4)

async def check_and_assign_role(member: discord.Member, xp: int):
    guild = member.guild
    if not guild:
        return

    qualified_roles = [name for req_xp, (emoji, name) in ROLE_REWARDS.items() if xp >= req_xp]
    highest_role_name = qualified_roles[-1] if qualified_roles else None

    if highest_role_name:
        new_role = discord.utils.get(guild.roles, name=highest_role_name)

        for _, (_, role_name) in ROLE_REWARDS.items():
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role in member.roles and role.name != highest_role_name:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    print(f"⚠️ Cannot remove role {role.name} from {member}")

        if new_role and new_role not in member.roles:
            try:
                await member.add_roles(new_role)
                try:
                    await member.send(f"🎖️ You earned the **{highest_role_name}** role in **{guild.name}**!")
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                print(f"⚠️ Cannot assign role {highest_role_name} to {member.name}")

def is_message_unique(user_id: str, message_content: str, guild_id: int) -> bool:
    threshold = similarity_thresholds.get(str(guild_id), default_similarity_threshold)
    user_messages = recent_messages.get(user_id, [])

    for old_msg in user_messages:
        similarity = SequenceMatcher(None, message_content, old_msg).ratio()
        if similarity >= threshold:
            return False
    return True

# === Gibberish / Spam Detection ===
def is_meaningful_message(message: str) -> bool:
    cleaned = re.sub(r'[^a-zA-Z\s]', '', message).strip().lower()

    if len(cleaned) < 4:
        return False

    if re.search(r'(.)\1{3,}', cleaned):
        return False

    if not re.search(r'[aeiou]', cleaned):
        return False

    consonants = len(re.findall(r'[bcdfghjklmnpqrstvwxyz]', cleaned))
    vowels = len(re.findall(r'[aeiou]', cleaned))

    if vowels > 0 and consonants / vowels > 5:
        return False

    return True

# === Events ===
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Bot is ready!")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user_id = str(message.author.id)
    guild_id = message.guild.id

    if user_id not in xp_data:
        xp_data[user_id] = {"xp": 0, "level": 0, "rank": None}

    content = ''.join(filter(str.isalpha, message.content.lower()))
    if not content:
        await bot.process_commands(message)
        return

    if not is_meaningful_message(message.content):
        print(f"🚫 Ignored meaningless message from {message.author}: {message.content}")
        await bot.process_commands(message)
        return

    if is_message_unique(user_id, content, guild_id):
        xp_earned = random.randint(5, 15)
        xp_data[user_id]["xp"] += xp_earned

        if user_id not in recent_messages:
            recent_messages[user_id] = []

        recent_messages[user_id].append(content)

        if len(recent_messages[user_id]) > 10:
            recent_messages[user_id].pop(0)

        qualified_roles = [name for req_xp, (emoji, name) in ROLE_REWARDS.items() if xp_data[user_id]["xp"] >= req_xp]
        current_rank = qualified_roles[-1] if qualified_roles else "Unranked"

        if xp_data[user_id].get("rank") != current_rank:
            xp_data[user_id]["rank"] = current_rank
            await message.channel.send(f"🎉 {message.author.mention} You have reached **{current_rank}** rank!")

        await check_and_assign_role(message.author, xp_data[user_id]["xp"])

    save_xp()
    await bot.process_commands(message)

# === Slash Commands ===
@bot.tree.command(name="similaritythreshold", description="Set the similarity threshold for XP (0-1)")
@app_commands.describe(threshold="A value between 0.0 and 1.0")
async def similarity_threshold(interaction: discord.Interaction, threshold: float):
    if not 0 <= threshold <= 1:
        await interaction.response.send_message("❌ Threshold must be between 0.0 and 1.0", ephemeral=True)
        return

    similarity_thresholds[str(interaction.guild.id)] = threshold
    save_thresholds()

    await interaction.response.send_message(f"✅ Similarity threshold set to {threshold}", ephemeral=True)

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
    await interaction.response.defer(ephemeral=False)
    end = time.perf_counter()

    bot_latency_ms = round(bot.latency * 1000)
    server_latency_ms = round((end - start) * 1000)

    await interaction.followup.send(
        f"🏓 Pong! Latency is {server_latency_ms}ms. Bot Latency is {bot_latency_ms}ms",
        ephemeral=False
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

    for user_id in users_seen:
        member = guild.get_member(int(user_id))
        if member:
            xp = xp_data[user_id]["xp"]
            await check_and_assign_role(member, xp)

    save_xp()
    await interaction.followup.send(f"✅ Done! Processed {total_messages} messages from {len(users_seen)} users.", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show top 10 users by XP", guild=discord.Object(id=GUILD_ID))
async def leaderboard(interaction: discord.Interaction):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await interaction.response.send_message("❌ Guild not found!", ephemeral=True)
        return

    sorted_xp = sorted(xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]
    lines = []

    for i, (user_id, data) in enumerate(sorted_xp, start=1):
        member = guild.get_member(int(user_id))
        if not member:
            continue
        xp = data["xp"]
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

@bot.tree.command(name="say", description="Make the bot say something")
async def say(interaction: discord.Interaction, message: str):

    # acknowledge interaction but hide response
    await interaction.response.defer(ephemeral=True)

    # send the actual bot message
    await interaction.channel.send(message)

    # delete the temporary interaction response
    try:
        await interaction.delete_original_response()
    except:
        pass

# === Run Bot ===
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN not found in .env file!")
