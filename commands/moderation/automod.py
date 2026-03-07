import discord
from discord import app_commands, Interaction, Embed, Colour, SelectOption, Message
from discord.ext import commands, tasks
from discord.ui import Select, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from collections import defaultdict, deque
import datetime
import re
import logging

logger = logging.getLogger(__name__)

class AutoModConfig:
    def __init__(self):
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.collection_name = "automod_configs"
        self.client = None
        self.collection = None
        self.connect_mongo()

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.collection = self.client[self.db_name][self.collection_name]
            self.client.admin.command('ping')
            print("Conectado ao MongoDB para Auto-Mod.")
        except ConnectionFailure:
            print("Erro ao conectar ao MongoDB para Auto-Mod. Usando valores padrão.")
            self.client = None
            self.collection = None

    def get_guild_config(self, guild_id: int) -> dict:
        str_id = str(guild_id)
        if self.collection is not None:
            doc = self.collection.find_one({"_id": str_id})
            if not doc:
                doc = {
                    "_id": str_id,
                    'enabled': False,
                    'banned_words': [],
                    'caps_threshold': 70,
                    'repeat_threshold': 3,
                    'action': 'delete'
                }
                self.collection.insert_one(doc)
            return doc
        else:
            return {
                'enabled': False,
                'banned_words': [],
                'caps_threshold': 70,
                'repeat_threshold': 3,
                'action': 'delete'
            }

    def save_guild_config(self, guild_id: int, config: dict):
        if self.collection is not None:
            self.collection.replace_one({"_id": str(guild_id)}, {"_id": str(guild_id), **config}, upsert=True)

class AutoModModal(Modal):
    def __init__(self, view: 'AutoModView', config: dict):
        super().__init__(title="Configurar Auto-Mod")
        self.view = view
        self.config = config

        banned = ','.join(self.config['banned_words'])
        self.add_item(TextInput(label="Palavras Proibidas (separadas por vírgula)", default=banned, style=discord.TextStyle.paragraph, required=False))  # Alterado para paragraph
        self.add_item(TextInput(label="Limite de Caps (%)", default=str(self.config['caps_threshold']), required=True))
        self.add_item(TextInput(label="Limite de Repetição", default=str(self.config['repeat_threshold']), required=True))
        self.add_item(TextInput(label="Ação (delete/warn/mute)", default=self.config['action'], required=True))

    async def on_submit(self, interaction: Interaction):
        try:
            words = [w.strip().lower() for w in self.children[0].value.split(',') if w.strip()]
            self.config['banned_words'] = words
            self.config['caps_threshold'] = int(self.children[1].value)
            self.config['repeat_threshold'] = int(self.children[2].value)
            action = self.children[3].value.lower()
            if action not in ['delete', 'warn', 'mute']:
                raise ValueError("Ação inválida")
            self.config['action'] = action

            self.view.automod_config.save_guild_config(self.view.original_interaction.guild_id, self.view.guild_config)
            await interaction.response.defer()
            await self.view.update_preview()
        except ValueError as e:
            await interaction.response.send_message(f"Erro: {str(e)}. Tente novamente.", ephemeral=True)

