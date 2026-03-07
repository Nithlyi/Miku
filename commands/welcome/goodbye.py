# commands/welcome/goodbye.py
import discord
from discord import app_commands, ui
from discord.ext import commands
import datetime

class GoodbyeView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def send_goodbye(self, member: discord.Member):
        guild_id = member.guild.id
        config = self.bot.db.goodbye_configs.find_one({"guild_id": guild_id})
        if not config or not config.get("enabled", True):
            return

        channel = member.guild.get_channel(config.get("channel_id"))
        if not channel:
            return

        embed_config = config.get("embed", {
            "title": "Adeus {user_name}...",
            "description": "Sentiremos sua falta no {server}!\nMembros atuais: {member_count}",
            "color": 0xff5555,
            "thumbnail": "{user_avatar}",
            "image": None,
            "footer": "ID: {user_id} • Saiu em {timestamp}",
            "fields": []
        })

        def replace_vars(text: str) -> str:
            if not text:
                return ""
            return text.format(
                user=member,
                user_mention=member.mention,
                user_name=member.name,
                user_id=member.id,
                user_avatar=member.avatar.url if member.avatar else None,
                server=member.guild.name,
                member_count=member.guild.member_count,
                timestamp=discord.utils.format_dt(datetime.datetime.utcnow(), "F"),
                user_created=discord.utils.format_dt(getattr(member, 'created_at', datetime.datetime.utcnow()), "F"),
                user_joined=discord.utils.format_dt(getattr(member, 'joined_at', datetime.datetime.utcnow()), "F")
            )

        title = replace_vars(embed_config.get("title", "Adeus..."))
        description = replace_vars(embed_config.get("description", ""))

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_config.get("color", 0xff5555)
        )

        if embed_config.get("thumbnail"):
            thumb = replace_vars(embed_config["thumbnail"])
            if "{user_avatar}" in thumb:
                embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
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

        await channel.send(embed=embed)


