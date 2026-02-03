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

# ===== Bot（最終確認版）=====
intents = discord.Intents.default()
intents.members = True

class MyBot(discord.Bot):
    async def setup_hook(self):
        print("🟢 setup_hook called")
        asyncio.create_task(world_boss_reminder())

    async def on_connect(self):
        print("🔌 Discord gateway connected")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")

bot = MyBot(intents=intents)

print("🚀 Starting Discord bot...")

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

# ===== 登記 =====
@bot.slash_command(
    name="登記",
    description="一次選組別並輸入你的名字完成登記",
    guild_ids=[GUILD_ID]
)
async def register(
    ctx,
    group: Option(str, "選擇臨時群組", choices=["A", "B", "C"]),
    name: Option(str, "輸入你的名字")
):
    if name in groups[group]:
        await ctx.respond(f"⚠️ {name} 已經在 {group} 組了", ephemeral=True)
        return

    groups[group].append(name)
    await ctx.respond(f"✅ {name} 已加入 {group} 組", ephemeral=True)

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

# ===== 彩蛋自動回應 =====
@bot.event
async def on_message(message: discord.Message):
    # 忽略自己的訊息
    if message.author == bot.user:
        return

    # 彩蛋列表：key = 觸發字詞, value = 回應
    easter_eggs = {
        "將軍的頭盔": "將軍的頭盔",
        "哈囉": "汪🐕",
        "你好": "汪🐕",
        "嗨": "喵🐈",
        "嘴嘴": "又怎麼了"
    }

    # 遍歷彩蛋，檢查訊息中是否包含關鍵字
    for key, reply in easter_eggs.items():
        if key in message.content:
            await message.channel.send(reply)
            break  # 只回覆第一個匹配的彩蛋

    # ⚠️ 最後不要忘記呼叫 process_commands，保留 slash command 功能
    await bot.process_commands(message)

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
# 世界王提醒（穩定除錯版，可直接覆蓋）
# =====================================================
async def world_boss_reminder():
    await bot.wait_until_ready()
    print("🟢 world_boss_reminder started")

    reminded = {}  # group_key -> first_respawn

    while not bot.is_closed():
        try:
            now = datetime.datetime.now(tz)
            print("⏱️ reminder heartbeat:", now.strftime("%H:%M:%S"))

            # 清掉已過期的提醒
            reminded = {k: v for k, v in reminded.items() if v > now}

            rows = await asyncio.to_thread(sheet.get_all_records)
            upcoming = []

            for r in rows:
                if not r.get("死亡時間"):
                    continue
                try:
                    death = tz.localize(
                        datetime.datetime.strptime(r["死亡時間"], "%Y/%m/%d %H:%M")
                    )
                    respawn = death + datetime.timedelta(hours=int(r["重生小時"]))
                    upcoming.append({"name": r["王名稱"], "respawn": respawn})
                except Exception as e:
                    print("❌ 資料解析失敗:", r, e)

            if not upcoming:
                await asyncio.sleep(10)
                continue

            upcoming.sort(key=lambda x: x["respawn"])

            # 分組（30 分鐘內視為同時期）
            boss_groups = []
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
                key = first.strftime("%Y%m%d%H%M")

                # ✅【關鍵修正】用剩餘時間區間判斷，永不漏
                delta = first - now

                if (
                    key not in reminded
                    and datetime.timedelta(seconds=0) < delta <= datetime.timedelta(minutes=10)
                ):
                    print(
                        "🔔 觸發提醒:",
                        first.strftime("%Y/%m/%d %H:%M"),
                        "剩餘:",
                        delta,
                    )

                    max_len = max(len(b["name"]) for b in g)
                    text = "\n".join(
                        f"{b['name']:<{max_len}} {b['respawn'].strftime('%H:%M')}"
                        for b in g
                    )

                    channel_id = 1463863523447668787

                    # ✅ 先嘗試 cache
                    channel = bot.get_channel(channel_id)

                    # ❗ cache 拿不到就強制 fetch
                    if channel is None:
                        print("⚠️ channel cache miss, fetching...")
                        channel = await bot.fetch_channel(channel_id)

                    await channel.send(
                        embed=discord.Embed(
                            title="⏰ 世界王即將重生（同時期）",
                            description="```" + text + "```",
                            color=0xE67E22
                        )
                    )

                    reminded[key] = first
                    print("✅ 提醒已送出")

            await asyncio.sleep(10)

        except Exception as e:
            print("🔥 world_boss_reminder error:", e)
            await asyncio.sleep(10)

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








































