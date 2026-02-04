# =====================================================
# bot.py — 世界王提醒最終穩定版
# =====================================================

import discord
from discord import Option
import random
import os
import datetime
import asyncio
import pytz
from discord.ui import View
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =====================================================
# Token / 基本設定
# =====================================================

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN 沒有設定到環境變數")

GUILD_ID = 1428004541340717058
REMIND_CHANNEL_ID = 1463863523447668787
tz = pytz.timezone("Asia/Taipei")

# =====================================================
# Google Sheets
# =====================================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.getenv("GOOGLE_SHEET_ID")).sheet1

# =====================================================
# Bot
# =====================================================

intents = discord.Intents.default()
intents.members = True
bot = discord.Bot(intents=intents)

# =====================================================
# 臨時群組
# =====================================================

groups = {"A": [], "B": [], "C": []}

# =====================================================
# 身分組 View
# =====================================================

class RoleSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)  # ✅ 永久 View

    @discord.ui.button(
        label="最強眾神-軍團成員",
        style=discord.ButtonStyle.primary,
        emoji="💖",
        custom_id="role_select_legion"  # ✅ 必須要有
    )
    async def role_1(self, interaction: discord.Interaction, button):
        role = interaction.guild.get_role(1428021750846718104)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "✅ 已領取軍團成員", ephemeral=True
            )

    @discord.ui.button(
        label="摯友",
        style=discord.ButtonStyle.secondary,
        emoji="🪐",
        custom_id="role_select_friend"  # ✅ 必須要有
    )
    async def role_2(self, interaction: discord.Interaction, button):
        role = interaction.guild.get_role(1428038147094085743)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "✅ 已領取摯友", ephemeral=True
            )

# =====================================================
# Slash 指令：登記 / 名單 / 清除 / 抽獎 / 刪除
# =====================================================

@bot.slash_command(name="登記名單", guild_ids=[GUILD_ID])
async def show_group(ctx, group: Option(str, choices=["A", "B", "C"])):
    members = groups[group]
    embed = discord.Embed(title=f"📋 {group} 組登記名單", color=0x1ABC9C)

    if not members:
        embed.description = "（目前沒有任何登記）"
        await ctx.respond(embed=embed)
        return

    max_len = max(len(name) for name in members)
    lines = [f"{'編號':<4} {'名稱':<{max_len}}", "─" * (max_len + 8)]
    for i, name in enumerate(members, 1):
        lines.append(f"{i:<4} {name:<{max_len}}")

    embed.description = "```" + "\n".join(lines) + "```"
    await ctx.respond(embed=embed)

@bot.slash_command(name="登記", guild_ids=[GUILD_ID])
async def register(ctx, group: Option(str, choices=["A", "B", "C"]), name: str):
    if name in groups[group]:
        await ctx.respond("⚠️ 已登記", ephemeral=True)
        return
    groups[group].append(name)
    await ctx.respond(f"✅ {name} 已加入 {group} 組", ephemeral=True)

@bot.slash_command(name="登記清除", guild_ids=[GUILD_ID])
async def clear_group(ctx, group: Option(str, choices=["A", "B", "C"])):
    groups[group].clear()
    await ctx.respond(f"🗑️ {group} 組已清空", ephemeral=True)

@bot.slash_command(name="抽獎", guild_ids=[GUILD_ID])
async def draw(ctx, group: Option(str, choices=["A", "B", "C"]), prizes: str):
    members = groups[group].copy()
    if not members:
        await ctx.respond("⚠️ 沒有人可以抽", ephemeral=True)
        return

    prize_list = [p.strip() for p in prizes.split("/") if p.strip()]
    random.shuffle(members)

    result = []
    for i, prize in enumerate(prize_list):
        if i >= len(members):
            break
        result.append(f"🎉 {members[i]} 抽中 {prize}")

    await ctx.respond("\n".join(result))

@bot.slash_command(name="刪除", guild_ids=[GUILD_ID])
async def remove_entry(ctx, group: Option(str, choices=["A", "B", "C"]), name: str):
    if name not in groups[group]:
        await ctx.respond("⚠️ 不在名單中", ephemeral=True)
        return
    groups[group].remove(name)
    await ctx.respond(f"🗑️ 已移除 {name}", ephemeral=True)

# =====================================================
# Slash 指令：王重生表
# =====================================================

