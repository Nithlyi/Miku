import discord
from discord import app_commands, ui
from discord.ext import commands
import datetime
import asyncio
from typing import Optional, Dict, Any

# ================================================
# MODAIS CORRIGIDOS
# ================================================

class SimpleEditModal(ui.Modal):
    def __init__(self, view: 'ModEmbedConfigView', field: str, title: str, paragraph: bool = False):
        super().__init__(title=f"Editar {title}")
        self.view = view
        self.field = field
        config = view.get_current_config()
        default = str(config.get(field, "") or "")
        if field == "color":
            default = f"#{config.get('color', 0xff0000):06x}"
        self.input = ui.TextInput(
            label=title,
            style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short,
            default=default,
            required=False,
            max_length=2000 if paragraph else 256
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.input.value.strip()
        config = self.view.get_current_config()
        
        if self.field == "color":
            if value:
                try:
                    if value.startswith("#"): value = value[1:]
                    color = int(value, 16)
                    if not 0 <= color <= 0xFFFFFF:
                        raise ValueError
                except ValueError:
                    await interaction.response.send_message("❌ Formato inválido. Use #RRGGBB", ephemeral=True)
                    return
            else:
                color = 0xff0000
            config["color"] = color
        else:
            config[self.field] = value if value else None

        self.view.save()
        await self.view.update_preview(interaction)
        
        await interaction.response.send_message(f"✅ {self.field.capitalize()} atualizado para {self.view.current_type.upper()}.", ephemeral=True)


class FieldEditModal(ui.Modal, title="Editar Campo Extra"):
    nome   = ui.TextInput(label="Nome do campo", style=discord.TextStyle.short, required=True, max_length=256)
    valor  = ui.TextInput(label="Valor (use {vars})", style=discord.TextStyle.paragraph, required=True, max_length=1024)
    inline = ui.TextInput(label="Inline? (sim/não)", style=discord.TextStyle.short, required=False, default="sim")

    def __init__(self, view: 'ModEmbedConfigView', index: int):
        super().__init__()
        self.view = view
        self.index = index
        fields = self.view.get_current_config().setdefault("fields", [])
        while len(fields) <= index: fields.append({})
        f = fields[index]
        self.nome.default  = f.get("name", "")
        self.valor.default = f.get("value", "")
        self.inline.default = "sim" if f.get("inline", False) else "não"

    async def on_submit(self, interaction: discord.Interaction):
        fields = self.view.get_current_config()["fields"]
        
        while len(fields) <= self.index:
            fields.append({})
        
        f = fields[self.index]
        f["name"]   = self.nome.value.strip()
        f["value"]  = self.valor.value.strip()
        f["inline"] = self.inline.value.lower() in ("sim", "s", "yes", "y", "true", "1")

        if not f["name"] or not f["value"]:
            if self.index < len(fields):
                fields.pop(self.index)

        self.view.save()
        await self.view.update_preview(interaction)
        
        await interaction.response.send_message(f"✅ Campo {self.index+1} atualizado para {self.view.current_type.upper()}.", ephemeral=True)


# ================================================
# VIEW DE CONFIGURAÇÃO CORRIGIDA
# ================================================

class ModEmbedConfigView(ui.View):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction):
        super().__init__(timeout=900)
        self.bot = bot
        self.interaction = interaction
        self.guild_id = interaction.guild_id
        self.current_type = "default"
        
        db_data = bot.db.moderation_embed_configs.find_one({"guild_id": self.guild_id}) or {}

        self.config = {
            "default": db_data.get("default", {
                "title": "{user_name} foi punido(a)",
                "description": "Aplicada por {moderator_mention}\n**Motivo:** {motivo}\n**Duração:** {tempo}",
                "color": 0xff0000,
                "thumbnail": "{user_avatar}",
                "image": None,
                "footer": "ID: {user_id} • {timestamp} • {server_name}",
                "fields": []
            }),
            "warn": db_data.get("warn", {}),
            "ban": db_data.get("ban", {}),
            "mute": db_data.get("mute", {}),
            "unwarn": db_data.get("unwarn", {}),
            "unban": db_data.get("unban", {}),
            "unmute": db_data.get("unmute", {})
        }

        self.preview_msg: Optional[discord.Message] = None
        
        self.add_item(self.PunishmentTypeSelect(self))

    class PunishmentTypeSelect(ui.Select):
        def __init__(self, view: 'ModEmbedConfigView'):
            options = [
                discord.SelectOption(label="Default", value="default", description="Configuração padrão", default=view.current_type == "default"),
                discord.SelectOption(label="Warn", value="warn", description="Advertência", default=view.current_type == "warn"),
                discord.SelectOption(label="Ban", value="ban", description="Banimento", default=view.current_type == "ban"),
                discord.SelectOption(label="Mute", value="mute", description="Silenciamento", default=view.current_type == "mute"),
                discord.SelectOption(label="Unwarn", value="unwarn", description="Remover advertência", default=view.current_type == "unwarn"),
                discord.SelectOption(label="Unban", value="unban", description="Desbanir", default=view.current_type == "unban"),
                discord.SelectOption(label="Unmute", value="unmute", description="Remover mute", default=view.current_type == "unmute"),
            ]
            super().__init__(
                placeholder="Selecione o tipo de punição para configurar...",
                min_values=1,
                max_values=1,
                options=options,
                row=0
            )
            self.view_ref = view

        async def callback(self, interaction: discord.Interaction):
            self.view_ref.current_type = self.values[0]
            await self.view_ref.update_preview(interaction)
            await interaction.response.defer()

    def get_current_config(self):
        if self.current_type not in self.config:
            self.config[self.current_type] = {}
        return self.config[self.current_type]

    def get_preview_vars(self) -> dict:
        user = self.interaction.user
        guild = self.interaction.guild
        now = datetime.datetime.now(datetime.UTC)
        avatar = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        return {
            "user_name":          "ExemploUser",
            "user_mention":       "<@123456789012345678>",
            "user_id":            "123456789012345678",
            "user_avatar":        avatar,
            "moderator_name":     user.name,
            "moderator_mention":  user.mention,
            "motivo":             "Teste de configuração",
            "tempo":              "45 minutos",
            "action":             self.current_type.upper(),
            "server_name":        guild.name if guild else "Servidor Exemplo",
            "timestamp":          discord.utils.format_dt(now, "F"),
        }

    async def update_preview(self, interaction: Optional[discord.Interaction] = None):
        vars_dict = self.get_preview_vars()
        current_cfg = self.get_current_config()

        instr = discord.Embed(
            title=f"⚙️ Configurando Embed para {self.current_type.upper()}",
            color=discord.Color.blue()
        )
        instr.description = (
            f"Editando configuração para **{self.current_type.upper()}**\n\n"
            "Selecione o tipo no menu acima para alternar entre configurações.\n"
            "Edite os campos abaixo e veja o preview em tempo real ↓\n\n"
            "**📋 Variáveis disponíveis:**\n"
            "`{user_name}` `{user_mention}` `{user_id}` `{user_avatar}`\n"
            "`{moderator_name}` `{moderator_mention}` `{motivo}` `{tempo}` `{action}`\n"
            "`{server_name}` `{timestamp}`"
        )
        instr.set_footer(text="💡 Dica: Use variáveis para dynamicizar seus embeds")

        preview_embed = discord.Embed(color=current_cfg.get("color", 0xff0000))

        try:
            title_text = current_cfg.get("title") or f"{self.current_type.upper()} aplicada"
            preview_embed.title = title_text.format(**vars_dict)
        except KeyError as e:
            preview_embed.title = f"[ERRO: variável {e} não encontrada]"
            preview_embed.color = discord.Color.red()

        try:
            desc_text = current_cfg.get("description") or ""
            preview_embed.description = desc_text.format(**vars_dict)
        except KeyError as e:
            preview_embed.description = f"[ERRO: variável {e} não encontrada]"
            preview_embed.color = discord.Color.red()

        if thumb := current_cfg.get("thumbnail"):
            try:
                preview_embed.set_thumbnail(url=thumb.format(**vars_dict))
            except KeyError as e:
                preview_embed.set_thumbnail(url=vars_dict["user_avatar"])
                preview_embed.add_field(name="⚠️ Aviso Thumbnail", value=f"Variável não encontrada: `{e}`", inline=False)

        if img := current_cfg.get("image"):
            try:
                preview_embed.set_image(url=img.format(**vars_dict))
            except KeyError as e:
                preview_embed.add_field(name="⚠️ Aviso Imagem", value=f"Variável não encontrada: `{e}`", inline=False)

        if foot := current_cfg.get("footer"):
            try:
                preview_embed.set_footer(text=foot.format(**vars_dict))
            except KeyError as e:
                preview_embed.set_footer(text=f"[ERRO no footer: {e}]")
                preview_embed.color = discord.Color.red()

        for idx, field in enumerate(current_cfg.get("fields", []), 1):
            try:
                name = field.get("name", f"Campo {idx}").format(**vars_dict)
                value = field.get("value", "—").format(**vars_dict)
                if name.strip() and value.strip():
                    preview_embed.add_field(name=name, value=value, inline=field.get("inline", False))
            except KeyError as e:
                preview_embed.add_field(name=f"Campo {idx} com erro", value=f"Variável não encontrada: `{e}`", inline=False)

        embeds = [instr, preview_embed]

        target_interaction = interaction or self.interaction

        if self.preview_msg:
            try:
                await self.preview_msg.edit(embeds=embeds, view=self)
            except discord.NotFound:
                self.preview_msg = None
        else:
            try:
                if target_interaction.response.is_done():
                    self.preview_msg = await target_interaction.followup.send(embeds=embeds, view=self, ephemeral=True)
                else:
                    self.preview_msg = await target_interaction.response.send_message(embeds=embeds, view=self, ephemeral=True)
            except Exception as e:
                print(f"Erro ao enviar preview: {e}")

    def save(self):
        data_to_save = {}
        for key, value in self.config.items():
            if value:
                data_to_save[key] = value
        
        if data_to_save:
            self.bot.db.moderation_embed_configs.update_one(
                {"guild_id": self.guild_id},
                {"$set": data_to_save},
                upsert=True
            )

    # Botões de edição (rows 1 a 4)
    @ui.button(label="Título", style=discord.ButtonStyle.primary, row=1, emoji="📝")
    async def edit_title(self, inter: discord.Interaction, _):
        await inter.response.send_modal(SimpleEditModal(self, "title", "Título"))

    @ui.button(label="Descrição", style=discord.ButtonStyle.primary, row=1, emoji="📄")
    async def edit_desc(self, inter: discord.Interaction, _):
        await inter.response.send_modal(SimpleEditModal(self, "description", "Descrição", paragraph=True))

    @ui.button(label="Cor", style=discord.ButtonStyle.primary, row=2, emoji="🎨")
    async def edit_color(self, inter: discord.Interaction, _):
        await inter.response.send_modal(SimpleEditModal(self, "color", "Cor (#RRGGBB)"))

    @ui.button(label="Thumbnail", style=discord.ButtonStyle.primary, row=2, emoji="🖼️")
    async def edit_thumbnail(self, inter: discord.Interaction, _):
        await inter.response.send_modal(SimpleEditModal(self, "thumbnail", "URL da thumbnail"))

    @ui.button(label="Imagem", style=discord.ButtonStyle.primary, row=3, emoji="🖼️")
    async def edit_image(self, inter: discord.Interaction, _):
        await inter.response.send_modal(SimpleEditModal(self, "image", "URL da imagem"))

    @ui.button(label="Footer", style=discord.ButtonStyle.secondary, row=3, emoji="📋")
    async def edit_footer(self, inter: discord.Interaction, _):
        await inter.response.send_modal(SimpleEditModal(self, "footer", "Texto do footer"))

    @ui.button(label="Campo 1", style=discord.ButtonStyle.secondary, row=4, emoji="1️⃣")
    async def edit_field1(self, inter: discord.Interaction, _):
        await inter.response.send_modal(FieldEditModal(self, 0))

    @ui.button(label="Campo 2", style=discord.ButtonStyle.secondary, row=4, emoji="2️⃣")
    async def edit_field2(self, inter: discord.Interaction, _):
        await inter.response.send_modal(FieldEditModal(self, 1))

    @ui.button(label="🔄 Resetar", style=discord.ButtonStyle.danger, row=4)
    async def reset_type(self, inter: discord.Interaction, _):
        if self.current_type == "default":
            await inter.response.send_message("⚠️ A configuração 'default' não pode ser resetada.", ephemeral=True)
            return

        self.config[self.current_type] = {}
        self.save()
        await self.update_preview(inter)
        
        await inter.response.send_message(f"✅ Configuração de **{self.current_type.upper()}** foi resetada.", ephemeral=True)

    async def on_timeout(self):
        if self.preview_msg:
            try:
                await self.preview_msg.edit(view=None)
            except:
                pass


