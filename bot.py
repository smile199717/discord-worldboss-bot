# bot.py
import discord
import random
import os
import datetime
import asyncio
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord.ui import View, Button
from discord.ext import commands

TOKEN = "MTQ2MzcxOTkxOTIxOTY0MjQ2OA.GqXL-y.qOnImQFyyGlSdehI6otFqjX3GG6fEXVMWSyqPs"  # 改成你的Bot Token
GUILD_ID = 1428004541340717058   # 改成整數，不要加引號

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# 臨時群組名單
groups = {
    "A": [],
    "B": [],
    "C": []
}

# ===== 登記指令 =====
@bot.slash_command(name="登記", description="加入臨時群組成員 (抽獎用)", guild_ids=[GUILD_ID])
async def register(ctx: discord.ApplicationContext, group: discord.Option(str, "選擇組別", choices=["A","B","C"]), name: str):
    if name not in groups[group]:
        groups[group].append(name)
    await ctx.respond(f"✅ {name} 已加入 {group} 組", ephemeral=True)

# ===== 登記清除 =====
@bot.slash_command(name="登記清除", description="清空指定組別成員", guild_ids=[GUILD_ID])
async def clear_group(ctx: discord.ApplicationContext, group: discord.Option(str, "選擇組別", choices=["A","B","C"])):
    groups[group].clear()
    await ctx.respond(f"✅ {group} 組已清空", ephemeral=True)

# ===== 抽獎 =====
@bot.slash_command(name="抽獎", description="從指定組別抽獎", guild_ids=[GUILD_ID])
async def draw(ctx: discord.ApplicationContext, group: discord.Option(str, "選擇組別", choices=["A","B","C"]), prizes: str):
    prize_list = [p.strip() for p in prizes.split("/")]
    members = groups[group].copy()
    if not members:
        await ctx.respond(f"⚠️ {group} 組沒有人可以抽獎", ephemeral=True)
        return
    random.shuffle(members)
    results = []
    for i, prize in enumerate(prize_list):
        if i >= len(members):
            break
        results.append(f"🎉 {members[i]} 抽中 {prize}")
    await ctx.respond("\n".join(results) if results else "⚠️ 沒有抽獎結果")

# ===== 登記名單 =====
@bot.slash_command(name="登記名單", description="查看指定組別名單", guild_ids=[GUILD_ID])
async def show_group(ctx: discord.ApplicationContext, group: discord.Option(str, "選擇組別", choices=["A","B","C"])):
    members = groups[group]
    msg = f"**{group}組名單:** {', '.join(members) if members else '沒有人'}"
    await ctx.respond(msg)  # 公開於伺服器

"""
# ===== Google Sheets =====
tz = pytz.timezone("Asia/Taipei")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    eval(os.getenv("GOOGLE_CREDENTIALS")), scope
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.getenv("GOOGLE_SHEET_ID")).sheet1
"""

# ===== Google Sheets =====
async def world_boss_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.datetime.now(tz)
        rows = sheet.get_all_records()

        for i, row in enumerate(rows, start=2):
            if not row["死亡時間"] or row["已提醒"] == True:
                continue

            death_time = tz.localize(
                datetime.datetime.strptime(row["死亡時間"], "%Y/%m/%d %H:%M")
            )
            respawn_time = death_time + datetime.timedelta(
                hours=int(row["重生小時"])
            )

            sheet.update(f"D{i}", respawn_time.strftime("%Y/%m/%d %H:%M"))

            # Embed 美化提醒
            if now >= respawn_time - datetime.timedelta(minutes=10):
                channel = bot.get_channel(int(row["提醒頻道ID"]))
                if channel:
                    respawn_time_str = respawn_time.strftime("%H:%M")
                    embed = discord.Embed(
                        title="⏰ 世界王即將重生",
                        color=0xE67E22
                    )
                    embed.add_field(name="世界王", value=row["王名稱"], inline=False)
                    embed.add_field(name="重生時間", value=respawn_time_str, inline=False)
                    await channel.send(embed=embed)
                    sheet.update(f"E{i}", True)

        await asyncio.sleep(60)

# ===== /王重生表 =====
@bot.slash_command(name="王重生表", description="列出所有世界王的重生時間")
async def world_boss_list(ctx: discord.ApplicationContext):
    ...
    await ctx.respond(embed=embed)
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.datetime.now(tz)

    rows = sheet.get_all_records()

    embed = discord.Embed(
        title="📜 世界王重生表",
        color=0x3498DB
    )

    has_data = False

    for row in rows:
        if not row["死亡時間"]:
            continue

        death_time = tz.localize(
            datetime.datetime.strptime(row["死亡時間"], "%Y/%m/%d %H:%M")
        )
        respawn_time = death_time + datetime.timedelta(
            hours=int(row["重生小時"])
        )

        remaining_minutes = int((respawn_time - now).total_seconds() // 60)

        if remaining_minutes < 0:
            remaining_minutes = 0

        embed.add_field(
            name=row["王名稱"],
            value=(
                f"🕒 重生時間：**{respawn_time.strftime('%H:%M')}**\n"
                f"⏳ 剩餘時間：**{remaining_minutes} 分鐘**"
            ),
            inline=False
        )
        has_data = True

    if not has_data:
        embed.description = "目前沒有已登記的世界王資料"

    await ctx.respond(embed=embed)

# ===== 身分組 =====
class RoleSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)  # 永不過期

    @discord.ui.button(
        label="最強眾神-軍團成員",
        style=discord.ButtonStyle.primary,
        emoji="⚔️",
        custom_id="role_button_1"
    )
    async def role_1(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        role = interaction.guild.get_role(1428021750846718104)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "✅ 已領取身分組：最強眾神-軍團成員",
                ephemeral=True
            )

    @discord.ui.button(
        label="摯友-副本/聖域/觀戰好朋友",
        style=discord.ButtonStyle.secondary,
        emoji="🤝",
        custom_id="role_button_2"
    )
    async def role_2(
        self,
        interaction: discord.Interaction,
        button: Button
    ):
        role = interaction.guild.get_role(1428038147094085743)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "✅ 已領取身分組：摯友",
                ephemeral=True
            )
@bot.slash_command(
    name="身分組選擇",
    description="發送新進成員身分組選擇面板",
    guild_ids=[GUILD_ID]
)
@commands.has_permissions(administrator=True)
async def send_role_panel(ctx: discord.ApplicationContext):

    embed = discord.Embed(
        title="📌 請選擇你的身分組",
        description=(
            "1️⃣ **選擇身分組才看的到頻道‼️**\n"
            "最強眾神-軍團成員\n"
            "摯友-副本/聖域/觀戰好朋友\n\n"
            "2️⃣ **軍團成員更改伺服器名稱**\n"
            "本人暱稱-職業/遊戲ID\n"
            "範例：小妮-治癒/窩肆妮妮\n\n"
            "3️⃣ **軍團成員至頻道 📚-聖域EXCEL 填寫基本資料**"
        ),
        color=0x2ECC71
    )

    await ctx.respond(embed=embed, view=RoleSelectView())

# ===== Bot 啟動訊息 =====
@bot.event
async def on_ready():
    print(f"✅ 已登入 {bot.user}")
    bot.add_view(RoleSelectView())
    print("✅ 身分組按鈕 View 已註冊")

# ===== 啟動 Bot =====
bot.run(TOKEN)