import discord
from discord import app_commands, Interaction, Embed, Colour, SelectOption, Message
from discord.ext import commands, tasks
from discord.ui import Select, View, Modal, TextInput
import asyncio
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from collections import defaultdict, deque
import datetime
import re
import logging  # Adicionado para logs de debug

logger = logging.getLogger(__name__)  # Para logs

class SecurityConfig:
    def __init__(self):
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.collection_name = "security_configs"
        self.client = None
        self.collection = None
        self.connect_mongo()

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.collection = self.client[self.db_name][self.collection_name]
            self.client.admin.command('ping')
            print("Conectado ao MongoDB com sucesso.")
        except ConnectionFailure:
            print("Erro ao conectar ao MongoDB. Usando valores padrão.")
            self.client = None
            self.collection = None

    def get_guild_config(self, guild_id: int) -> dict:
        str_id = str(guild_id)
        if self.collection is not None:
            doc = self.collection.find_one({"_id": str_id})
            if not doc:
                doc = {
                    "_id": str_id,
                    'anti_raid': {'enabled': False, 'join_threshold': 5, 'time_window': 60, 'action': 'ban'},
                    'anti_links': {'enabled': False, 'allowed_domains': [], 'action': 'delete'},
                    'anti_spam': {'enabled': False, 'message_threshold': 5, 'time_window': 10, 'action': 'mute'},
                    'anti_nuke': {'enabled': False, 'change_threshold': 3, 'time_window': 60, 'action': 'ban'}
                }
                self.collection.insert_one(doc)
            return doc
        else:
            return {
                'anti_raid': {'enabled': False, 'join_threshold': 5, 'time_window': 60, 'action': 'ban'},
                'anti_links': {'enabled': False, 'allowed_domains': [], 'action': 'delete'},
                'anti_spam': {'enabled': False, 'message_threshold': 5, 'time_window': 10, 'action': 'mute'},
                'anti_nuke': {'enabled': False, 'change_threshold': 3, 'time_window': 60, 'action': 'ban'}
            }

    def save_guild_config(self, guild_id: int, config: dict):
        if self.collection is not None:
            self.collection.replace_one({"_id": str(guild_id)}, {"_id": str(guild_id), **config}, upsert=True)

class SecurityModal(Modal):
    def __init__(self, view: 'SecurityView', feature: str, config: dict):
        super().__init__(title=f"Configurar {feature.replace('_', ' ').title()}")
        self.view = view
        self.feature = feature
        self.config = config[feature]

        if feature == 'anti_raid':
            self.add_item(TextInput(label="Limite de Joins (ex: 5)", default=str(self.config['join_threshold']), required=True))
            self.add_item(TextInput(label="Janela de Tempo (segundos)", default=str(self.config['time_window']), required=True))
            self.add_item(TextInput(label="Ação (ban/kick/mute)", default=self.config['action'], required=True))
        elif feature == 'anti_links':
            allowed = ','.join(self.config['allowed_domains'])
            self.add_item(TextInput(label="Domínios Permitidos (separados por vírgula)", default=allowed, required=False))
            self.add_item(TextInput(label="Ação (delete/warn)", default=self.config['action'], required=True))
        elif feature == 'anti_spam':
            self.add_item(TextInput(label="Limite de Mensagens", default=str(self.config['message_threshold']), required=True))
            self.add_item(TextInput(label="Janela de Tempo (segundos)", default=str(self.config['time_window']), required=True))
            self.add_item(TextInput(label="Ação (mute/delete)", default=self.config['action'], required=True))
        elif feature == 'anti_nuke':
            self.add_item(TextInput(label="Limite de Mudanças", default=str(self.config['change_threshold']), required=True))
            self.add_item(TextInput(label="Janela de Tempo (segundos)", default=str(self.config['time_window']), required=True))
            self.add_item(TextInput(label="Ação (ban/kick)", default=self.config['action'], required=True))

    async def on_submit(self, interaction: Interaction):
        try:
            if self.feature == 'anti_raid':
                self.config['join_threshold'] = int(self.children[0].value)
                self.config['time_window'] = int(self.children[1].value)
                action = self.children[2].value.lower()
                if action not in ['ban', 'kick', 'mute']:
                    raise ValueError("Ação inválida")
                self.config['action'] = action
            elif self.feature == 'anti_links':
                domains = [d.strip() for d in self.children[0].value.split(',') if d.strip()]
                self.config['allowed_domains'] = domains
                action = self.children[1].value.lower()
                if action not in ['delete', 'warn']:
                    raise ValueError("Ação inválida")
                self.config['action'] = action
            elif self.feature == 'anti_spam':
                self.config['message_threshold'] = int(self.children[0].value)
                self.config['time_window'] = int(self.children[1].value)
                action = self.children[2].value.lower()
                if action not in ['mute', 'delete']:
                    raise ValueError("Ação inválida")
                self.config['action'] = action
            elif self.feature == 'anti_nuke':
                self.config['change_threshold'] = int(self.children[0].value)
                self.config['time_window'] = int(self.children[1].value)
                action = self.children[2].value.lower()
                if action not in ['ban', 'kick']:
                    raise ValueError("Ação inválida")
                self.config['action'] = action

            self.view.security_config.save_guild_config(self.view.original_interaction.guild_id, self.view.guild_config)
            await interaction.response.defer()
            await self.view.update_preview()
        except ValueError as e:
            await interaction.response.send_message(f"Erro: {str(e)}. Tente novamente.", ephemeral=True)

