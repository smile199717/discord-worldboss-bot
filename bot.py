# bot.py
import discord
from discord import Option
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
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN 沒有設定到環境變數")

GUILD_ID = 1428004541340717058

# ===== Google Sheets =====
tz = pytz.timezone("Asia/Taipei")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.getenv("GOOGLE_SHEET_ID")).sheet1

# ===== Bot =====
intents = discord.Intents.default()
intents.members = True
bot = discord.Bot(intents=intents)

# ===== 臨時群組 =====
groups = {"A": [], "B": [], "C": []}

# =====================================================
# /登記名單（表格、公開）
# =====================================================
@bot.slash_command(
    name="登記名單",
    description="查看臨時群組名單（表格）",
    guild_ids=[GUILD_ID]
)
async def show_group(
    ctx,
    group: Option(str, "選擇臨時群組", choices=["A", "B", "C"])
):
    members = groups[group]

    embed = discord.Embed(
        title=f"📋 {group} 組登記名單",
        color=0x1ABC9C
    )

    if not members:
        embed.description = "（目前沒有任何登記）"
        await ctx.respond(embed=embed)
        return

    max_len = max(len(name) for name in members)
    header = f"{'編號':<4} {'名稱':<{max_len}}"
    lines = [header, "─" * (len(header) + 2)]

    for idx, name in enumerate(members, start=1):
        lines.append(f"{idx:<4} {name:<{max_len}}")

    embed.description = "```" + "\n".join(lines) + "```"
    await ctx.respond(embed=embed)

# =====================================================
# /登記清除
# =====================================================
@bot.slash_command(
    name="登記清除",
    description="清空臨時群組",
    guild_ids=[GUILD_ID]
)
async def clear_group(
    ctx,
    group: Option(str, "選擇臨時群組", choices=["A", "B", "C"])
):
    groups[group].clear()
    await ctx.respond(f"🗑️ {group} 組已清空", ephemeral=True)

# =====================================================
# /抽獎
# =====================================================
@bot.slash_command(
    name="抽獎",
    description="從臨時群組中抽獎",
    guild_ids=[GUILD_ID]
)
async def draw(
    ctx,
    group: Option(str, "選擇臨時群組", choices=["A", "B", "C"]),
    prizes: Option(str, "輸入獎品（用 / 分隔）")
):
    members = groups[group].copy()
    if not members:
        await ctx.respond("⚠️ 該群組沒有人可以抽", ephemeral=True)
        return

    prize_list = [p.strip() for p in prizes.split("/") if p.strip()]
    random.shuffle(members)

    results = []
    for i, prize in enumerate(prize_list):
        if i >= len(members):
            break
        results.append(f"🎉 {members[i]} 抽中 {prize}")

    await ctx.respond("\n".join(results))

# =====================================================
# /刪除
# =====================================================
@bot.slash_command(
    name="刪除",
    description="刪除自己在臨時群組的登記（請輸入登記時的名字）",
    guild_ids=[GUILD_ID]
)
async def remove_entry(
    ctx,
    group: Option(str, "選擇臨時群組", choices=["A", "B", "C"]),
    name: Option(str, "輸入登記時使用的名字")
):
    if name not in groups[group]:
        await ctx.respond(f"⚠️ {name} 不在 {group} 組的登記名單中", ephemeral=True)
        return

    groups[group].remove(name)
    await ctx.respond(f"🗑️ 已將 **{name}** 從 {group} 組移除", ephemeral=True)

# =====================================================
# 身分組 View
# =====================================================
class RoleSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="最強眾神-軍團成員", style=discord.ButtonStyle.primary, emoji="💖")
    async def role_1(self, interaction, button):
        role = interaction.guild.get_role(1428021750846718104)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ 已領取軍團成員", ephemeral=True)

    @discord.ui.button(label="摯友", style=discord.ButtonStyle.secondary, emoji="🪐")
    async def role_2(self, interaction, button):
        role = interaction.guild.get_role(1428038147094085743)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ 已領取摯友", ephemeral=True)