# ================================================
# FUNÇÃO AUXILIAR PARA FORMATAR EMBEDS COM SEGURANÇA
# ================================================

def safe_format(template: str, vars_dict: dict) -> str:
    """Formata uma string com variáveis, tratando erros de forma segura."""
    try:
        return template.format(**vars_dict)
    except KeyError as e:
        return f"[ERRO: variável {e} não encontrada]"
    except Exception:
        return "[ERRO: falha ao formatar]"


# ================================================
# COG PRINCIPAL
# ================================================

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_embed_config(self, guild_id: int, action_type: str = "default") -> dict:
        db_data = self.bot.db.moderation_embed_configs.find_one({"guild_id": guild_id}) or {}
        return db_data.get(action_type, db_data.get("default", {}))

    def get_mod_config(self, guild_id: int) -> dict:
        default = {
            "guild_id": guild_id,
            "log_channel_id": None,
            "moderator_role_id": None,
            "warnings": {},
            "mutes": {}
        }
        cfg = self.bot.db.moderation_configs.find_one({"guild_id": guild_id}) or default
        cfg.setdefault("warnings", {})
        cfg.setdefault("mutes", {})
        return cfg

    def save_mod_config(self, config: dict):
        self.bot.db.moderation_configs.replace_one(
            {"guild_id": config["guild_id"]},
            config,
            upsert=True
        )

    async def send_punishment_log(self, guild: discord.Guild, action_type: str, **kwargs):
        embed_cfg = self.get_embed_config(guild.id, action_type)
        mod_cfg = self.get_mod_config(guild.id)
        log_channel_id = mod_cfg.get("log_channel_id")
        if not log_channel_id:
            return

        channel = guild.get_channel(log_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        vars_dict = {
            "user_name":     kwargs.get("user_name", "Usuário"),
            "user_mention":  kwargs.get("user_mention", "<@000000>"),
            "user_id":       str(kwargs.get("user_id", "000000")),
            "user_avatar":   kwargs.get("user_avatar") or "https://cdn.discordapp.com/embed/avatars/0.png",
            "moderator_name": kwargs.get("moderator_name", "Moderador"),
            "moderator_mention": kwargs.get("moderator_mention", "<@000000>"),
            "motivo":        kwargs.get("motivo", "Não informado"),
            "tempo":         kwargs.get("tempo", "Permanente"),
            "server_name":   guild.name,
            "timestamp":     discord.utils.format_dt(datetime.datetime.now(datetime.UTC), "F"),
            "action":        action_type.upper(),
        }

        embed = discord.Embed(
            title=safe_format(embed_cfg.get("title") or f"{action_type.upper()} aplicada", vars_dict),
            description=safe_format(embed_cfg.get("description") or "", vars_dict),
            color=embed_cfg.get("color", 0xff0000),
            timestamp=datetime.datetime.now(datetime.UTC)
        )

        if thumb := embed_cfg.get("thumbnail"):
            try:
                embed.set_thumbnail(url=thumb.format(**vars_dict))
            except KeyError:
                embed.set_thumbnail(url=vars_dict["user_avatar"])

        if img := embed_cfg.get("image"):
            try:
                embed.set_image(url=img.format(**vars_dict))
            except KeyError:
                pass

        if footer := embed_cfg.get("footer"):
            try:
                embed.set_footer(text=footer.format(**vars_dict))
            except KeyError:
                embed.set_footer(text=f"{action_type.upper()} • {guild.name}")

        for field in embed_cfg.get("fields", []):
            try:
                name = field.get("name", "—").format(**vars_dict)
                value = field.get("value", "—").format(**vars_dict)
                if name.strip() and value.strip():
                    embed.add_field(name=name, value=value, inline=field.get("inline", False))
            except:
                continue

        await channel.send(embed=embed)

    @app_commands.command(name="mod_embed", description="⚙️ Configura embeds separados para cada tipo de punição")
    @app_commands.default_permissions(administrator=True)
    async def mod_embed_config(self, interaction: discord.Interaction):
        view = ModEmbedConfigView(self.bot, interaction)
        await interaction.response.defer(ephemeral=True)
        await view.update_preview(interaction)

    @app_commands.command(name="log_channel", description="📢 Define o canal de logs de punições")
    @app_commands.default_permissions(administrator=True)
    async def log_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        cfg = self.get_mod_config(interaction.guild_id)
        cfg["log_channel_id"] = canal.id
        self.save_mod_config(cfg)
        await interaction.response.send_message(f"✅ Canal de logs definido: {canal.mention}", ephemeral=True)

    @app_commands.command(name="mod_role", description="👮 Cargo que recebe alertas (ex: 3 warns)")
    @app_commands.default_permissions(administrator=True)
    async def mod_role(self, interaction: discord.Interaction, cargo: discord.Role):
        cfg = self.get_mod_config(interaction.guild_id)
        cfg["moderator_role_id"] = cargo.id
        self.save_mod_config(cfg)
        await interaction.response.send_message(f"✅ Cargo de moderador definido: {cargo.mention}", ephemeral=True)

    @app_commands.command(name="warn", description="⚠️ Advertir usuário")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        if interaction.user.top_role <= membro.top_role and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Você não pode punir este usuário.", ephemeral=True)

        cfg = self.get_mod_config(interaction.guild_id)
        uid = str(membro.id)
        warns = cfg["warnings"].get(uid, 0) + 1
        cfg["warnings"][uid] = warns
        self.save_mod_config(cfg)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="warn",
            user_name=membro.name,
            user_mention=membro.mention,
            user_id=membro.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo="Advertência"
        )

        embed = discord.Embed(
            title="⚠️ Usuário Advertido",
            description=f"{membro.mention} recebeu uma advertência.",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo or "Não informado", inline=True)
        embed.add_field(name="📊 Advertências totais", value=f"**{warns}**", inline=True)

        if warns >= 3:
            mod_role = interaction.guild.get_role(cfg.get("moderator_role_id", 0))
            if mod_role:
                embed.add_field(
                    name="🚨 Aviso Importante",
                    value=f"{mod_role.mention} — Este usuário atingiu **3 ou mais advertências**!",
                    inline=False
                )

        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unwarn", description="✅ Remover 1 advertência de um usuário")
    @app_commands.default_permissions(manage_messages=True)
    async def unwarn(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Motivo não informado"):
        cfg = self.get_mod_config(interaction.guild_id)
        uid = str(membro.id)
        warns = cfg["warnings"].get(uid, 0)

        if warns <= 0:
            return await interaction.response.send_message(f"❌ {membro.mention} não tem advertências.", ephemeral=True)

        cfg["warnings"][uid] = warns - 1
        self.save_mod_config(cfg)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="unwarn",
            user_name=membro.name,
            user_mention=membro.mention,
            user_id=membro.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo=f"Restam {warns-1} warns"
        )

        embed = discord.Embed(
            title="✅ Advertência Removida",
            description=f"1 advertência foi removida de {membro.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo da remoção", value=motivo, inline=True)
        embed.add_field(name="📊 Advertências restantes", value=f"**{warns-1}**", inline=True)
        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="🔨 Banir um usuário permanentemente")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Motivo não informado"):
        if interaction.user.top_role <= membro.top_role and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Você não pode banir este usuário.", ephemeral=True)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        try:
            await membro.ban(reason=motivo)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ Sem permissão para banir este usuário.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Erro ao banir: {e}", ephemeral=True)

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="ban",
            user_name=membro.name,
            user_mention=membro.mention,
            user_id=membro.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo="Permanente"
        )

        embed = discord.Embed(
            title="🔨 Usuário Banido",
            description=f"{membro.mention} foi banido do servidor.",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=True)
        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unban", description="🔓 Desbanir um usuário pelo ID")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, motivo: str = "Motivo não informado"):
        try:
            user_id_int = int(user_id)
        except ValueError:
            return await interaction.response.send_message("❌ ID inválido. Use apenas números.", ephemeral=True)

        try:
            user = await self.bot.fetch_user(user_id_int)
        except discord.NotFound:
            return await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)

        try:
            await interaction.guild.unban(user, reason=motivo)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ Sem permissão para desbanir.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Erro ao desbanir: {e}", ephemeral=True)

        avatar_url = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="unban",
            user_name=user.name,
            user_mention=user.mention,
            user_id=user.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo="—"
        )

        embed = discord.Embed(
            title="🔓 Usuário Desbanido",
            description=f"{user.mention} foi desbanido do servidor.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=True)
        embed.set_footer(text=f"ID: {user.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mute", description="🔇 Mutar usuário por minutos")
    @app_commands.default_permissions(manage_roles=True)
    async def mute(self, interaction: discord.Interaction, membro: discord.Member, tempo_minutos: int, motivo: str):
        if tempo_minutos < 1 or tempo_minutos > 10080:
            return await interaction.response.send_message("❌ Tempo deve ser entre 1 minuto e 7 dias (10080 minutos).", ephemeral=True)

        muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not muted_role:
            return await interaction.response.send_message("❌ Crie o cargo **Muted** primeiro.", ephemeral=True)

        if muted_role in membro.roles:
            return await interaction.response.send_message(f"❌ {membro.mention} já está mutado.", ephemeral=True)

        try:
            await membro.add_roles(muted_role, reason=motivo)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ Sem permissão para mutar este usuário.", ephemeral=True)

        cfg = self.get_mod_config(interaction.guild_id)
        uid = str(membro.id)
        mutes = cfg["mutes"].get(uid, 0) + 1
        cfg["mutes"][uid] = mutes
        self.save_mod_config(cfg)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="mute",
            user_name=membro.name,
            user_mention=membro.mention,
            user_id=membro.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo=f"{tempo_minutos} minutos"
        )

        embed = discord.Embed(
            title="🔇 Usuário Mutado",
            description=f"{membro.mention} foi silenciado.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏱️ Tempo", value=f"{tempo_minutos} minutos", inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=True)
        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

        async def auto_unmute():
            await asyncio.sleep(tempo_minutos * 60)
            try:
                if muted_role in membro.roles:
                    await membro.remove_roles(muted_role, reason="Tempo de mute expirado")
            except:
                pass

        asyncio.create_task(auto_unmute())

    @app_commands.command(name="unmute", description="🔊 Desmutar usuário")
    @app_commands.default_permissions(manage_roles=True)
    async def unmute(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Motivo não informado"):
        muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not muted_role:
            return await interaction.response.send_message("❌ Cargo Muted não existe.", ephemeral=True)

        if muted_role not in membro.roles:
            return await interaction.response.send_message(f"❌ {membro.mention} não está mutado.", ephemeral=True)

        try:
            await membro.remove_roles(muted_role, reason=motivo)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ Sem permissão para desmutar.", ephemeral=True)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="unmute",
            user_name=membro.name,
            user_mention=membro.mention,
            user_id=membro.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo="—"
        )

        embed = discord.Embed(
            title="🔊 Usuário Desmutado",
            description=f"{membro.mention} teve o mute removido.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=True)
        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="infractions", description="📋 Ver warns e mutes de um membro")
    @app_commands.default_permissions(manage_messages=True)
    async def infractions(self, interaction: discord.Interaction, membro: discord.Member):
        cfg = self.get_mod_config(interaction.guild_id)
        uid = str(membro.id)

        warns = cfg.get("warnings", {}).get(uid, 0)
        mutes = cfg.get("mutes", {}).get(uid, 0)

        if warns >= 5:
            status = "🚨 Crítico"
        elif warns >= 3:
            status = "⚠️ Alerta"
        elif warns >= 1:
            status = "📝 Atenção"
        else:
            status = "✅ Limpo"

        embed = discord.Embed(
            title=f"📋 Infrações — {membro.name}",
            description=membro.mention,
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.add_field(name="⚠️ Advertências (warns)", value=str(warns), inline=True)
        embed.add_field(name="🔇 Mutes recebidos", value=str(mutes), inline=True)
        embed.add_field(name="📊 Status", value=status, inline=True)
        embed.set_footer(text=f"ID: {membro.id} • Servidor: {interaction.guild.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear_warns", description="🗑️ Limpar todas as advertências de um usuário")
    @app_commands.default_permissions(manage_messages=True)
    async def clear_warns(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Limpeza manual"):
        cfg = self.get_mod_config(interaction.guild_id)
        uid = str(membro.id)
        warns_antes = cfg["warnings"].get(uid, 0)

        if warns_antes == 0:
            return await interaction.response.send_message(f"❌ {membro.mention} não tem advertências para limpar.", ephemeral=True)

        cfg["warnings"][uid] = 0
        self.save_mod_config(cfg)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        await self.send_punishment_log(
            guild=interaction.guild,
            action_type="unwarn",
            user_name=membro.name,
            user_mention=membro.mention,
            user_id=membro.id,
            user_avatar=avatar_url,
            moderator_name=interaction.user.name,
            moderator_mention=interaction.user.mention,
            motivo=motivo,
            tempo=f"Removidas {warns_antes} advertências"
        )

        embed = discord.Embed(
            title="🗑️ Advertências Limpas",
            description=f"Todas as advertências foram removidas de {membro.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=True)
        embed.add_field(name="🗑️ Advertências removidas", value=f"**{warns_antes}**", inline=True)
        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kick", description="🦶 Expulsar um usuário")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membro: discord.Member, motivo: str = "Motivo não informado"):
        if interaction.user.top_role <= membro.top_role and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Você não pode expulsar este usuário.", ephemeral=True)

        avatar_url = membro.avatar.url if membro.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

        try:
            await membro.kick(reason=motivo)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ Sem permissão para expulsar este usuário.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Erro ao expulsar: {e}", ephemeral=True)

        embed = discord.Embed(
            title="🦶 Usuário Expulsado",
            description=f"{membro.mention} foi expulsado do servidor.",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👮 Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=True)
        embed.set_footer(text=f"ID: {membro.id} • {interaction.guild.name}")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Moderation(bot))