@bot.slash_command(
    name="王重生表",
    description="列出所有世界王的重生時間（美化版）",
    guild_ids=[GUILD_ID]
)
async def world_boss_list(ctx: discord.ApplicationContext):
    try:
        now = datetime.datetime.now(tz)
        rows = await asyncio.to_thread(sheet.get_all_records)

        # 過濾掉沒死亡時間的
        filtered = [r for r in rows if r.get("死亡時間")]
        if not filtered:
            await ctx.respond("目前沒有已登記的世界王資料", ephemeral=True)
            return

        # 計算王名稱欄寬
        name_width = max(len(r["王名稱"]) for r in filtered)
        respawn_width = len("重生時間")
        remain_width = len("剩餘時間(分鐘)")

        # 標題列
        header = f"{'王名稱':<{name_width}}  {'重生時間':<{respawn_width}}  {'剩餘時間(分鐘)':<{remain_width}}"
        lines = [header, "─" * len(header)]

        for r in filtered:
            death = tz.localize(datetime.datetime.strptime(r["死亡時間"], "%Y/%m/%d %H:%M"))
            respawn = death + datetime.timedelta(hours=int(r["重生小時"]))
            remain = max(0, int((respawn - now).total_seconds() // 60))

            line = f"{r['王名稱']:<{name_width}}  {respawn.strftime('%H:%M'):<{respawn_width}}  {remain:<{remain_width}}"
            lines.append(line)

        embed = discord.Embed(
            title="📜 世界王重生表",
            description="```" + "\n".join(lines) + "```",
            color=0x3498DB
        )

        await ctx.respond(embed=embed)

    except Exception as e:
        if not ctx.response.is_done():
            await ctx.respond(f"❌ 發生錯誤：{e}", ephemeral=True)

# =====================================================
# 世界王提醒（30 分鐘分組＋10 分鐘前提醒＋美化版）
# =====================================================
async def world_boss_reminder():
    await bot.wait_until_ready()
    print("🟢 world_boss_reminder started")

    reminded = {}  # group_key -> first_respawn

    while not bot.is_closed():
        try:
            now = datetime.datetime.now(tz)
           
            # 清掉已經重生過的群組（讓下一輪能再提醒）
            reminded = {k: v for k, v in reminded.items() if v > now}

            rows = await asyncio.to_thread(sheet.get_all_records)
            bosses = []

            # 1️⃣ 收集所有王的重生時間
            for r in rows:
                if not r.get("死亡時間"):
                    continue
                try:
                    death = tz.localize(
                        datetime.datetime.strptime(r["死亡時間"], "%Y/%m/%d %H:%M")
                    )
                    respawn = death + datetime.timedelta(hours=int(r["重生小時"]))
                    bosses.append({
                        "name": r["王名稱"],
                        "respawn": respawn
                    })
                except Exception as e:
                    print("❌ 資料解析失敗:", r, e)

            if not bosses:
                await asyncio.sleep(10)
                continue

            # 2️⃣ 依重生時間排序
            bosses.sort(key=lambda b: b["respawn"])

            # 3️⃣ 30 分鐘內分組
            groups = []
            current_group = [bosses[0]]

            for boss in bosses[1:]:
                if (boss["respawn"] - current_group[0]["respawn"]).total_seconds() <= 30 * 60:
                    current_group.append(boss)
                else:
                    groups.append(current_group)
                    current_group = [boss]

            groups.append(current_group)

            # 4️⃣ 每組只在「第一隻王重生前 10 分鐘」提醒
            for group in groups:
                first_respawn = group[0]["respawn"]
                delta = first_respawn - now

                group_key = first_respawn.strftime("%Y%m%d%H%M")

                
                if (
                    group_key not in reminded
                    and datetime.timedelta(seconds=0) < delta <= datetime.timedelta(minutes=10)
                ):
                    # 5️⃣ 建立對齊表格（美化）
                    max_name_len = max(len(b["name"]) for b in group)
                    header = f"{'王名稱':<{max_name_len}}  重生時間"
                    lines = [header, "─" * (len(header) + 2)]

                    for b in group:
                        lines.append(
                            f"{b['name']:<{max_name_len}}  {b['respawn'].strftime('%H:%M')}"
                        )

                    table = "```" + "\n".join(lines) + "```"

                    channel = bot.get_channel(REMIND_CHANNEL_ID)
                    if channel is None:
                        channel = await bot.fetch_channel(REMIND_CHANNEL_ID)

                    await channel.send(
                        embed=discord.Embed(
                            title="⏰ 世界王即將重生（10 分鐘內）",
                            description=table,
                            color=0xE67E22
                        )
                    )

                    reminded[group_key] = first_respawn
                    print("✅ 已提醒群組:", group_key)

            await asyncio.sleep(10)

        except Exception as e:
            print("🔥 world_boss_reminder error:", e)
            await asyncio.sleep(30)

# =====================================================
# on_ready
# =====================================================

@bot.event
async def on_ready():
    print(f"✅ 已登入 {bot.user}")
    bot.add_view(RoleSelectView())

    if not hasattr(bot, "boss_task"):
        bot.boss_task = bot.loop.create_task(world_boss_reminder())
        print("🟢 世界王提醒任務已啟動")

# =====================================================
# http
# =====================================================

from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

Thread(target=run_web).start()

# =====================================================
# Run
# =====================================================

bot.run(TOKEN)

















