class SecurityView(View):
    def __init__(self, interaction: Interaction, security_config: SecurityConfig):
        super().__init__(timeout=1800)
        self.original_interaction = interaction
        self.preview_message = None
        self.security_config = security_config
        self.guild_config = security_config.get_guild_config(interaction.guild_id)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    async def update_preview(self):
        embed = Embed(title="Configurações de Segurança", color=Colour.red())
        for feature, conf in self.guild_config.items():
            if feature == "_id":
                continue
            status = "Ativado" if conf['enabled'] else "Desativado"
            details = []
            if feature == 'anti_raid':
                details = [f"Limite: {conf['join_threshold']} joins em {conf['time_window']}s", f"Ação: {conf['action']}"]
            elif feature == 'anti_links':
                details = [f"Domínios permitidos: {', '.join(conf['allowed_domains']) or 'Nenhum'}", f"Ação: {conf['action']}"]
            elif feature == 'anti_spam':
                details = [f"Limite: {conf['message_threshold']} msgs em {conf['time_window']}s", f"Ação: {conf['action']}"]
            elif feature == 'anti_nuke':
                details = [f"Limite: {conf['change_threshold']} mudanças em {conf['time_window']}s", f"Ação: {conf['action']}"]
            embed.add_field(name=f"{feature.replace('_', ' ').title()} ({status})", value='\n'.join(details) or "Padrão", inline=False)

        if self.preview_message:
            await self.preview_message.edit(embed=embed, view=self)
        else:
            self.preview_message = await self.original_interaction.followup.send(embed=embed, view=self, ephemeral=True)

    @discord.ui.select(
        placeholder="Selecione um recurso para configurar...",
        options=[
            SelectOption(label="Anti-Raid", value="anti_raid"),
            SelectOption(label="Anti-Links", value="anti_links"),
            SelectOption(label="Anti-Spam", value="anti_spam"),
            SelectOption(label="Anti-Nuke", value="anti_nuke"),
        ],
        row=0
    )
    async def config_select(self, interaction: Interaction, select: Select):
        selected = select.values[0]
        modal = SecurityModal(self, selected, self.guild_config)
        await interaction.response.send_modal(modal)

    @discord.ui.select(
        placeholder="Escolha o recurso para ativar/desativar...",
        options=[
            SelectOption(label="Anti-Raid", value="anti_raid"),
            SelectOption(label="Anti-Links", value="anti_links"),
            SelectOption(label="Anti-Spam", value="anti_spam"),
            SelectOption(label="Anti-Nuke", value="anti_nuke"),
        ],
        row=1
    )
    async def toggle_select(self, interaction: Interaction, select: Select):
        feat = select.values[0]
        self.guild_config[feat]['enabled'] = not self.guild_config[feat]['enabled']
        self.security_config.save_guild_config(self.original_interaction.guild_id, self.guild_config)
        await interaction.response.defer()
        await self.update_preview()

    @discord.ui.button(label="Salvar e Sair", style=discord.ButtonStyle.green, row=2)
    async def save_exit(self, interaction: Interaction, button):
        self.security_config.save_guild_config(self.original_interaction.guild_id, self.guild_config)
        await interaction.response.send_message("Configurações salvas!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, interaction: Interaction, button):
        await interaction.response.send_message("Configuração cancelada.", ephemeral=True)
        self.stop()

class SecurityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.security_config = SecurityConfig()
        self.join_tracker = defaultdict(deque)  # Para anti-raid: deque de timestamps
        self.message_tracker = defaultdict(lambda: defaultdict(deque))  # Para anti-spam: guild -> user -> deque de timestamps
        self.nuke_tracker = defaultdict(lambda: defaultdict(deque))  # Para anti-nuke: guild -> user -> deque de (timestamp, action)
        self.clean_trackers.start()

    @tasks.loop(minutes=5)
    async def clean_trackers(self):
        now = datetime.datetime.utcnow()
        cutoff = datetime.timedelta(minutes=10)
        for guild_id in list(self.join_tracker.keys()):
            while self.join_tracker[guild_id] and now - self.join_tracker[guild_id][0] > cutoff:
                self.join_tracker[guild_id].popleft()
            if not self.join_tracker[guild_id]:
                del self.join_tracker[guild_id]

        for guild_id in list(self.message_tracker.keys()):
            for user_id in list(self.message_tracker[guild_id].keys()):
                while self.message_tracker[guild_id][user_id] and now - self.message_tracker[guild_id][user_id][0] > cutoff:
                    self.message_tracker[guild_id][user_id].popleft()
                if not self.message_tracker[guild_id][user_id]:
                    del self.message_tracker[guild_id][user_id]
            if not self.message_tracker[guild_id]:
                del self.message_tracker[guild_id]

        for guild_id in list(self.nuke_tracker.keys()):
            for user_id in list(self.nuke_tracker[guild_id].keys()):
                while self.nuke_tracker[guild_id][user_id] and now - self.nuke_tracker[guild_id][user_id][0][0] > cutoff:
                    self.nuke_tracker[guild_id][user_id].popleft()
                if not self.nuke_tracker[guild_id][user_id]:
                    del self.nuke_tracker[guild_id][user_id]
            if not self.nuke_tracker[guild_id]:
                del self.nuke_tracker[guild_id]

    @app_commands.command(name="security", description="Configura o sistema de segurança do servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def security(self, interaction: Interaction):
        view = SecurityView(interaction, self.security_config)
        await interaction.response.send_message("Iniciando configuração de segurança...", ephemeral=True)
        await view.update_preview()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = self.security_config.get_guild_config(member.guild.id)['anti_raid']
        if not config['enabled']:
            return

        now = datetime.datetime.utcnow()
        guild_id = member.guild.id
        self.join_tracker[guild_id].append(now)

        # Contar joins na janela
        window_start = now - datetime.timedelta(seconds=config['time_window'])
        recent_joins = sum(1 for t in self.join_tracker[guild_id] if t >= window_start)

        if recent_joins >= config['join_threshold']:
            # Ação: banir/kick/mute os membros recentes
            recent_members = [m for m in member.guild.members if m.joined_at and (now - m.joined_at) < datetime.timedelta(seconds=config['time_window'])]
            for m in recent_members[-config['join_threshold']:]:
                try:
                    if config['action'] == 'ban':
                        await m.ban(reason="Anti-Raid: Join em massa detectado")
                    elif config['action'] == 'kick':
                        await m.kick(reason="Anti-Raid: Join em massa detectado")
                    elif config['action'] == 'mute':
                        mute_role = discord.utils.get(member.guild.roles, name="Muted")
                        if mute_role:
                            await m.add_roles(mute_role, reason="Anti-Raid: Join em massa detectado")
                except discord.Forbidden:
                    pass  # Bot sem permissões

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild:
            return
        guild_id = message.guild.id
        config = self.security_config.get_guild_config(guild_id)

        # Anti-Links
        if config['anti_links']['enabled']:
            url_pattern = re.compile(r'https?://[^\s]+')
            urls = url_pattern.findall(message.content)
            if urls:
                allowed = config['anti_links']['allowed_domains']
                if not any(any(domain in url for domain in allowed) for url in urls):
                    try:
                        if config['anti_links']['action'] == 'delete':
                            await message.delete()
                            await message.channel.send(f"{message.author.mention}, links não permitidos aqui!", delete_after=5)
                        elif config['anti_links']['action'] == 'warn':
                            await message.channel.send(f"{message.author.mention}, aviso: links não permitidos!")
                    except discord.Forbidden:
                        pass

        # Anti-Spam
        if config['anti_spam']['enabled']:
            user_id = message.author.id
            now = datetime.datetime.utcnow()
            self.message_tracker[guild_id][user_id].append(now)

            # Contar mensagens na janela
            window_start = now - datetime.timedelta(seconds=config['anti_spam']['time_window'])
            recent_msgs = sum(1 for t in self.message_tracker[guild_id][user_id] if t >= window_start)

            if recent_msgs >= config['anti_spam']['message_threshold']:
                try:
                    if config['anti_spam']['action'] == 'mute':
                        mute_role = discord.utils.get(message.guild.roles, name="Muted")
                        if mute_role:
                            await message.author.add_roles(mute_role, reason="Anti-Spam: Spam detectado")
                    elif config['anti_spam']['action'] == 'delete':
                        await message.delete()
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.check_nuke(channel.guild, 'channel_delete', channel)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        # Para member_remove, vamos verificar logs de kick ou ban (já que saídas naturais não geram logs)
        await self.check_nuke(member.guild, 'kick', member)  # Ou 'ban', dependendo do foco; aqui priorizamos kick

    # Adicione mais listeners para roles, bans, etc., se necessário

    async def check_nuke(self, guild: discord.Guild, event_type: str, target=None):
        config = self.security_config.get_guild_config(guild.id)['anti_nuke']
        if not config['enabled']:
            return

        # Obter o usuário responsável via audit log
        action = getattr(discord.AuditLogAction, event_type, None)
        if action is None:
            logger.warning(f"[DEBUG] Ação de audit log inválida para event_type: {event_type}. Pulando verificação.")
            return  # Pula para eventos sem ação válida (ex.: member_remove natural)

        try:
            async for entry in guild.audit_logs(limit=1, action=action):
                user = entry.user
                logger.info(f"[DEBUG] Entrada de audit log encontrada para {event_type}: usuário {user} (ID: {user.id})")
                break
            else:
                logger.info(f"[DEBUG] Nenhuma entrada de audit log encontrada para {event_type}.")
                return  # Não encontrou entry
        except discord.Forbidden:
            logger.warning(f"[DEBUG] Sem permissão para acessar audit logs em {guild.name}.")
            return

        now = datetime.datetime.utcnow()
        guild_id = guild.id
        user_id = user.id
        self.nuke_tracker[guild_id][user_id].append((now, event_type))

        # Contar mudanças na janela
        window_start = now - datetime.timedelta(seconds=config['time_window'])
        recent_changes = sum(1 for t, _ in self.nuke_tracker[guild_id][user_id] if t >= window_start)

        if recent_changes >= config['change_threshold']:
            try:
                if config['action'] == 'ban':
                    await user.ban(reason="Anti-Nuke: Mudanças em massa detectadas")
                    logger.info(f"[DEBUG] Usuário {user} banido por anti-nuke em {guild.name}.")
                elif config['action'] == 'kick':
                    await user.kick(reason="Anti-Nuke: Mudanças em massa detectadas")
                    logger.info(f"[DEBUG] Usuário {user} kickado por anti-nuke em {guild.name}.")
            except discord.Forbidden:
                logger.warning(f"[DEBUG] Sem permissão para punir {user} em {guild.name}.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SecurityCog(bot))