# =====================================================
# /王重生表
# =====================================================
@bot.slash_command(
    name="王重生表",
    description="列出所有世界王的重生時間",
    guild_ids=[GUILD_ID]
)
async def world_boss_list(ctx: discord.ApplicationContext):
    try:
        now = datetime.datetime.now(tz)
        rows = await asyncio.to_thread(sheet.get_all_records)

        filtered = [r for r in rows if r.get("死亡時間")]
        if not filtered:
            await ctx.respond("目前沒有已登記的世界王資料", ephemeral=True)
            return

        name_width = max(len(r["王名稱"]) for r in filtered) + 2
        lines = [f"{'王名稱':<{name_width}} 重生 剩餘(分)", "─" * (name_width + 10)]

        for r in filtered:
            death = tz.localize(datetime.datetime.strptime(r["死亡時間"], "%Y/%m/%d %H:%M"))
            respawn = death + datetime.timedelta(hours=int(r["重生小時"]))
            remain = max(0, int((respawn - now).total_seconds() // 60))
            lines.append(f"{r['王名稱']:<{name_width}} {respawn.strftime('%H:%M')} {remain}")

        await ctx.respond(
            embed=discord.Embed(
                title="📜 世界王重生表",
                description="```" + "\n".join(lines) + "```",
                color=0x3498DB
            )
        )

    except Exception as e:
        if not ctx.response.is_done():
            await ctx.respond(f"❌ 發生錯誤：{e}", ephemeral=True)

# =====================================================
# 世界王提醒
# =====================================================
async def world_boss_reminder():
    await bot.wait_until_ready()
    reminded = {}

    while not bot.is_closed():
        try:
            now = datetime.datetime.now(tz)
            reminded = {k: v for k, v in reminded.items() if v > now}

            rows = await asyncio.to_thread(sheet.get_all_records)
            upcoming = []

            for r in rows:
                if not r.get("死亡時間"):
                    continue
                death = tz.localize(datetime.datetime.strptime(r["死亡時間"], "%Y/%m/%d %H:%M"))
                respawn = death + datetime.timedelta(hours=int(r["重生小時"]))
                upcoming.append({"name": r["王名稱"], "respawn": respawn})

            upcoming.sort(key=lambda x: x["respawn"])

            boss_groups = []
            if upcoming:
                cur = [upcoming[0]]
                for b in upcoming[1:]:
                    if (b["respawn"] - cur[0]["respawn"]).total_seconds() <= 1800:
                        cur.append(b)
                    else:
                        boss_groups.append(cur)
                        cur = [b]
                boss_groups.append(cur)

            for g in boss_groups:
                first = g[0]["respawn"]
                if first - datetime.timedelta(minutes=10) <= now < first:
                    key = first.strftime("%Y%m%d%H%M")
                    if key in reminded:
                        continue

                    text = "\n".join(f"{b['name']} {b['respawn'].strftime('%H:%M')}" for b in g)
                    channel = bot.get_channel(1463863523447668787)
                    if channel:
                        await channel.send(
                            embed=discord.Embed(
                                title="⏰ 世界王即將重生",
                                description="```" + text + "```",
                                color=0xE67E22
                            )
                        )
                    reminded[key] = first

            await asyncio.sleep(60)

        except Exception as e:
            print("World boss reminder error:", e)
            await asyncio.sleep(60)

# =====================================================
# 啟動
# =====================================================
@bot.event
async def on_ready():
    print(f"✅ 已登入 {bot.user}")
    bot.add_view(RoleSelectView())
    if not hasattr(bot, "boss_task"):
        bot.boss_task = bot.loop.create_task(world_boss_reminder())

# ===== Render keep-alive =====
from flask import Flask
from threading import Thread

app = Flask("keep-alive")

@app.route("/")
def home():
    return "Bot running"

Thread(
    target=lambda: app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
).start()

bot.run(TOKEN)



























