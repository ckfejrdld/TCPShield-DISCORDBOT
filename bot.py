import discord
from discord import app_commands
import sqlite3
import config
import api
import datetime
import asyncio

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def create_table():
    con = connect_db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS proxy (
        "domain"	TEXT NOT NULL,
        "backend"	TEXT NOT NULL,
        "owner"	TEXT NOT NULL,
        "created_at" TEXT
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS backend (
        "name"	TEXT NOT NULL,
        "hostname"	TEXT NOT NULL,
        "port"	INTEGER NOT NULL,
        "proxy_protocol"	INTEGER NOT NULL,
        "owner"	TEXT NOT NULL,
        "created_at" TEXT
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        "discord_user_id" TEXT NOT NULL,
        "start_date" TEXT,
        "expire_date" TEXT
    );""")
    con.commit()
    con.close()

def connect_db():
    return sqlite3.connect("database.db")

def is_admin(user_id):
    return str(user_id) in [str(i) for i in config.admin_discord_ids]

@client.event
async def on_ready():
    create_table()
    await client.change_presence(activity=discord.Game(name=f"/백엔드등록"))
    synced = await tree.sync()
    print(f"Synced {len(synced)} commands")
    print(f"{client.user.name} is on ready.")

# ----------- 후원자 SlashCommand -----------

@tree.command(name="후원자", description="후원자 관리 (추가/연장/삭제/help)")
@app_commands.describe(
    action="추가(add), 연장(renew), 삭제(remove), 도움말(help) 중 선택",
    discord_user_id="대상 디스코드 유저 ID (help 제외 필수)",
    days="기간(일) (추가/연장 시 필수)"
)
async def 후원자(
    interaction: discord.Interaction,
    action: str,
    discord_user_id: str = None,
    days: int = None
):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("권한이 없습니다.", ephemeral=True)
        return

    if action == "help":
        help_text = (
            "**후원자 명령어 도움말**\n"
            "`/후원자 <add|renew|remove|help> <디스코드 ID> <기간(일)>`\n"
            "- add: 후원자 등록 (기간 필수)\n"
            "- renew: 후원자 기간 연장 (기간 필수)\n"
            "- remove: 후원자 삭제 (기간 입력 불필요)\n"
            "- help: 도움말 출력\n"
            "※ 관리자만 사용 가능합니다."
        )
        await interaction.response.send_message(help_text, ephemeral=True)
        return

    con = connect_db()
    cur = con.cursor()
    now = datetime.datetime.now()

    if action == "add":
        if not discord_user_id or days is None:
            await interaction.response.send_message("디스코드 ID와 기간(일)을 입력해주세요.", ephemeral=True)
            con.close()
            return
        start_date = now.strftime("%Y-%m-%d %H:%M:%S")
        expire_date = (now + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("SELECT discord_user_id FROM users WHERE discord_user_id = ?", (discord_user_id,))
        if cur.fetchone():
            await interaction.response.send_message("이미 등록된 후원자입니다. 연장하려면 renew를 사용하세요.", ephemeral=True)
        else:
            cur.execute("INSERT INTO users VALUES (?, ?, ?)", (discord_user_id, start_date, expire_date))
            con.commit()
            await interaction.response.send_message(f"후원자 등록 완료: {discord_user_id}, 만료일: {expire_date}", ephemeral=True)
    elif action == "renew":
        if not discord_user_id or days is None:
            await interaction.response.send_message("디스코드 ID와 기간(일)을 입력해주세요.", ephemeral=True)
            con.close()
            return
        cur.execute("SELECT expire_date FROM users WHERE discord_user_id = ?", (discord_user_id,))
        row = cur.fetchone()
        if not row:
            await interaction.response.send_message("등록된 후원자가 아닙니다. 먼저 add로 등록하세요.", ephemeral=True)
        else:
            old_expire = row[0]
            try:
                old_expire_dt = datetime.datetime.strptime(old_expire, "%Y-%m-%d %H:%M:%S")
            except:
                old_expire_dt = now
            new_expire = (max(now, old_expire_dt) + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("UPDATE users SET expire_date = ? WHERE discord_user_id = ?", (new_expire, discord_user_id))
            con.commit()
            await interaction.response.send_message(f"후원자 만료일 연장 완료: {discord_user_id}, 새로운 만료일: {new_expire}", ephemeral=True)
    elif action == "remove":
        if not discord_user_id:
            await interaction.response.send_message("디스코드 ID를 입력해주세요.", ephemeral=True)
            con.close()
            return
        cur.execute("DELETE FROM users WHERE discord_user_id = ?", (discord_user_id,))
        con.commit()
        await interaction.response.send_message(f"후원자 삭제 완료: {discord_user_id}", ephemeral=True)
    else:
        await interaction.response.send_message("action은 add/renew/remove/help 중 하나여야 합니다.", ephemeral=True)
    con.close()

@후원자.autocomplete('action')
async def 후원자_action_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    actions = ["add", "renew", "remove", "help"]
    return [
        app_commands.Choice(name=a, value=a)
        for a in actions if current.lower() in a
    ]

class DomainRegisterModal(discord.ui.Modal, title="도메인 등록"):
    domain = discord.ui.TextInput(label="도메인", required=True)
    backend_name = discord.ui.TextInput(label="백엔드 서버 이름", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("처리 중입니다...", ephemeral=True)

        def has_korean(text):
            return any('\uac00' <= char <= '\ud7af' or '\u3131' <= char <= '\u3163' for char in text)

        if has_korean(self.domain.value):
            await interaction.edit_original_response(content="도메인 이름에는 한국어를 사용할 수 없습니다.")
            return
            
        if has_korean(self.backend_name.value):
            await interaction.edit_original_response(content="백엔드 서버 이름에는 한국어를 사용할 수 없습니다.")
            return
        
        split = self.domain.value.split(" ")
        con = connect_db()
        cur = con.cursor()
        cur.execute("SELECT owner FROM `proxy` WHERE domain = ?", (self.domain.value,))
        data = cur.fetchone()
        con.close()
        if data:
            await interaction.edit_original_response(content="이미 등록된 도메인입니다.")
            return
        else:
            con = connect_db()
            cur = con.cursor()
            cur.execute("SELECT hostname FROM backend WHERE name = ? AND owner = ?", (self.backend_name.value, interaction.user.id,))
            data = cur.fetchone()
            con.close()
            if data:
                if api.create_domain(config.network_name, self.domain.value, self.backend_name.value) == 200:
                    if api.verify_domain(config.network_name, self.domain.value) == 200:
                        con = connect_db()
                        cur = con.cursor()
                        cur.execute("INSERT INTO `proxy` VALUES(?, ?, ?, ?);", (self.domain.value, self.backend_name.value, interaction.user.id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
                        con.commit()
                        con.close()
                        await interaction.edit_original_response(content="성공적으로 등록되었습니다.")
                    else:
                        api.delete_domain(config.network_name, self.domain.value)
                        await interaction.edit_original_response(content="인증된 도메인이 아닙니다. 인증(CNAME 등록) 후 다시 시도해주세요.")
                else:
                    await interaction.edit_original_response(content="오류가 발생했습니다. 명령어를 다시 확인해주세요.")
            else:
                await interaction.edit_original_response(content="존재하지 않거나 본인이 등록하지 않은 백엔드 서버입니다.")

class BackendRegisterModal(discord.ui.Modal, title="백엔드 등록"):
    name = discord.ui.TextInput(label="백엔드 서버 이름", required=True)
    hostname = discord.ui.TextInput(label="아이피/도메인", required=True)
    port = discord.ui.TextInput(label="포트", required=True)
    proxy_protocol = discord.ui.TextInput(label="프록시 프로토콜 여부(on/off)", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("처리 중입니다...", ephemeral=True)
        
        # 한국어 문자 검사
        def has_korean(text):
            return any('\uac00' <= char <= '\ud7af' or '\u3131' <= char <= '\u3163' for char in text)
        
        if has_korean(self.name.value):
            await interaction.edit_original_response(content="백엔드 서버 이름에는 한국어를 사용할 수 없습니다.")
            return
        
        con = connect_db()
        cur = con.cursor()
        cur.execute("SELECT owner FROM `backend` WHERE name = ?", (self.name.value,))
        data = cur.fetchone()
        con.close()
        if data:
            await interaction.edit_original_response(content="등록이 불가능한 백엔드입니다. 고유 이름 중복/블랙리스트 이름 등과 같은 사유가 있을 수 있습니다.")
            return
        else:
            con = connect_db()
            cur = con.cursor()
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("DELETE FROM users WHERE expire_date IS NOT NULL AND expire_date < ?", (now,))
            con.commit()
            cur.execute("SELECT discord_user_id FROM users WHERE discord_user_id = ?", (str(interaction.user.id),))
            sponsor_data = cur.fetchone()
            if sponsor_data:
                max_backend = config.maximum_backend_count_per_sponsor
                max_domain = config.maximum_domain_count_per_sponsor
            else:
                max_backend = config.maximum_backend_count
                max_domain = config.maximum_domain_count
            cur.execute("SELECT COUNT(hostname) FROM `backend` WHERE owner = ?", (interaction.user.id,))
            backend_count_data = cur.fetchone()
            backend_count = int(backend_count_data[0]) if backend_count_data else 0
            cur.execute("SELECT COUNT(domain) FROM `proxy` WHERE owner = ?", (interaction.user.id,))
            domain_count_data = cur.fetchone()
            domain_count = int(domain_count_data[0]) if domain_count_data else 0
            con.close()
            if backend_count >= max_backend:
                await interaction.edit_original_response(content="백엔드 서버 등록 가능 최대 한도를 초과하셨습니다.")
                return
            if domain_count >= max_domain:
                await interaction.edit_original_response(content="도메인 등록 가능 최대 한도를 초과하셨습니다.")
                return
            if self.proxy_protocol.value.lower() not in ["on", "off"]:
                await interaction.edit_original_response(content="Proxy Protocol 여부는 on/off 중으로 작성해주세요.")
                return
            try:
                port = int(self.port.value)
                if port < 1 or port > 65536:
                    await interaction.edit_original_response(content="포트는 1~65535 중으로 선택해주세요.")
                    return
            except:
                await interaction.edit_original_response(content="포트는 1~65535 중으로 선택해주세요.")
                return
            if self.proxy_protocol.value.lower() == "on":
                proxyprotocol = True
                proxy_protocol_status = 1
            elif self.proxy_protocol.value.lower() == "off":
                proxyprotocol = False
                proxy_protocol_status = 0

            if api.create_backend(config.network_name, self.name.value, self.hostname.value, port, proxyprotocol) == 200:
                con = connect_db()
                cur = con.cursor()
                cur.execute("INSERT INTO `backend` VALUES(?, ?, ?, ?, ?, ?);", (self.name.value, self.hostname.value, port, proxy_protocol_status, interaction.user.id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
                con.commit()
                con.close()
                await interaction.edit_original_response(content="백엔드 서버가 성공적으로 생성되었습니다.")
            else:
                await interaction.edit_original_response(content="오류가 발생했습니다. 명령어를 다시 확인해주세요.")

@tree.command(name="도메인등록", description="도메인 등록")
async def 도메인등록(interaction: discord.Interaction):
    await interaction.response.send_modal(DomainRegisterModal())

@tree.command(name="도메인삭제", description="도메인 삭제")
@app_commands.describe(domain="삭제할 도메인")
async def 도메인삭제(interaction: discord.Interaction, domain: str):
    con = connect_db()
    cur = con.cursor()
    cur.execute("SELECT backend FROM proxy WHERE domain = ? AND owner = ?", (domain, interaction.user.id),)
    data = cur.fetchone()
    con.close()
    if data:
        if api.delete_domain(config.network_name, domain) == 200:
            con = connect_db()
            cur = con.cursor()
            cur.execute("DELETE FROM `proxy` WHERE domain = ?;", (domain,))
            con.commit()
            con.close()
            await interaction.response.send_message("성공적으로 삭제되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)
    else:
        await interaction.response.send_message("등록되지 않았거나 본인이 소유하지 않은 도메인입니다.", ephemeral=True)
        return

@tree.command(name="도메인목록", description="도메인 목록")
async def 도메인목록(interaction: discord.Interaction):
    con = connect_db()
    cur = con.cursor()
    cur.execute("SELECT domain FROM proxy WHERE owner = ?", (interaction.user.id,))
    data = cur.fetchall()
    con.close()
    data = [j for i in data for j in i]
    embed = discord.Embed(title="도메인 목록", description="AL CLOUD PROXY에 등록된 도메인 목록을 확인합니다.", color=0x62c1cc)
    for i in data:
        embed.add_field(name="", value=i, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="백엔드등록", description="백엔드 등록")
async def 백엔드등록(interaction: discord.Interaction):
    await interaction.response.send_modal(BackendRegisterModal())

@tree.command(name="백엔드삭제", description="백엔드 삭제")
@app_commands.describe(name="삭제할 백엔드 서버 이름")
async def 백엔드삭제(interaction: discord.Interaction, name: str):
    con = connect_db()
    cur = con.cursor()
    cur.execute("SELECT hostname FROM `backend` WHERE name = ? AND owner = ?", (name, interaction.user.id),)
    data = cur.fetchone()
    con.close()
    if data:
        if api.delete_backend(config.network_name, name) == 200:
            con = connect_db()
            cur = con.cursor()
            cur.execute("DELETE FROM `backend` WHERE name = ?;", (name,))
            con.commit()
            con.close()
            await interaction.response.send_message("성공적으로 삭제되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)
    else:
        await interaction.response.send_message("등록되지 않았거나 본인이 소유하지 않은 백엔드 서버입니다.", ephemeral=True)
        return

@tree.command(name="백엔드목록", description="백엔드 목록")
async def 백엔드목록(interaction: discord.Interaction):
    con = connect_db()
    cur = con.cursor()
    cur.execute("SELECT name,hostname,port,proxy_protocol FROM `backend` WHERE owner = ?", (interaction.user.id,))
    data = cur.fetchall()
    con.close()
    embed = discord.Embed(title="백엔드 서버 목록", description="AL CLOUD PROXY에 등록된 백엔드 서버 목록을 확인합니다.", color=0x62c1cc)
    for i in data:
        name, hostname, port, proxyprotocol_status = i
        if proxyprotocol_status == 0:
            proxy_protocol = "off"
        if proxyprotocol_status == 1:
            proxy_protocol = "on"
        embed.add_field(name=name, value=f"{hostname}:{port} - Proxy Protocol: {proxy_protocol}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

client.run(config.bot_token)