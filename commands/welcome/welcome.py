import discord
from discord import app_commands, ui
from discord.ext import commands
import logging

# Configuração básica do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


class WelcomeView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def send_welcome(self, member: discord.Member):
        logger.info(f"[DEBUG] Iniciando send_welcome para {member}...")
        config = self.bot.db.welcome_configs.find_one({"guild_id": member.guild.id})
        if not config:
            logger.info("[DEBUG] Nenhuma configuração encontrada no DB.")
            return
        if not config.get("enabled", True):
            logger.info("[DEBUG] Sistema de welcome desativado.")
            return
        channel_id = config.get("channel_id")
        if not channel_id:
            logger.info("[DEBUG] Canal não definido na configuração.")
            return
        channel = member.guild.get_channel(channel_id)
        if not channel:
            logger.info("[DEBUG] Canal não encontrado (ID inválido ou bot sem acesso).")
            return
        logger.info(f"[DEBUG] Canal encontrado: {channel} (ID: {channel.id}). Tentando enviar embed...")

        embed_config = config.get("embed", {
            "title": "Bem-vindo(a) ao {server}!",
            "description": "Olá {user.mention}! Esperamos que você se divirta muito aqui!\nMembros atuais: {member_count}",
            "color": 0x00ff88,
            "thumbnail": "{user.avatar}",
            "image": None,
            "footer": "ID: {user.id} • Entrou em {timestamp}",
            "fields": []
        })

        def replace_vars(text: str) -> str:
            if not text:
                return ""
            try:
                return text.format(
                    user=member,
                    user_mention=member.mention,
                    user_name=member.name,
                    server=member.guild.name,
                    member_count=member.guild.member_count,
                    timestamp=discord.utils.format_dt(discord.utils.utcnow(), "F"),
                    user_created=discord.utils.format_dt(member.created_at, "F"),
                    user_joined=discord.utils.format_dt(member.joined_at, "F") if member.joined_at else "N/A"
                )
            except KeyError as e:
                logger.warning(f"Erro de formatação em '{text}': {e}")
                return text

        title = replace_vars(embed_config.get("title", "Bem-vindo(a)!"))
        description = replace_vars(embed_config.get("description", ""))

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_config.get("color", 0x00ff88)
        )

        if embed_config.get("thumbnail"):
            thumb = replace_vars(embed_config["thumbnail"])
            if "{user.avatar}" in thumb:
                embed.set_thumbnail(url=member.display_avatar.url)
            else:
                embed.set_thumbnail(url=thumb)

        if embed_config.get("image"):
            img = replace_vars(embed_config["image"])
            embed.set_image(url=img)

        if embed_config.get("footer"):
            footer = replace_vars(embed_config["footer"])
            embed.set_footer(text=footer)

        for field in embed_config.get("fields", []):
            name = replace_vars(field.get("name", "Campo"))
            value = replace_vars(field.get("value", "Valor"))
            inline = field.get("inline", False)
            embed.add_field(name=name, value=value, inline=inline)

        try:
            mention_user = config.get("mention_user", False)
            mention_text = config.get("mention_text", "{user.mention}")
            mention_content = replace_vars(mention_text) if mention_user and mention_text else None
            
            if mention_content:
                await channel.send(content=mention_content, embed=embed)
            else:
                await channel.send(embed=embed)
            logger.info("[DEBUG] Mensagem de welcome enviada com sucesso!")
        except Exception as e:
            logger.error(f"[DEBUG] Erro ao enviar mensagem: {e}")


