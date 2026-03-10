import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import asyncio
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_duration(value: str) -> timedelta | None:
    """
    Aceita formatos como: 30m, 2h, 1h30m, 90m, 24h
    Retorna timedelta ou None se inválido.
    """
    value = value.strip().lower()
    hours = 0
    minutes = 0

    # tenta 1h30m
    import re
    match = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?', value)
    if not match or not match.group(0):
        return None

    h_part = match.group(1)
    m_part = match.group(2)

    if h_part:
        hours = int(h_part)
    if m_part:
        minutes = int(m_part)

    if hours == 0 and minutes == 0:
        return None

    return timedelta(hours=hours, minutes=minutes)


def format_duration(td: timedelta) -> str:
    """Formata um timedelta de volta para string legível."""
    total_minutes = int(td.total_seconds() // 60)
    h = total_minutes // 60
    m = total_minutes % 60
    if h and m:
        return f"{h}h{m}m"
    elif h:
        return f"{h}h"
    else:
        return f"{m}m"


def build_bar(votes: int, total: int, length: int = 12) -> str:
    filled = round((votes / total) * length) if total > 0 else 0
    return "█" * filled + "░" * (length - filled)


def build_embed(poll: dict) -> discord.Embed:
    config    = poll.get("config", {})
    options   = poll.get("options", [])
    votes_map = poll.get("votes_map", {})
    closed    = poll.get("closed", False)
    total     = len(votes_map)

    color = config.get("embed_color", 0x57F287)
    embed = discord.Embed(
        title=config.get("embed_title", "📊 Votação"),
        color=color
    )

    counts = [0] * len(options)
    for opt_idx in votes_map.values():
        if 0 <= opt_idx < len(counts):
            counts[opt_idx] += 1

    results_lines = []
    for i, opt in enumerate(options):
        pct = round((counts[i] / total) * 100) if total > 0 else 0
        bar = build_bar(counts[i], total)
        results_lines.append(f"**{opt}**\n{bar} {counts[i]} voto(s) ({pct}%)")

    embed.add_field(
        name="Opções",
        value="\n\n".join(results_lines) if results_lines else "*Nenhuma opção*",
        inline=False
    )
    embed.add_field(name="Total de votos", value=str(total), inline=True)

    if closed:
        embed.add_field(name="Status", value="🔒 Encerrada", inline=True)
        if counts and total > 0:
            winner_idx = counts.index(max(counts))
            embed.add_field(name="🏆 Vencedor", value=options[winner_idx], inline=False)
    else:
        ends_at = poll.get("ends_at")
        if ends_at:
            ts = int(ends_at.timestamp())
            embed.add_field(name="Encerra em", value=f"<t:{ts}:R>", inline=True)

    embed.set_footer(text=f"Criada por {config.get('created_by', '?')}")

    image = config.get("embed_image")
    if image:
        embed.set_image(url=image)

    return embed


# ── View dos botões de voto (PERSISTENTE) ──────────────────────────────────────

VOTE_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

class VoteView(View):
    def __init__(self, cog, poll_id: str, options: list, closed: bool = False):
        super().__init__(timeout=None)
        self.cog     = cog
        self.poll_id = poll_id

        for i, opt in enumerate(options):
            btn = Button(
                label=opt[:80],
                emoji=VOTE_EMOJIS[i] if i < len(VOTE_EMOJIS) else "🗳️",
                style=discord.ButtonStyle.success if not closed else discord.ButtonStyle.secondary,
                custom_id=f"vote:{poll_id}:{i}",
                disabled=closed,
                row=i // 3
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            await self.cog.handle_vote(interaction, self.poll_id, idx)
        return callback


# ── Modal único de criação ─────────────────────────────────────────────────────

class CreatePollModal(Modal, title="Criar Votação"):

    poll_title = TextInput(
        label="Título da votação",
        placeholder="Ex: Qual a melhor linguagem?",
        required=True,
        max_length=100
    )
    poll_options = TextInput(
        label="Opções (uma por linha, mín. 2, máx. 5)",
        placeholder="Python\nJavaScript\nRust\nGo",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=300
    )
    poll_duration = TextInput(
        label="Duração  —  ex: 30m  |  2h  |  1h30m",
        placeholder="1h",
        required=True,
        max_length=10
    )
    poll_color = TextInput(
        label="Cor do embed em hex (padrão: 57F287)",
        placeholder="57F287",
        required=False,
        max_length=7
    )
    poll_image = TextInput(
        label="URL da imagem (opcional)",
        placeholder="https://exemplo.com/banner.png",
        required=False,
        max_length=300
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        # Valida opções
        options = [o.strip() for o in self.poll_options.value.splitlines() if o.strip()]
        if len(options) < 2:
            await interaction.response.send_message("❌ Informe pelo menos **2 opções**.", ephemeral=True)
            return
        if len(options) > 5:
            await interaction.response.send_message("❌ Máximo de **5 opções** permitido.", ephemeral=True)
            return

        # Valida duração
        td = parse_duration(self.poll_duration.value)
        if td is None:
            await interaction.response.send_message(
                "❌ Duração inválida! Use o formato `30m`, `2h` ou `1h30m`.", ephemeral=True
            )
            return

        # Valida cor
        color = 0x57F287
        raw_color = self.poll_color.value.strip().replace("#", "")
        if raw_color:
            try:
                color = int(raw_color, 16)
            except ValueError:
                await interaction.response.send_message("❌ Cor inválida! Use formato hex (ex: FF5733).", ephemeral=True)
                return

        # Valida imagem
        image = self.poll_image.value.strip() or None

        ends_at = datetime.utcnow() + td

        config = {
            "embed_title":  self.poll_title.value.strip(),
            "embed_color":  color,
            "embed_image":  image,
            "created_by":   interaction.user.display_name,
            "duration_str": format_duration(td)
        }

        await self.cog.create_poll(interaction, config, options, ends_at)


# ── Cog principal ──────────────────────────────────────────────────────────────

class Votacao(commands.Cog):
    def __init__(self, bot):
        self.bot             = bot
        self.mongo_uri       = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name         = "discord_bot"
        self.collection_name = "votacoes"
        self.client          = None
        self.collection      = None
        self._timers: dict   = {}

        self.connect_mongo()

    async def cog_load(self):
        self.bot.loop.create_task(self.restore_polls())

    def connect_mongo(self):
        try:
            self.client     = MongoClient(self.mongo_uri)
            self.collection = self.client[self.db_name][self.collection_name]
            self.client.admin.command('ping')
            print("✅ [Votação] Conectado ao MongoDB com sucesso.")
        except ConnectionFailure:
            print("❌ [Votação] Erro ao conectar ao MongoDB.")
            self.client     = None
            self.collection = None

    # ── Restauração após reinício ──────────────────────────────────────────────

    async def restore_polls(self):
        await self.bot.wait_until_ready()
        if self.collection is None:
            return

        open_polls = list(self.collection.find({"closed": False}))
        for poll in open_polls:
            poll_id = str(poll["_id"])
            options = poll.get("options", [])

            view = VoteView(self, poll_id, options, closed=False)
            self.bot.add_view(view)

            ends_at = poll.get("ends_at")
            if ends_at:
                delay = (ends_at - datetime.utcnow()).total_seconds()
                if delay > 0:
                    task = self.bot.loop.create_task(self._close_after(poll_id, delay))
                    self._timers[poll_id] = task
                else:
                    await self.close_poll(poll_id)

        print(f"🔄 [Votação] {len(open_polls)} votação(ões) restaurada(s).")

    # ── Criar votação ──────────────────────────────────────────────────────────

    async def create_poll(self, interaction, config, options, ends_at):
        poll_doc = {
            "guild_id":   str(interaction.guild_id),
            "channel_id": str(interaction.channel_id),
            "message_id": None,
            "config":     config,
            "options":    options,
            "votes_map":  {},
            "ends_at":    ends_at,
            "closed":     False,
            "created_at": datetime.utcnow()
        }

        if self.collection is not None:
            result  = self.collection.insert_one(poll_doc)
            poll_id = str(result.inserted_id)
        else:
            poll_id = str(uuid.uuid4())

        poll_doc["_id"] = poll_id

        view  = VoteView(self, poll_id, options)
        embed = build_embed(poll_doc)

        await interaction.response.send_message("✅ Votação criada!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        if self.collection is not None:
            self.collection.update_one(
                {"_id": ObjectId(poll_id)},
                {"$set": {"message_id": str(msg.id)}}
            )

        delay = (ends_at - datetime.utcnow()).total_seconds()
        task  = self.bot.loop.create_task(self._close_after(poll_id, delay))
        self._timers[poll_id] = task

    # ── Registrar voto ─────────────────────────────────────────────────────────

    async def handle_vote(self, interaction: discord.Interaction, poll_id: str, option_idx: int):
        if self.collection is None:
            await interaction.response.send_message("❌ Banco de dados indisponível.", ephemeral=True)
            return

        try:
            oid = ObjectId(poll_id)
        except Exception:
            await interaction.response.send_message("❌ Votação inválida.", ephemeral=True)
            return

        poll = self.collection.find_one({"_id": oid})
        if not poll:
            await interaction.response.send_message("❌ Votação não encontrada.", ephemeral=True)
            return
        if poll.get("closed"):
            await interaction.response.send_message("🔒 Esta votação já foi encerrada.", ephemeral=True)
            return

        user_id   = str(interaction.user.id)
        votes_map = poll.get("votes_map", {})
        options   = poll.get("options", [])

        # Clicou na mesma opção que já votou — ignora
        if votes_map.get(user_id) == option_idx:
            await interaction.response.send_message(
                f"⚠️ Você já votou em **{options[option_idx]}**!",
                ephemeral=True
            )
            return

        # Registra ou troca o voto
        previous = votes_map.get(user_id)
        votes_map[user_id] = option_idx
        self.collection.update_one({"_id": oid}, {"$set": {"votes_map": votes_map}})

        poll["votes_map"] = votes_map
        embed = build_embed(poll)

        if previous is not None:
            msg = f"🔄 Voto alterado de **{options[previous]}** para **{options[option_idx]}**!"
        else:
            msg = f"✅ Voto registrado em **{options[option_idx]}**!"

        try:
            await interaction.response.edit_message(embed=embed)
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            await interaction.response.send_message(msg, ephemeral=True)

    # ── Encerramento ───────────────────────────────────────────────────────────

    async def _close_after(self, poll_id: str, delay: float):
        await asyncio.sleep(delay)
        await self.close_poll(poll_id)

    async def close_poll(self, poll_id: str):
        if self.collection is None:
            return
        try:
            oid = ObjectId(poll_id)
        except Exception:
            return

        poll = self.collection.find_one({"_id": oid})
        if not poll or poll.get("closed"):
            return

        self.collection.update_one({"_id": oid}, {"$set": {"closed": True}})
        poll["closed"] = True

        channel_id = int(poll.get("channel_id", 0))
        message_id = int(poll.get("message_id", 0))
        channel    = self.bot.get_channel(channel_id)

        if channel and message_id:
            try:
                msg         = await channel.fetch_message(message_id)
                closed_view = VoteView(self, poll_id, poll.get("options", []), closed=True)
                embed       = build_embed(poll)
                await msg.edit(embed=embed, view=closed_view)
                await channel.send(
                    f"🔒 A votação **{poll['config'].get('embed_title', '')}** foi encerrada!"
                )
            except Exception as e:
                print(f"[Votação] Erro ao encerrar {poll_id}: {e}")

        self._timers.pop(poll_id, None)

    # ── Comandos slash ─────────────────────────────────────────────────────────

    @app_commands.command(name="votar", description="Cria uma nova votação (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def votar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreatePollModal(self))

    @app_commands.command(name="encerrar_votacao", description="Encerra uma votação manualmente (Admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(poll_id="ID da votação")
    async def encerrar_votacao(self, interaction: discord.Interaction, poll_id: str):
        if self.collection is None:
            await interaction.response.send_message("❌ Banco de dados indisponível.", ephemeral=True)
            return
        try:
            oid = ObjectId(poll_id)
        except Exception:
            await interaction.response.send_message("❌ ID inválido.", ephemeral=True)
            return

        poll = self.collection.find_one({"_id": oid})
        if not poll:
            await interaction.response.send_message("❌ Votação não encontrada.", ephemeral=True)
            return
        if poll.get("closed"):
            await interaction.response.send_message("⚠️ Essa votação já foi encerrada.", ephemeral=True)
            return
        if str(poll.get("guild_id")) != str(interaction.guild_id):
            await interaction.response.send_message("❌ Essa votação não pertence a este servidor.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Encerrando votação...", ephemeral=True)
        task = self._timers.pop(poll_id, None)
        if task:
            task.cancel()
        await self.close_poll(poll_id)

    @app_commands.command(name="resultado_votacao", description="Mostra o resultado atual de uma votação (Admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(poll_id="ID da votação")
    async def resultado_votacao(self, interaction: discord.Interaction, poll_id: str):
        if self.collection is None:
            await interaction.response.send_message("❌ Banco de dados indisponível.", ephemeral=True)
            return
        try:
            oid = ObjectId(poll_id)
        except Exception:
            await interaction.response.send_message("❌ ID inválido.", ephemeral=True)
            return

        poll = self.collection.find_one({"_id": oid})
        if not poll:
            await interaction.response.send_message("❌ Votação não encontrada.", ephemeral=True)
            return
        if str(poll.get("guild_id")) != str(interaction.guild_id):
            await interaction.response.send_message("❌ Essa votação não pertence a este servidor.", ephemeral=True)
            return

        embed = build_embed(poll)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Votacao(bot))