class AutoModView(View):
    def __init__(self, interaction: Interaction, automod_config: AutoModConfig):
        super().__init__(timeout=1800)
        self.original_interaction = interaction
        self.preview_message = None
        self.automod_config = automod_config
        self.guild_config = automod_config.get_guild_config(interaction.guild_id)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    async def update_preview(self):
        embed = Embed(title="Configurações de Auto-Mod", color=discord.Color.from_str("#1A1A1A"))
        status = "Ativado" if self.guild_config['enabled'] else "Desativado"
        details = [
            f"Palavras proibidas: {', '.join(self.guild_config['banned_words']) or 'Nenhuma'}",
            f"Limite de Caps: {self.guild_config['caps_threshold']}%",
            f"Limite de Repetição: {self.guild_config['repeat_threshold']}",
            f"Ação: {self.guild_config['action']}"
        ]
        embed.add_field(name=f"Auto-Mod ({status})", value='\n'.join(details), inline=False)

        if self.preview_message:
            await self.preview_message.edit(embed=embed, view=self)
        else:
            self.preview_message = await self.original_interaction.followup.send(embed=embed, view=self, ephemeral=True)

    @discord.ui.select(
        placeholder="Escolha uma opção...",
        options=[
            SelectOption(label="Editar Configurações", value="edit"),
            SelectOption(label="Ativar/Desativar Auto-Mod", value="toggle"),
        ],
        row=0
    )
    async def action_select(self, interaction: Interaction, select: Select):
        choice = select.values[0]
        if choice == "edit":
            modal = AutoModModal(self, self.guild_config)
            await interaction.response.send_modal(modal)
        elif choice == "toggle":
            self.guild_config['enabled'] = not self.guild_config['enabled']
            self.automod_config.save_guild_config(self.original_interaction.guild_id, self.guild_config)
            await interaction.response.defer()
            await self.update_preview()

    @discord.ui.button(label="Salvar e Sair", style=discord.ButtonStyle.green, row=1)
    async def save_exit(self, interaction: Interaction, button):
        self.automod_config.save_guild_config(self.original_interaction.guild_id, self.guild_config)
        await interaction.response.send_message("Configurações salvas!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, row=1)
    async def cancel(self, interaction: Interaction, button):
        await interaction.response.send_message("Configuração cancelada.", ephemeral=True)
        self.stop()

class AutoModCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.automod_config = AutoModConfig()
        self.repeat_tracker = defaultdict(lambda: defaultdict(deque))  # guild -> user -> deque de (timestamp, message)
        self.warn_tracker = defaultdict(lambda: defaultdict(int))  # guild -> user -> count de warns

    @tasks.loop(hours=24)  # Resetar warns a cada 24h
    async def reset_warns(self):
        self.warn_tracker.clear()
        logger.info("[DEBUG] Warns resetados globalmente.")

    @app_commands.command(name="automod", description="Configura o sistema de auto-moderação do servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod(self, interaction: Interaction):
        view = AutoModView(interaction, self.automod_config)
        await interaction.response.send_message("Iniciando configuração de auto-mod...", ephemeral=True)
        await view.update_preview()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild:
            return
        guild_id = message.guild.id
        config = self.automod_config.get_guild_config(guild_id)
        if not config['enabled']:
            return

        content = message.content.lower()
        user_id = message.author.id
        now = datetime.datetime.utcnow()

        # Filtro de Palavras Proibidas
        if config['banned_words']:
            if any(word in content for word in config['banned_words']):
                await self.apply_action(message, config['action'], "Palavra proibida detectada")
                return

        # Filtro de Caps
        letters = [c for c in message.content if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters) * 100
            if caps_ratio > config['caps_threshold']:
                await self.apply_action(message, config['action'], "Caps excessivo detectado")
                return

        # Filtro de Repetição
        self.repeat_tracker[guild_id][user_id].append((now, content))
        # Manter apenas as últimas mensagens
        while len(self.repeat_tracker[guild_id][user_id]) > config['repeat_threshold']:
            self.repeat_tracker[guild_id][user_id].popleft()
        # Verificar se todas as mensagens recentes são iguais
        if len(self.repeat_tracker[guild_id][user_id]) >= config['repeat_threshold']:
            recent_messages = [msg for _, msg in self.repeat_tracker[guild_id][user_id]]
            if all(msg == recent_messages[0] for msg in recent_messages):
                await self.apply_action(message, config['action'], "Repetição detectada")
                return

    async def apply_action(self, message: Message, action: str, reason: str):
        user = message.author
        guild = message.guild
        try:
            if action == 'delete':
                await message.delete()
                logger.info(f"[DEBUG] Mensagem deletada por {reason} em {guild.name}.")
            elif action == 'warn':
                warn_count = self.warn_tracker[guild.id][user.id]
                if warn_count >= 2:
                    # Mute por 1h após 2 warns
                    try:
                        await user.timeout(datetime.timedelta(hours=1), reason=f"Auto-Mod: {reason} - Warns excedidos")
                        await message.channel.send(f"{user.mention}, você foi mutado por 1 hora devido a warns excedidos!", delete_after=10)
                        self.warn_tracker[guild.id][user.id] = 0  # Resetar warns após mute
                        logger.info(f"[DEBUG] Usuário {user} mutado por 1h (warns excedidos) em {guild.name}.")
                    except discord.Forbidden:
                        mute_role = discord.utils.get(guild.roles, name="Muted")
                        if mute_role:
                            await user.add_roles(mute_role, reason=f"Auto-Mod: {reason} - Warns excedidos")
                            await message.channel.send(f"{user.mention}, você foi mutado devido a warns excedidos!", delete_after=10)
                            self.warn_tracker[guild.id][user.id] = 0
                            logger.info(f"[DEBUG] Usuário {user} mutado via role (warns excedidos) em {guild.name}.")
                        else:
                            await message.channel.send(f"{user.mention}, erro: não foi possível mutar!", delete_after=5)
                else:
                    self.warn_tracker[guild.id][user.id] += 1
                    await message.channel.send(f"{user.mention}, aviso ({self.warn_tracker[guild.id][user.id]}/2): {reason}!", delete_after=10)
                    logger.info(f"[DEBUG] Warn {self.warn_tracker[guild.id][user.id]}/2 enviado para {user} em {guild.name}.")
            elif action == 'mute':
                try:
                    await user.timeout(datetime.timedelta(hours=1), reason=f"Auto-Mod: {reason}")
                    logger.info(f"[DEBUG] Usuário {user} mutado por 1h em {guild.name}.")
                except discord.Forbidden:
                    mute_role = discord.utils.get(guild.roles, name="Muted")
                    if mute_role:
                        await user.add_roles(mute_role, reason=f"Auto-Mod: {reason}")
                        logger.info(f"[DEBUG] Usuário {user} mutado via role em {guild.name}.")
                    else:
                        await message.channel.send(f"{user.mention}, erro: não foi possível mutar!", delete_after=5)
        except discord.Forbidden:
            logger.warning(f"[DEBUG] Sem permissão para aplicar ação em {guild.name}.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModCog(bot))