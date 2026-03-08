import discord
from discord import app_commands, ui
from discord.ext import commands
import datetime
import os
import pathlib
from discord.utils import format_dt
import asyncio

# ──────────────────────────────────────────────────────────────
#  CLASSES AUXILIARES
# ──────────────────────────────────────────────────────────────

class TicketView(ui.View):
    """Botão persistente no painel principal para abrir ticket"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Abrir Ticket", style=discord.ButtonStyle.green, emoji="🎫", custom_id="ticket:create")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild_id = interaction.guild_id
        config = self.bot.db.ticket_configs.find_one({"guild_id": guild_id}) or {}
        if not config.get("enabled", True):
            return await interaction.response.send_message("Sistema de tickets desativado.", ephemeral=True)

        modal = TicketModal(self.bot)
        await interaction.response.send_modal(modal)


class TicketModal(ui.Modal, title="Criar novo ticket"):
    motivo = ui.TextInput(
        label="Motivo (obrigatório)",
        style=discord.TextStyle.short,
        placeholder="Ex: Denúncia, Suporte, Dúvida...",
        required=True
    )
    descricao = ui.TextInput(
        label="Descrição detalhada (opcional)",
        style=discord.TextStyle.paragraph,
        required=False
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        config = self.bot.db.ticket_configs.find_one({"guild_id": guild_id}) or {}

        category = interaction.guild.get_channel(config.get("category_id"))
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        staff_role_id = config.get("staff_role")
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, manage_messages=True
                )

        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"Aberto por {interaction.user} | Motivo: {self.motivo.value}"
        )

        embed = discord.Embed(
            title="Ticket criado com sucesso!",
            description=f"{interaction.user.mention}, seu ticket foi aberto!\n**Motivo:** {self.motivo.value}",
            color=discord.Color.green()
        )
        if self.descricao.value:
            embed.add_field(name="Descrição", value=self.descricao.value, inline=False)

        view = TicketControlView(self.bot, interaction.user)
        await channel.send(embed=embed, content=interaction.user.mention, view=view)

        await interaction.response.send_message(f"Ticket criado! Veja aqui: {channel.mention}", ephemeral=True)


# ──────────────────────────────────────────────────────────────
#  VIEW DOS BOTÕES DO EMBED DE TICKET FECHADO (igual à print)
# ──────────────────────────────────────────────────────────────



class TicketControlView(ui.View):
    def __init__(self, bot, owner: discord.Member):
        super().__init__(timeout=None)
        self.bot = bot
        self.owner = owner
        self._closing = False  # trava contra duplo clique

    @ui.button(label="Claim", style=discord.ButtonStyle.blurple, emoji="🔒")
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        config = self.bot.db.ticket_configs.find_one({"guild_id": interaction.guild_id})
        staff_role_id = config.get("staff_role")
        if not staff_role_id or staff_role_id not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("Apenas staff pode claimar tickets.", ephemeral=True)

        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)

        embed = discord.Embed(
            description=f"🔒 {interaction.user.mention} claimou este ticket!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Agora apenas a staff pode responder aqui.")

        await interaction.response.send_message(embed=embed)

    @ui.button(label="Fechar Ticket", style=discord.ButtonStyle.red, emoji="🗑️")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        config = self.bot.db.ticket_configs.find_one({"guild_id": interaction.guild_id})
        staff_role_id = config.get("staff_role")
        is_staff = staff_role_id and staff_role_id in [r.id for r in interaction.user.roles]
        is_owner_or_admin = interaction.user == self.owner or interaction.user.guild_permissions.administrator

        if not (is_staff or is_owner_or_admin):
            return await interaction.response.send_message("Você não tem permissão para fechar este ticket.", ephemeral=True)

        if self._closing:
            return await interaction.response.send_message("Este ticket já está sendo fechado.", ephemeral=True)
        self._closing = True

        await interaction.response.send_message("Ticket será fechado em 5 segundos...", ephemeral=False)
        await asyncio.sleep(5)

        # ── Extrair informações do tópico do canal ──
        topic = interaction.channel.topic or ""
        parts = topic.split("|")
        opened_by_str = parts[0].replace("Aberto por ", "").strip() if len(parts) > 0 else "Desconhecido"
        reason = parts[1].replace("Motivo: ", "").strip() if len(parts) > 1 else "No reason specified"

        # ── Detectar quem claimou (busca nas mensagens) ──
        claimed_by = None
        async for msg in interaction.channel.history(limit=100):
            if msg.embeds:
                desc = msg.embeds[0].description or ""
                if "claimou este ticket" in desc:
                    # Extrai a menção do início da descrição
                    claimed_by = desc.split("claimou")[0].replace("🔒", "").strip()
                    break

        # ── Número sequencial do ticket (usa ID do canal como fallback) ──
        # Se você tiver um contador no DB, use-o aqui.
        ticket_number = self.bot.db.ticket_configs.find_one(
            {"guild_id": interaction.guild_id}
        ) or {}
        counter = ticket_number.get("ticket_counter", 0) + 1
        self.bot.db.ticket_configs.update_one(
            {"guild_id": interaction.guild_id},
            {"$set": {"ticket_counter": counter}},
            upsert=True
        )

        # ── Montar o embed IGUAL à print ──
        embed = discord.Embed(
            title="Ticket Closed",
            color=discord.Color.red()
        )

        # Linha 1: Ticket ID | Opened By | Closed By
        embed.add_field(
            name="📋 Ticket ID",
            value=str(counter),
            inline=True
        )
        embed.add_field(
            name="✅ Opened By",
            value=opened_by_str,
            inline=True
        )
        embed.add_field(
            name="🚫 Closed By",
            value=interaction.user.mention,
            inline=True
        )

        # Linha 2: Open Time | Claimed By
        embed.add_field(
            name="⏰ Open Time",
            value=f"<t:{int(interaction.channel.created_at.timestamp())}:F>",
            inline=True
        )
        embed.add_field(
            name="🔵 Claimed By",
            value=claimed_by if claimed_by else "@ly in silence",  # fallback para teste
            inline=True
        )
        # Célula vazia para fechar a linha de 3 colunas
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Linha 3: Reason (largura total)
        embed.add_field(
            name="❓ Reason",
            value=reason if reason else "No reason specified",
            inline=False
        )

        # ── Enviar para canal de logs com os botões da print ──
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(embed=embed)

        await interaction.channel.delete()


class FieldEditModal(ui.Modal, title="Adicionar/Editar Campo"):
    nome = ui.TextInput(
        label="Nome do campo",
        placeholder="Ex: Regras importantes",
        required=True,
        max_length=256
    )
    valor = ui.TextInput(
        label="Valor/conteúdo",
        style=discord.TextStyle.paragraph,
        placeholder="Suporte 24h • Proibido flood • etc...",
        required=True,
        max_length=1024
    )
    inline = ui.TextInput(
        label="Inline? (sim/não)",
        placeholder="sim ou não (padrão: não)",
        required=False,
        max_length=3
    )
    indice = ui.TextInput(
        label="Editar campo existente? (número)",
        placeholder="Deixe vazio para adicionar novo",
        required=False,
        max_length=2
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            idx = int(self.indice.value.strip()) - 1 if self.indice.value.strip() else None
        except ValueError:
            idx = None

        field_data = {
            "name": self.nome.value.strip(),
            "value": self.valor.value.strip(),
            "inline": self.inline.value.lower().strip() in ("sim", "s", "true", "1", "yes", "y")
        }

        fields = self.view.config["embed"].setdefault("fields", [])

        if idx is not None and 0 <= idx < len(fields):
            fields[idx] = field_data
            msg = f"Campo **{idx+1}** atualizado!"
        else:
            if len(fields) >= 5:
                await interaction.response.send_message("Limite de 5 campos atingido!", ephemeral=True)
                return
            fields.append(field_data)
            msg = "Campo adicionado com sucesso!"

        self.view.bot.db.ticket_configs.update_one(
            {"guild_id": self.view.guild_id},
            {"$set": {"embed.fields": fields}},
            upsert=True
        )

        await self.view.update_preview()
        await interaction.response.send_message(msg, ephemeral=True)


class TicketConfigView(ui.View):
    def __init__(self, bot, interaction):
        super().__init__(timeout=600)
        self.bot = bot
        self.interaction = interaction
        self.guild_id = interaction.guild_id
        self.config = self.bot.db.ticket_configs.find_one({"guild_id": self.guild_id}) or {
            "staff_role": None,
            "category_id": None,
            "log_channel_id": None,
            "embed": {
                "title": "Sistema de Tickets",
                "description": "Clique no botão abaixo para abrir um ticket!",
                "color": 0x00ff00,
                "thumbnail": None,
                "image": None,
                "fields": []
            }
        }
        self.preview_message = None

    async def update_preview(self):
        embed = discord.Embed(
            title=self.config["embed"].get("title", "Sistema de Tickets"),
            description=self.config["embed"].get("description", "Clique no botão abaixo para abrir um ticket!"),
            color=self.config["embed"].get("color", 0x00ff00)
        )
        if self.config["embed"].get("thumbnail"):
            embed.set_thumbnail(url=self.config["embed"]["thumbnail"])
        if self.config["embed"].get("image"):
            embed.set_image(url=self.config["embed"]["image"])

        for field in self.config["embed"].get("fields", []):
            embed.add_field(
                name=field.get("name", "?"),
                value=field.get("value", "—"),
                inline=field.get("inline", False)
            )

        fields_info = "\n".join(
            f"**{i+1}.** {f['name']} {'(inline)' if f.get('inline') else ''}"
            for i, f in enumerate(self.config["embed"].get("fields", []))
        ) or "Nenhum campo personalizado"

        embed.add_field(
            name="Configurações atuais",
            value=(
                f"**Cargo Staff:** <@&{self.config.get('staff_role') or 'Não definido'}>\n"
                f"**Categoria:** <#{self.config.get('category_id') or 'Não definido'}>\n"
                f"**Canal Logs:** <#{self.config.get('log_channel_id') or 'Não definido'}>\n"
                f"**Thumbnail:** {self.config['embed'].get('thumbnail') or 'Não definido'}\n"
                f"**Imagem Principal:** {self.config['embed'].get('image') or 'Não definido'}\n"
                f"**Campos personalizados:**\n{fields_info}"
            ),
            inline=False
        )

        embed.set_author(name="Preview ao vivo do painel de tickets")
        embed.set_footer(text="Alterações salvas automaticamente • Botões editam em tempo real")

        if self.preview_message:
            await self.preview_message.edit(embed=embed, view=self)
        else:
            self.preview_message = await self.interaction.followup.send(embed=embed, view=self, ephemeral=True)

    @ui.button(label="Editar Título", style=discord.ButtonStyle.primary, row=0)
    async def edit_title(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "title", "Título do painel")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Descrição", style=discord.ButtonStyle.primary, row=0)
    async def edit_desc(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "description", "Descrição do painel", paragraph=True)
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Cor (hex)", style=discord.ButtonStyle.primary, row=1)
    async def edit_color(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "color", "Cor em hex (#RRGGBB)")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Thumbnail URL", style=discord.ButtonStyle.primary, row=1)
    async def edit_thumbnail(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "thumbnail", "URL da thumbnail")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Imagem Principal (URL)", style=discord.ButtonStyle.primary, row=2)
    async def edit_image(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "image", "URL da imagem principal")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Cargo Staff (ID)", style=discord.ButtonStyle.secondary, row=2)
    async def edit_staff(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "staff_role", "ID do cargo de staff")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Categoria (ID)", style=discord.ButtonStyle.secondary, row=3)
    async def edit_category(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "category_id", "ID da categoria")
        await interaction.response.send_modal(modal)

    @ui.button(label="Editar Canal Logs (ID)", style=discord.ButtonStyle.secondary, row=3)
    async def edit_logs(self, interaction: discord.Interaction, _):
        modal = SimpleEditModal(self, "log_channel_id", "ID do canal de logs")
        await interaction.response.send_modal(modal)

    @ui.button(label="Adicionar/Editar Campo", style=discord.ButtonStyle.green, row=4)
    async def add_field(self, interaction: discord.Interaction, _):
        modal = FieldEditModal(self)
        await interaction.response.send_modal(modal)

    @ui.button(label="Remover Campo", style=discord.ButtonStyle.red, row=4)
    async def remove_field(self, interaction: discord.Interaction, _):
        modal = ui.Modal(title="Remover Campo")
        idx_input = ui.TextInput(
            label="Número do campo a remover (1 a 5)",
            placeholder="Ex: 2",
            required=True,
            max_length=2
        )
        modal.add_item(idx_input)

        async def remove_submit(inter: discord.Interaction):
            try:
                idx = int(idx_input.value.strip()) - 1
                fields = self.config["embed"].setdefault("fields", [])
                if 0 <= idx < len(fields):
                    del fields[idx]
                    self.bot.db.ticket_configs.update_one(
                        {"guild_id": self.guild_id},
                        {"$set": {"embed.fields": fields}},
                        upsert=True
                    )
                    await self.update_preview()
                    await inter.response.send_message(f"Campo {idx+1} removido!", ephemeral=True)
                else:
                    await inter.response.send_message("Número inválido.", ephemeral=True)
            except ValueError:
                await inter.response.send_message("Digite um número válido.", ephemeral=True)

        modal.on_submit = remove_submit
        await interaction.response.send_modal(modal)

    @ui.button(label="Limpar Campos", style=discord.ButtonStyle.danger, row=4)
    async def clear_fields(self, interaction: discord.Interaction, _):
        self.config["embed"]["fields"] = []
        self.bot.db.ticket_configs.update_one(
            {"guild_id": self.guild_id},
            {"$set": {"embed.fields": []}},
            upsert=True
        )
        await self.update_preview()
        await interaction.response.send_message("Todos os campos foram removidos.", ephemeral=True)

    @ui.button(label="Resetar Tudo", style=discord.ButtonStyle.danger, row=4)
    async def reset(self, interaction: discord.Interaction, _):
        self.bot.db.ticket_configs.delete_one({"guild_id": self.guild_id})
        self.config = {
            "staff_role": None,
            "category_id": None,
            "log_channel_id": None,
            "embed": {
                "title": "Sistema de Tickets",
                "description": "Clique no botão abaixo para abrir um ticket!",
                "color": 0x00ff00,
                "thumbnail": None,
                "image": None,
                "fields": []
            }
        }
        await self.update_preview()
        await interaction.response.send_message("Configurações resetadas para padrão!", ephemeral=True)


class SimpleEditModal(ui.Modal):
    def __init__(self, view, field, title, paragraph=False):
        super().__init__(title=f"Editar {title}")
        self.view = view
        self.field = field
        default = ""
        if field in ["title", "description", "thumbnail", "image"]:
            default = str(view.config.get("embed", {}).get(field, ""))
        elif field == "color":
            default = hex(view.config.get("embed", {}).get(field, 0x00ff00))[2:].zfill(6)
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

        if self.field in ["title", "description", "thumbnail", "image"]:
            embed_data = self.view.config.setdefault("embed", {})
            embed_data[self.field] = value if value else None
            self.view.bot.db.ticket_configs.update_one(
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
                value = 0x00ff00
            embed_data = self.view.config.setdefault("embed", {})
            embed_data[self.field] = value
            self.view.bot.db.ticket_configs.update_one(
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
            self.view.bot.db.ticket_configs.update_one(
                {"guild_id": self.view.guild_id},
                {"$set": {self.field: value}},
                upsert=True
            )

        await self.view.update_preview()
        await interaction.response.send_message(f"**{self.field.capitalize()}** atualizado!", ephemeral=True)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketView(bot))

    @app_commands.command(name="ticketconfig", description="Configura o painel de tickets com preview ao vivo")
    @app_commands.default_permissions(administrator=True)
    async def ticketconfig(self, interaction: discord.Interaction):
        view = TicketConfigView(self.bot, interaction)
        await interaction.response.defer(ephemeral=True)
        await view.update_preview()

    @app_commands.command(name="ticketsetup", description="Envia o painel de tickets atual")
    @app_commands.default_permissions(administrator=True)
    async def ticketsetup(self, interaction: discord.Interaction):
        config = self.bot.db.ticket_configs.find_one({"guild_id": interaction.guild_id}) or {}
        embed_config = config.get("embed", {
            "title": "Sistema de Tickets",
            "description": "Clique no botão abaixo para abrir um ticket!",
            "color": 0x00ff00,
            "thumbnail": None,
            "image": None,
            "fields": []
        })

        embed = discord.Embed(
            title=embed_config.get("title", "Sistema de Tickets"),
            description=embed_config.get("description", "Clique no botão abaixo para abrir um ticket!"),
            color=embed_config.get("color", 0x00ff00)
        )
        if embed_config.get("thumbnail"):
            embed.set_thumbnail(url=embed_config["thumbnail"])
        if embed_config.get("image"):
            embed.set_image(url=embed_config["image"])

        for field in embed_config.get("fields", []):
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )

        await interaction.channel.send(embed=embed, view=TicketView(self.bot))
        await interaction.response.send_message("Painel enviado com sucesso!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))