class WelcomeConfigView(ui.View):
    def __init__(self, bot, interaction):
        super().__init__(timeout=600)
        self.bot = bot
        self.interaction = interaction
        self.guild_id = interaction.guild_id
        self.config = self.bot.db.welcome_configs.find_one({"guild_id": self.guild_id}) or {
            "enabled": True,
            "channel_id": None,
            "mention_user": False,
            "mention_text": "{user.mention}",
            "embed": {
                "title": "Bem-vindo(a) ao {server}!",
                "description": "Olá {user.mention}! Esperamos que você se divirta muito aqui!\nMembros atuais: {member_count}",
                "color": 0x00ff88,
                "thumbnail": "{user.avatar}",
                "image": None,
                "footer": "ID: {user.id} • Entrou em {timestamp}",
                "fields": []
            }
        }
        self.preview_message = None

    async def update_preview(self):
        embed = discord.Embed(
            title="⚙️ Configuração de Welcome",
            description="Edite os campos e veja a mensagem de boas-vindas em tempo real.",
            color=discord.Color.blue()
        )

        user = self.interaction.user
        guild = self.interaction.guild
        timestamp = discord.utils.format_dt(discord.utils.utcnow(), "F")

        preview_embed = discord.Embed(
            title=self.config["embed"].get("title", "Bem-vindo(a)!").format(
                user=user, server=guild.name, member_count=guild.member_count,
                timestamp=timestamp, user_created=timestamp, user_joined=timestamp
            ),
            description=self.config["embed"].get("description", "").format(
                user=user, server=guild.name, member_count=guild.member_count,
                timestamp=timestamp, user_created=timestamp, user_joined=timestamp
            ),
            color=self.config["embed"].get("color", 0x00ff88)
        )

        if self.config["embed"].get("thumbnail"):
            thumb = self.config["embed"]["thumbnail"].format(user=user)
            if "{user.avatar}" in thumb:
                preview_embed.set_thumbnail(url=getattr(user, 'display_avatar', None).url if hasattr(user, 'display_avatar') and user.display_avatar else None)
            else:
                preview_embed.set_thumbnail(url=thumb)

        if self.config["embed"].get("image"):
            img = self.config["embed"]["image"].format(user=user)
            preview_embed.set_image(url=img)

        if self.config["embed"].get("footer"):
            footer = self.config["embed"]["footer"].format(
                user=user, server=guild.name, member_count=guild.member_count,
                timestamp=timestamp, user_created=timestamp, user_joined=timestamp
            )
            preview_embed.set_footer(text=footer)

        for field in self.config["embed"].get("fields", []):
            name = field.get("name", "Campo").format(
                user=user, server=guild.name, member_count=guild.member_count,
                timestamp=timestamp, user_created=timestamp, user_joined=timestamp
            )
            value = field.get("value", "Valor").format(
                user=user, server=guild.name, member_count=guild.member_count,
                timestamp=timestamp, user_created=timestamp, user_joined=timestamp
            )
            inline = field.get("inline", False)
            preview_embed.add_field(name=name, value=value, inline=inline)

        mention_status = "✅ Ativado" if self.config.get("mention_user", False) else "❌ Desativado"
        
        embed.add_field(name="📢 Menção", value=f"{mention_status}", inline=True)
        embed.add_field(name="📝 Canal", value=f"<#{self.config.get('channel_id', 'Não definido')}>", inline=True)
        embed.add_field(name="✅ Status", value="Ativado" if self.config.get("enabled", True) else "Desativado", inline=True)
        embed.add_field(name="👁️ Preview", value="↓ Veja abaixo ↓", inline=False)

        if self.preview_message:
            await self.preview_message.edit(embed=embed, view=self)
            await self.preview_message.edit(embed=preview_embed)
        else:
            self.preview_message = await self.interaction.followup.send(embed=embed, view=self, ephemeral=True)
            await self.preview_message.edit(embed=preview_embed)

    # Linha 0
    @ui.button(label="Editar Título", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "title", "Título da mensagem")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Descrição", style=discord.ButtonStyle.primary, row=0)
    async def edit_desc(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "description", "Descrição da mensagem", paragraph=True)
        await interaction.response.send_modal(modal)

    # Linha 1
    @ui.button(label="Editar Cor", style=discord.ButtonStyle.primary, row=1)
    async def edit_color(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "color", "Cor (#RRGGBB)")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Thumbnail", style=discord.ButtonStyle.primary, row=1)
    async def edit_thumbnail(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "thumbnail", "URL thumbnail")
        await interaction.response.send_modal(modal)

    # Linha 2
    @ui.button(label="Editar Imagem", style=discord.ButtonStyle.secondary, row=2)
    async def edit_image(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "image", "URL da imagem")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Footer", style=discord.ButtonStyle.secondary, row=2)
    async def edit_footer(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "footer", "Texto do rodapé")
        await interaction.response.send_modal(modal)

    # Linha 3
    @ui.button(label="Campo 1", style=discord.ButtonStyle.secondary, row=3)
    async def edit_field1(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 0)
        await interaction.response.send_modal(modal)

    @ui.button(label="Campo 2", style=discord.ButtonStyle.secondary, row=3)
    async def edit_field2(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 1)
        await interaction.response.send_modal(modal)

    @ui.button(label="Campo 3", style=discord.ButtonStyle.secondary, row=3)
    async def edit_field3(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 2)
        await interaction.response.send_modal(modal)

    @ui.button(label="Campo 4", style=discord.ButtonStyle.secondary, row=3)
    async def edit_field4(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 3)
        await interaction.response.send_modal(modal)

    # Linha 4
    @ui.button(label="Definir Canal", style=discord.ButtonStyle.secondary, row=4)
    async def edit_channel(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "channel_id", "ID do canal")
        await interaction.response.send_modal(modal)

    @ui.button(label="Ativar/Desativar", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_enabled(self, interaction: discord.Interaction, _):
        self.config["enabled"] = not self.config.get("enabled", True)
        self.bot.db.welcome_configs.update_one({"guild_id": self.guild_id}, {"$set": {"enabled": self.config["enabled"]}}, upsert=True)
        await self.update_preview()
        await interaction.response.send_message(f"Sistema **{'ativado' if self.config['enabled'] else 'desativado'}**.", ephemeral=True)

    @ui.button(label="Alternar Menção", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_mention(self, interaction: discord.Interaction, _):
        self.config["mention_user"] = not self.config.get("mention_user", False)
        self.bot.db.welcome_configs.update_one({"guild_id": self.guild_id}, {"$set": {"mention_user": self.config["mention_user"]}}, upsert=True)
        await self.update_preview()
        status = "ativada" if self.config["mention_user"] else "desativada"
        await interaction.response.send_message(f"Menção **{status}**!", ephemeral=True)

    @ui.button(label="Texto Menção", style=discord.ButtonStyle.secondary, row=4)
    async def edit_mention_text(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "mention_text", "Texto da menção")
        await interaction.response.send_modal(modal)

    @ui.button(label="Resetar", style=discord.ButtonStyle.danger, row=4)
    async def reset(self, interaction: discord.Interaction, _):
        self.bot.db.welcome_configs.delete_one({"guild_id": self.guild_id})
        self.config = {
            "enabled": True, "channel_id": None, "mention_user": False, "mention_text": "{user.mention}",
            "embed": {"title": "Bem-vindo(a) ao {server}!", "description": "Olá {user.mention}!...\nMembros: {member_count}",
                "color": 0x00ff88, "thumbnail": "{user.avatar}", "image": None, "footer": "ID: {user.id} • {timestamp}", "fields": []}
        }
        await self.update_preview()
        await interaction.response.send_message("Configurações resetadas!", ephemeral=True)


class SimpleEditModal(ui.Modal):
    def __init__(self, view, field, title, paragraph=False):
        super().__init__(title=f"Editar {title}")
        self.view = view
        self.field = field
        
        if field in ["title", "description", "thumbnail", "image", "footer"]:
            default = str(view.config.get("embed", {}).get(field, ""))
        elif field == "color":
            default = hex(view.config.get("embed", {}).get(field, 0x00ff88))[2:].zfill(6)
        elif field == "mention_text":
            default = str(view.config.get("mention_text", "{user.mention}"))
        elif field == "channel_id":
            default = str(view.config.get("channel_id", ""))
        else:
            default = str(view.config.get(field, ""))

        self.input = ui.TextInput(label=title, style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short, default=default, required=False)
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.input.value.strip()

        if self.field in ["title", "description", "thumbnail", "image", "footer"]:
            embed_data = self.view.config.setdefault("embed", {})
            embed_data[self.field] = value if value else None
            self.view.bot.db.welcome_configs.update_one({"guild_id": self.view.guild_id}, {"$set": {"embed": embed_data}}, upsert=True)
        elif self.field == "color":
            if value:
                try:
                    value = int(value.lstrip('#'), 16)
                except ValueError:
                    await interaction.response.send_message("Cor inválida.", ephemeral=True)
                    return
            else:
                value = 0x00ff88
            embed_data = self.view.config.setdefault("embed", {})
            embed_data[self.field] = value
            self.view.bot.db.welcome_configs.update_one({"guild_id": self.view.guild_id}, {"$set": {"embed": embed_data}}, upsert=True)
        elif self.field == "mention_text":
            self.view.config["mention_text"] = value if value else "{user.mention}"
            self.view.bot.db.welcome_configs.update_one({"guild_id": self.view.guild_id}, {"$set": {"mention_text": self.view.config["mention_text"]}}, upsert=True)
        elif self.field == "channel_id":
            try:
                value = int(value) if value else None
            except ValueError:
                value = None
            self.view.config["channel_id"] = value
            self.view.bot.db.welcome_configs.update_one({"guild_id": self.view.guild_id}, {"$set": {"channel_id": value}}, upsert=True)

        await self.view.update_preview()
        await interaction.response.send_message(f"**{self.field}** atualizado!", ephemeral=True)


class FieldEditModal(ui.Modal, title="Editar Campo"):
    def __init__(self, view, field_index):
        super().__init__()
        self.view = view
        self.field_index = field_index
        
        fields = self.view.config["embed"].setdefault("fields", [{} for _ in range(4)])
        while len(fields) <= field_index:
            fields.append({})
        field = fields[field_index]
        
        self.name_input = ui.TextInput(label="Nome", style=discord.TextStyle.short, default=field.get("name", ""), required=True)
        self.value_input = ui.TextInput(label="Valor", style=discord.TextStyle.paragraph, default=field.get("value", ""), required=True)
        self.inline_input = ui.TextInput(label="Inline? (sim/não)", style=discord.TextStyle.short, default="sim" if field.get("inline", True) else "não", required=False)
        self.add_item(self.name_input)
        self.add_item(self.value_input)
        self.add_item(self.inline_input)

    async def on_submit(self, interaction: discord.Interaction):
        fields = self.view.config["embed"].setdefault("fields", [{} for _ in range(4)])
        field = fields[self.field_index]
        
        field["name"] = self.name_input.value
        field["value"] = self.value_input.value
        field["inline"] = self.inline_input.value.lower() in ["sim", "s", "yes", "y", "true"]

        self.view.bot.db.welcome_configs.update_one(
            {"guild_id": self.view.guild_id},
            {"$set": {"embed.fields": fields}},
            upsert=True
        )

        await self.view.update_preview()
        await interaction.response.send_message(f"Campo {self.field_index + 1} atualizado!", ephemeral=True)


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        logger.info(f"[DEBUG] on_member_join disparado para {member} (ID: {member.id}) em {member.guild.name} (Guild ID: {member.guild.id})")
        await WelcomeView(self.bot).send_welcome(member)

    @app_commands.command(name="welcomeconfig", description="[Admin] Configura a mensagem de boas-vindas")
    @app_commands.default_permissions(administrator=True)
    async def welcomeconfig(self, interaction: discord.Interaction):
        view = WelcomeConfigView(self.bot, interaction)
        await interaction.response.defer(ephemeral=True)
        await view.update_preview()

    @app_commands.command(name="welcomesendtest", description="[Admin] Envia um teste da mensagem de boas-vindas")
    @app_commands.default_permissions(administrator=True)
    async def welcomesendtest(self, interaction: discord.Interaction):
        config = self.bot.db.welcome_configs.find_one({"guild_id": interaction.guild_id})
        if not config:
            return await interaction.response.send_message("Configure primeiro com /welcomeconfig", ephemeral=True)

        channel = interaction.channel
        embed_config = config.get("embed", {
            "title": "Bem-vindo(a) ao {server}!",
            "description": "Olá {user.mention}! Esperamos que você se divirta muito aqui!\nMembros atuais: {member_count}",
            "color": 0x00ff88,
            "thumbnail": "{user.avatar}",
            "image": None,
            "footer": "ID: {user.id} • Entrou em {timestamp}",
            "fields": []
        })

        def replace_vars(text: str) -> str:
            if not text:
                return ""
            try:
                return text.format(
                    user=interaction.user,
                    user_mention=interaction.user.mention,
                    user_name=interaction.user.name,
                    server=interaction.guild.name,
                    member_count=interaction.guild.member_count,
                    timestamp=discord.utils.format_dt(discord.utils.utcnow(), "F"),
                    user_created=discord.utils.format_dt(getattr(interaction.user, 'created_at', discord.utils.utcnow()), "F"),
                    user_joined=discord.utils.format_dt(getattr(interaction.user, 'joined_at', discord.utils.utcnow()), "F") if hasattr(interaction.user, 'joined_at') else "N/A"
                )
            except KeyError as e:
                logger.warning(f"Erro de formatação em '{text}': {e}")
                return text

        title = replace_vars(embed_config.get("title", ""))
        description = replace_vars(embed_config.get("description", ""))

        embed = discord.Embed(title=title, description=description, color=embed_config.get("color", 0x00ff88))

        if embed_config.get("thumbnail"):
            thumb = replace_vars(embed_config["thumbnail"])
            if "{user.avatar}" in thumb:
                embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            else:
                embed.set_thumbnail(url=thumb)

        if embed_config.get("image"):
            img = replace_vars(embed_config["image"])
            embed.set_image(url=img)

        if embed_config.get("footer"):
            footer = replace_vars(embed_config["footer"])
            embed.set_footer(text=footer)

        for field in embed_config.get("fields", []):
            name = replace_vars(field.get("name", "Campo"))
            value = replace_vars(field.get("value", "Valor"))
            inline = field.get("inline", False)
            embed.add_field(name=name, value=value, inline=inline)

        mention_user = config.get("mention_user", False)
        mention_text = config.get("mention_text", "{user.mention}")
        mention_content = replace_vars(mention_text) if mention_user and mention_text else None

        if mention_content:
            await channel.send(content=mention_content, embed=embed)
        else:
            await channel.send(embed=embed)
        
        await interaction.response.send_message("Teste de boas-vindas enviado!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))