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

    # 過濾出有死亡時間的資料，避免重複或空白
    filtered_rows = [row for row in rows if row.get("死亡時間")]

    if not filtered_rows:
        await ctx.respond("目前沒有已登記的世界王資料")
        return

    # 計算每一欄最大長度，方便格式化
    name_width = max(len(row["王名稱"]) for row in filtered_rows) + 2
    respawn_width = len("重生時間") + 2
    remaining_width = len("剩餘時間(分鐘)") + 2

    # 建立 Embed
    embed = discord.Embed(
        title="📜 世界王重生表",
        color=0x3498DB
    )

    # 標題列
    header = f"{'王名稱':<{name_width}} {'重生時間':<{respawn_width}} {'剩餘時間(分鐘)':<{remaining_width}}"
    table_lines = [header, "―" * len(header)]  # 分隔線

    for row in filtered_rows:
        death_time = tz.localize(
            datetime.datetime.strptime(row["死亡時間"], "%Y/%m/%d %H:%M")
        )
        respawn_time = death_time + datetime.timedelta(hours=int(row["重生小時"]))
        remaining_minutes = int((respawn_time - now).total_seconds() // 60)
        if remaining_minutes < 0:
            remaining_minutes = 0

        line = f"{row['王名稱']:<{name_width}} {respawn_time.strftime('%H:%M'):<{respawn_width}} {remaining_minutes:<{remaining_width}}"
        table_lines.append(line)

    # 把整個表格放入 description
    embed.description = "```" + "\n".join(table_lines) + "```"

    await ctx.respond(embed=embed)

# ===== 提醒王重生（修正版）=====
async def world_boss_reminder():
    tz = pytz.timezone("Asia/Taipei")
    await bot.wait_until_ready()

    reminded_groups = set()  # 記錄已提醒過的「群組時間戳」

    while not bot.is_closed():
        now = datetime.datetime.now(tz)
        rows = sheet.get_all_records()

        upcoming = []

        # 1️⃣ 收集所有王的重生時間
        for row in rows:
            if not row.get("死亡時間"):
                continue

            try:
                death_time = tz.localize(
                    datetime.datetime.strptime(row["死亡時間"], "%Y/%m/%d %H:%M")
                )
                respawn_time = death_time + datetime.timedelta(
                    hours=int(row["重生小時"])
                )
                upcoming.append({
                    "name": row["王名稱"],
                    "respawn": respawn_time
                })
            except Exception:
                continue  # 有格式錯誤就跳過

        if not upcoming:
            await asyncio.sleep(60)
            continue

        # 2️⃣ 依重生時間排序
        upcoming.sort(key=lambda x: x["respawn"])

        # 3️⃣ 分組（30 分鐘內視為同時期）
        groups = []
        current_group = [upcoming[0]]

        for boss in upcoming[1:]:
            if (boss["respawn"] - current_group[0]["respawn"]).total_seconds() <= 30 * 60:
                current_group.append(boss)
            else:
                groups.append(current_group)
                current_group = [boss]

        groups.append(current_group)

        # 4️⃣ 每組只在「第一隻王重生前 10 分鐘」提醒一次
        for group in groups:
            first_respawn = group[0]["respawn"]
            remind_time = first_respawn - datetime.timedelta(minutes=10)

            group_key = first_respawn.strftime("%Y%m%d%H%M")  # 群組唯一 key

            # ✅ 正確的提醒時間判斷（關鍵）
            if remind_time <= now < first_respawn:
                if group_key in reminded_groups:
                    continue

                # 5️⃣ 建立對齊表格（王名長短不會亂）
                max_name_len = max(len(b["name"]) for b in group)
                header = f"{'王名稱':<{max_name_len}}  重生時間"
                lines = [header, "─" * (len(header) + 2)]

                for b in group:
                    lines.append(
                        f"{b['name']:<{max_name_len}}  {b['respawn'].strftime('%H:%M')}"
                    )

                table = "```" + "\n".join(lines) + "```"

                embed = discord.Embed(
                    title="⏰ 世界王即將重生（同時期）",
                    description=table,
                    color=0xE67E22
                )

                channel_id = 1463863523447668787  # 你的提醒頻道
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)

                # 6️⃣ 標記此群組已提醒
                reminded_groups.add(group_key)

        await asyncio.sleep(60)

# ===== 啟動 =====
@bot.event
async def on_ready():
    print(f"✅ 已登入 {bot.user}")
    bot.add_view(RoleSelectView())
    print("✅ 身分組按鈕 View 已註冊，指令同步完成")

bot.loop.create_task(world_boss_reminder())

# ===== Render Keep-Alive Server =====
from flask import Flask
from threading import Thread

app = Flask("render-keep-alive")

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

Thread(target=run_web).start()

bot.run(TOKEN)