class GoodbyeConfigView(ui.View):
    def __init__(self, bot, interaction):
        super().__init__(timeout=600)
        self.bot = bot
        self.interaction = interaction
        self.guild_id = interaction.guild_id
        self.config = self.bot.db.goodbye_configs.find_one({"guild_id": self.guild_id}) or {
            "enabled": True,
            "channel_id": None,
            "embed": {
                "title": "Adeus {user_name}...",
                "description": "Sentiremos sua falta no {server}!\nMembros atuais: {member_count}",
                "color": 0xff5555,
                "thumbnail": "{user_avatar}",
                "image": None,
                "footer": "ID: {user_id} • Saiu em {timestamp}",
                "fields": []
            }
        }
        self.preview_message = None

    def replace_vars(self, text: str, user: discord.User, guild: discord.Guild) -> str:
        if not text:
            return ""
        return text.format(
            user=user,
            user_mention=user.mention,
            user_name=user.name,
            user_id=user.id,
            user_avatar=user.avatar.url if user.avatar else None,
            server=guild.name,
            member_count=guild.member_count,
            timestamp=discord.utils.format_dt(datetime.datetime.utcnow(), "F"),
            user_created=discord.utils.format_dt(getattr(user, 'created_at', datetime.datetime.utcnow()), "F"),
            user_joined=discord.utils.format_dt(getattr(user, 'joined_at', datetime.datetime.utcnow()), "F") if hasattr(user, 'joined_at') and getattr(user, 'joined_at') else "N/A"
        )

    async def update_preview(self):
        embed = discord.Embed(
            title="Configuração de Goodbye (Preview ao vivo)",
            description="Edite os campos e veja a mensagem de despedida em tempo real.",
            color=discord.Color.red()
        )

        user = self.interaction.user
        guild = self.interaction.guild

        # Use replace_vars para título e descrição
        title = self.replace_vars(self.config["embed"].get("title", "Adeus..."), user, guild)
        description = self.replace_vars(self.config["embed"].get("description", ""), user, guild)

        preview_embed = discord.Embed(
            title=title,
            description=description,
            color=self.config["embed"].get("color", 0xff5555)
        )

        # Para thumbnail, use replace_vars
        if self.config["embed"].get("thumbnail"):
            thumb = self.replace_vars(self.config["embed"]["thumbnail"], user, guild)
            preview_embed.set_thumbnail(url=thumb)

        # Para image, use replace_vars
        if self.config["embed"].get("image"):
            img = self.replace_vars(self.config["embed"]["image"], user, guild)
            preview_embed.set_image(url=img)

        # Para footer, use replace_vars
        if self.config["embed"].get("footer"):
            footer = self.replace_vars(self.config["embed"]["footer"], user, guild)
            preview_embed.set_footer(text=footer)

        # Para fields, use replace_vars
        for field in self.config["embed"].get("fields", []):
            name = self.replace_vars(field.get("name", "Campo"), user, guild)
            value = self.replace_vars(field.get("value", "Valor"), user, guild)
            inline = field.get("inline", False)
            preview_embed.add_field(name=name, value=value, inline=inline)

        embed.add_field(name="Canal de Envio", value=f"<#{self.config.get('channel_id', 'Não definido')}>", inline=True)
        embed.add_field(name="Ativado?", value="Sim" if self.config.get("enabled", True) else "Não", inline=True)
        embed.add_field(name="Preview da mensagem de despedida", value="↓ Veja abaixo ↓", inline=False)

        if self.preview_message:
            await self.preview_message.edit(embed=embed, view=self)
            await self.preview_message.edit(embed=preview_embed)  # Nota: Isso edita duas vezes; teste e ajuste se necessário (ex.: envie duas mensagens separadas).
        else:
            self.preview_message = await self.interaction.followup.send(embed=embed, view=self, ephemeral=True)
            await self.preview_message.edit(embed=preview_embed)

    # Botões de edição (reorganizados para rows 0-4)
    @ui.button(label="Editar Título", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "title", "Título da mensagem de goodbye")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Descrição", style=discord.ButtonStyle.primary, row=0)
    async def edit_desc(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "description", "Descrição da mensagem", paragraph=True)
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Cor (hex)", style=discord.ButtonStyle.primary, row=1)
    async def edit_color(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "color", "Cor do embed (#RRGGBB)")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Thumbnail URL", style=discord.ButtonStyle.primary, row=1)
    async def edit_thumbnail(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "thumbnail", "URL da thumbnail (ou {user_avatar})")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Imagem Principal (URL)", style=discord.ButtonStyle.primary, row=2)
    async def edit_image(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "image", "URL da imagem grande")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Footer", style=discord.ButtonStyle.secondary, row=2)
    async def edit_footer(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "footer", "Texto do rodapé")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Campo 1", style=discord.ButtonStyle.secondary, row=3)
    async def edit_field1(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 0)
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Campo 2", style=discord.ButtonStyle.secondary, row=3)
    async def edit_field2(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 1)
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Campo 3", style=discord.ButtonStyle.secondary, row=4)
    async def edit_field3(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 2)
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Campo 4", style=discord.ButtonStyle.secondary, row=4)
    async def edit_field4(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self, 3)
        await interaction.response.send_modal(modal)

    @ui.button(label="Definir Canal (ID)", style=discord.ButtonStyle.secondary, row=4)
    async def edit_channel(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "channel_id", "ID do canal de despedida")
        await interaction.response.send_modal(modal)

    @ui.button(label="Ativar/Desativar", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_enabled(self, interaction: discord.Interaction, _):
        self.config["enabled"] = not self.config.get("enabled", True)
        self.bot.db.goodbye_configs.update_one(
            {"guild_id": self.guild_id},
            {"$set": {"enabled": self.config["enabled"]}},
            upsert=True
        )
        await self.update_preview()
        await interaction.response.send_message(f"Sistema de goodbye agora está **{'ativado' if self.config['enabled'] else 'desativado'}**.", ephemeral=True)

    @ui.button(label="Resetar Tudo", style=discord.ButtonStyle.danger, row=4)
    async def reset(self, interaction: discord.Interaction, _):
        self.bot.db.goodbye_configs.delete_one({"guild_id": self.guild_id})
        self.config = {
            "enabled": True,
            "channel_id": None,
            "embed": {
                "title": "Adeus {user_name}...",
                "description": "Sentiremos sua falta no {server}!\nMembros atuais: {member_count}",
                "color": 0xff5555,
                "thumbnail": "{user_avatar}",
                "image": None,
                "footer": "ID: {user_id} • Saiu em {timestamp}",
                "fields": []
            }
        }
        await self.update_preview()
        await interaction.response.send_message("Configurações de goodbye resetadas para padrão!", ephemeral=True)


class SimpleEditModal(ui.Modal):
    def __init__(self, view, field, title, paragraph=False):
        super().__init__(title=f"Editar {title}")
        self.view = view
        self.field = field
        default = ""
        if field in ["title", "description", "thumbnail", "image", "footer"]:
            default = str(view.config.get("embed", {}).get(field, ""))
        elif field == "color":
            default = hex(view.config.get("embed", {}).get(field, 0xff5555))[2:].zfill(6)
        else:
            default = str(view.config.get(field, ""))

        self.input = ui.TextInput(
            label=title,
            style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short,
            default=default,
            required=False
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.input.value.strip()

        if self.field in ["title", "description", "thumbnail", "image", "footer"]:
            embed_data = self.view.config.setdefault("embed", {})
            embed_data[self.field] = value if value else None
            self.view.bot.db.goodbye_configs.update_one(
                {"guild_id": self.view.guild_id},
                {"$set": {"embed": embed_data}},
                upsert=True
            )
        elif self.field == "color":
            if value:
                try:
                    value = int(value.lstrip('#'), 16)
                except ValueError:
                    await interaction.response.send_message("Cor inválida. Use #RRGGBB ou deixe vazio.", ephemeral=True)
                    return
            else:
                value = 0xff5555
            embed_data = self.view.config.setdefault("embed", {})
            embed_data[self.field] = value
            self.view.bot.db.goodbye_configs.update_one(
                {"guild_id": self.view.guild_id},
                {"$set": {"embed": embed_data}},
                upsert=True
            )
        else:
            try:
                value = int(value) if value else None
            except ValueError:
                value = None
            self.view.config[self.field] = value
            self.view.bot.db.goodbye_configs.update_one(
                {"guild_id": self.view.guild_id},
                {"$set": {self.field: value}},
                upsert=True
            )

        await self.view.update_preview()
        await interaction.response.send_message(f"**{self.field.capitalize()}** atualizado!", ephemeral=True)


class FieldEditModal(ui.Modal, title="Editar Campo Extra"):
    name = ui.TextInput(label="Nome do campo", style=discord.TextStyle.short, required=True)
    value = ui.TextInput(label="Valor do campo (use variáveis)", style=discord.TextStyle.paragraph, required=True)
    inline = ui.TextInput(label="Inline? (sim/não)", style=discord.TextStyle.short, default="sim", required=False)

    def __init__(self, view, field_index):
        super().__init__()
        self.view = view
        self.field_index = field_index
        fields = self.view.config["embed"].setdefault("fields", [{} for _ in range(4)])
        while len(fields) <= field_index:
            fields.append({})
        field = fields[field_index]
        self.name.default = field.get("name", "")
        self.value.default = field.get("value", "")
        self.inline.default = "sim" if field.get("inline", False) else "não"

    async def on_submit(self, interaction: discord.Interaction):
        fields = self.view.config["embed"].setdefault("fields", [{} for _ in range(4)])
        field = fields[self.field_index]
        field["name"] = self.name.value
        field["value"] = self.value.value
        field["inline"] = self.inline.value.lower() in ["sim", "s", "yes", "y", "true"]

        self.view.bot.db.goodbye_configs.update_one(
            {"guild_id": self.view.guild_id},
            {"$set": {"embed.fields": fields}},
            upsert=True
        )

        await self.view.update_preview()
        await interaction.response.send_message(f"Campo {self.field_index + 1} atualizado!", ephemeral=True)


class Goodbye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await GoodbyeView(self.bot).send_goodbye(member)

    @app_commands.command(name="goodbyeconfig", description="[Admin] Configura a mensagem de despedida com preview ao vivo")
    @app_commands.default_permissions(administrator=True)
    async def goodbyeconfig(self, interaction: discord.Interaction):
        view = GoodbyeConfigView(self.bot, interaction)
        await interaction.response.defer(ephemeral=True)
        await view.update_preview()

    @app_commands.command(name="goodbyesendtest", description="[Admin] Envia um teste da mensagem de despedida atual")
    @app_commands.default_permissions(administrator=True)
    async def goodbyesendtest(self, interaction: discord.Interaction):
        config = self.bot.db.goodbye_configs.find_one({"guild_id": interaction.guild_id})
        if not config:
            return await interaction.response.send_message("Configure primeiro com /goodbyeconfig", ephemeral=True)

        embed_config = config.get("embed", {
            "title": "Adeus {user_name}...",
            "description": "Sentiremos sua falta no {server}!\nMembros atuais: {member_count}",
            "color": 0xff5555,
            "thumbnail": "{user_avatar}",
            "image": None,
            "footer": "ID: {user_id} • Saiu em {timestamp}",
            "fields": []
        })

        def replace_vars(text: str) -> str:
            if not text:
                return ""
            return text.format(
                user=interaction.user,
                user_mention=interaction.user.mention,
                user_name=interaction.user.name,
                user_id=interaction.user.id,
                user_avatar=interaction.user.avatar.url if interaction.user.avatar else None,
                server=interaction.guild.name,
                member_count=interaction.guild.member_count,
                timestamp=discord.utils.format_dt(datetime.datetime.utcnow(), "F"),
                user_created=discord.utils.format_dt(getattr(interaction.user, 'created_at', datetime.datetime.utcnow()), "F"),
                user_joined=discord.utils.format_dt(getattr(interaction.user, 'joined_at', datetime.datetime.utcnow()), "F") if hasattr(interaction.user, 'joined_at') else "N/A"
            )

        title = replace_vars(embed_config.get("title", ""))
        description = replace_vars(embed_config.get("description", ""))

        embed = discord.Embed(title=title, description=description, color=embed_config.get("color", 0xff5555))

        if embed_config.get("thumbnail"):
            thumb = replace_vars(embed_config["thumbnail"])
            if "{user_avatar}" in thumb:
                embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
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

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Teste de goodbye enviado no canal atual!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Goodbye(bot))