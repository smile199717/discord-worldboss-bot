# bot.py
import discord
import random
import os
import datetime
import asyncio
import pytz
from discord.ui import View, Button
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ===== Token =====
TOKEN = os.getenv("DISCORD_TOKEN")  # 從 Render 環境變數讀
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN 沒有設定到環境變數")

GUILD_ID = 1428004541340717058

# ===== Google Sheets =====
tz = pytz.timezone("Asia/Taipei")  # 台灣時區

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# 從 Render 環境變數讀 JSON
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
gc = gspread.authorize(creds)

# Sheet ID 也從環境變數讀
sheet = gc.open_by_key(os.getenv("GOOGLE_SHEET_ID")).sheet1

# ===== Bot =====
intents = discord.Intents.default()
intents.members = True
bot = discord.Bot(intents=intents)

# ===== 時區 =====
tz = pytz.timezone("Asia/Taipei")

# ===== 臨時群組 =====
groups = {"A": [], "B": [], "C": []}

# ===== 登記 =====
@bot.slash_command(name="登記", guild_ids=[GUILD_ID])
async def register(ctx, group: str, name: str):
    if group not in groups:
        await ctx.respond("❌ 群組不存在", ephemeral=True)
        return
    if name not in groups[group]:
        groups[group].append(name)
    await ctx.respond(f"✅ {name} 已加入 {group} 組", ephemeral=True)

# ===== 清除 =====
@bot.slash_command(name="登記清除", guild_ids=[GUILD_ID])
async def clear_group(ctx, group: str):
    groups[group].clear()
    await ctx.respond(f"✅ {group} 組已清空", ephemeral=True)

# ===== 抽獎 =====
@bot.slash_command(name="抽獎", guild_ids=[GUILD_ID])
async def draw(ctx, group: str, prizes: str):
    members = groups[group].copy()
    if not members:
        await ctx.respond("⚠️ 沒有人可以抽", ephemeral=True)
        return

    prize_list = [p.strip() for p in prizes.split("/")]
    random.shuffle(members)

    results = []
    for i, prize in enumerate(prize_list):
        if i >= len(members):
            break
        results.append(f"🎉 {members[i]} 抽中 {prize}")

    await ctx.respond("\n".join(results))

# ===== 名單 =====
@bot.slash_command(name="登記名單", guild_ids=[GUILD_ID])
async def show_group(ctx, group: str):
    members = groups[group]
    await ctx.respond(
        f"**{group} 組名單：** {', '.join(members) if members else '沒有人'}"
    )

# ===== 身分組 View =====
class RoleSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="最強眾神-軍團成員",
        style=discord.ButtonStyle.primary,
        emoji="⚔️",
        custom_id="role_1"
    )
    async def role_1(self, interaction, button):
        role = interaction.guild.get_role(1428021750846718104)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ 已領取軍團成員", ephemeral=True)

    @discord.ui.button(
        label="摯友",
        style=discord.ButtonStyle.secondary,
        emoji="🤝",
        custom_id="role_2"
    )
    async def role_2(self, interaction, button):
        role = interaction.guild.get_role(1428038147094085743)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ 已領取摯友", ephemeral=True)

# ===== 發送身分組面板（管理員）=====
@bot.slash_command(name="發送身分組", guild_ids=[GUILD_ID])
@discord.default_permissions(administrator=True)
async def send_role_panel(ctx):
    embed = discord.Embed(
        title="📌 請選擇你的身分組",
        description="點擊下方按鈕領取身分組",
        color=0x2ECC71
    )
    await ctx.respond(embed=embed, view=RoleSelectView())

# ===== /王重生表 =====
@bot.slash_command(
    name="王重生表",
    description="列出所有世界王的重生時間",
    guild_ids=[GUILD_ID]
)
async def world_boss_list(ctx: discord.ApplicationContext):
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.datetime.now(tz)

    rows = sheet.get_all_records()

    if not rows:
        await ctx.respond("目前沒有已登記的世界王資料")
        return

    # 建立 Embed
    embed = discord.Embed(
        title="📜 世界王重生表",
        color=0x3498DB
    )

    # 標題欄位
    header = f"{'王名稱':<10} {'重生時間':<8} {'剩餘時間(分鐘)':<8}"
    table_lines = [header, "―" * len(header)]  # 分隔線

    # 循環累加每隻王資料
    for row in rows:
        if not row.get("死亡時間"):
            continue  # 沒死亡時間就跳過

        death_time = tz.localize(
            datetime.datetime.strptime(row["死亡時間"], "%Y/%m/%d %H:%M")
        )
        respawn_time = death_time + datetime.timedelta(hours=int(row["重生小時"]))
        remaining_minutes = int((respawn_time - now).total_seconds() // 60)
        if remaining_minutes < 0:
            remaining_minutes = 0

        line = f"{row['王名稱']:<12} {respawn_time.strftime('%H:%M'):<6} {remaining_minutes:<12}"
        table_lines.append(line)

     # 使用 ljust 保證對齊
    line = f"{row['王名稱'][:10].ljust(10)} {respawn_time.strftime('%H:%M').ljust(8)} {str(remaining_minutes).ljust(8)}"
    table_lines.append(line)
    
    # 循環結束後再把整個表格放入 description
    embed.description = "```" + "\n".join(table_lines) + "```"

    await ctx.respond(embed=embed)

# ===== 啟動 =====
@bot.event
async def on_ready():
    print(f"✅ 已登入 {bot.user}")
    bot.add_view(RoleSelectView())
    print("✅ 身分組按鈕 View 已註冊，指令同步完成")

bot.run(TOKEN)









