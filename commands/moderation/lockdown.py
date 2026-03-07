# commands/moderation/lockdown.py
import discord
from discord import app_commands
from discord.ext import commands
import datetime

class Lockdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_config(self, guild_id: int):
        return self.bot.db.lockdown_configs.find_one({"guild_id": guild_id}) or {
            "guild_id": guild_id,
            "whitelist_channels": [],
            "allowed_roles": [],
            "lockdown_active": False  # Novo: status do lockdown
        }

    def save_config(self, config):
        self.bot.db.lockdown_configs.replace_one(
            {"guild_id": config["guild_id"]},
            config,
            upsert=True
        )

    @app_commands.command(name="lockdown", description="Ativa o lockdown no servidor (bloqueia mensagens em canais públicos)")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = self.get_config(guild.id)

        if config["lockdown_active"]:
            await interaction.response.send_message("Lockdown já está ativo.", ephemeral=True)
            return

        config["lockdown_active"] = True
        self.save_config(config)

        embed = discord.Embed(
            title="🔒 Lockdown Ativado",
            description=(
                "O servidor entrou em **lockdown**.\n"
                "Mensagens em canais públicos foram bloqueadas para @everyone.\n"
                f"Canais na whitelist: {len(config['whitelist_channels'])}\n"
                f"Cargos que ainda podem falar: {len(config['allowed_roles'])}"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Executado por {interaction.user}")
        embed.timestamp = datetime.datetime.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)

        changed_channels = 0
        for channel in guild.text_channels:
            if channel.id in config["whitelist_channels"]:
                continue

            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is not False:
                overwrite.send_messages = False
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                changed_channels += 1

            for role_id in config["allowed_roles"]:
                role = guild.get_role(role_id)
                if role:
                    role_overwrite = channel.overwrites_for(role)
                    role_overwrite.send_messages = True
                    await channel.set_permissions(role, overwrite=role_overwrite)

        followup_embed = discord.Embed(
            title="Lockdown Concluído",
            description=f"**{changed_channels} canais** foram bloqueados.\nUse `/unlockdown` para reverter.",
            color=discord.Color.dark_red()
        )
        await interaction.followup.send(embed=followup_embed, ephemeral=True)

    @app_commands.command(name="unlockdown", description="Remove o lockdown do servidor (libera mensagens)")
    @app_commands.default_permissions(manage_guild=True)
    async def unlockdown(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = self.get_config(guild.id)

        if not config["lockdown_active"]:
            await interaction.response.send_message("Lockdown já está desativado.", ephemeral=True)
            return

        config["lockdown_active"] = False
        self.save_config(config)

        embed = discord.Embed(
            title="🔓 Lockdown Removido",
            description="O servidor voltou ao normal.\nMensagens liberadas em todos os canais.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Executado por {interaction.user}")
        embed.timestamp = datetime.datetime.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)

        changed_channels = 0
        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is False:
                overwrite.send_messages = None
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                changed_channels += 1

        followup_embed = discord.Embed(
            title="Unlockdown Concluído",
            description=f"**{changed_channels} canais** foram liberados.",
            color=discord.Color.dark_green()
        )
        await interaction.followup.send(embed=followup_embed, ephemeral=True)

    # Whitelist de canais
    @app_commands.command(name="lockdown_channel_add", description="Adiciona um canal à whitelist do lockdown")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown_channel_add(self, interaction: discord.Interaction, canal: discord.TextChannel):
        config = self.get_config(interaction.guild.id)
        if canal.id not in config["whitelist_channels"]:
            config["whitelist_channels"].append(canal.id)
            self.save_config(config)
            await interaction.response.send_message(f"Canal {canal.mention} adicionado à whitelist do lockdown.", ephemeral=True)
        else:
            await interaction.response.send_message(f"O canal {canal.mention} já está na whitelist.", ephemeral=True)

    @app_commands.command(name="lockdown_channel_remove", description="Remove um canal da whitelist do lockdown")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown_channel_remove(self, interaction: discord.Interaction, canal: discord.TextChannel):
        config = self.get_config(interaction.guild.id)
        if canal.id in config["whitelist_channels"]:
            config["whitelist_channels"].remove(canal.id)
            self.save_config(config)
            await interaction.response.send_message(f"Canal {canal.mention} removido da whitelist do lockdown.", ephemeral=True)
        else:
            await interaction.response.send_message(f"O canal {canal.mention} não está na whitelist.", ephemeral=True)

    # Cargos permitidos para falar no lockdown
    @app_commands.command(name="lockdown_role_add", description="Adiciona um cargo que pode continuar falando durante o lockdown")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown_role_add(self, interaction: discord.Interaction, cargo: discord.Role):
        config = self.get_config(interaction.guild.id)
        if cargo.id not in config["allowed_roles"]:
            config["allowed_roles"].append(cargo.id)
            self.save_config(config)
            await interaction.response.send_message(f"Cargo {cargo.mention} agora pode falar durante o lockdown.", ephemeral=True)
        else:
            await interaction.response.send_message(f"O cargo {cargo.mention} já está permitido.", ephemeral=True)

    @app_commands.command(name="lockdown_role_remove", description="Remove um cargo da permissão de falar durante o lockdown")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown_role_remove(self, interaction: discord.Interaction, cargo: discord.Role):
        config = self.get_config(interaction.guild.id)
        if cargo.id in config["allowed_roles"]:
            config["allowed_roles"].remove(cargo.id)
            self.save_config(config)
            await interaction.response.send_message(f"Cargo {cargo.mention} removido da permissão de falar no lockdown.", ephemeral=True)
        else:
            await interaction.response.send_message(f"O cargo {cargo.mention} não está na lista de permitidos.", ephemeral=True)

    # Novo comando: Status do lockdown
    @app_commands.command(name="lockdown_status", description="Mostra o status atual do lockdown, whitelist de canais e cargos permitidos")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown_status(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)

        status = "Ativado 🔒" if config.get("lockdown_active", False) else "Desativado 🔓"
        channels = [f"<#{cid}>" for cid in config["whitelist_channels"]]
        roles = [f"<@&{rid}>" for rid in config["allowed_roles"]]

        embed = discord.Embed(
            title="Status do Lockdown",
            description=f"**Estado atual:** {status}",
            color=discord.Color.blue() if config.get("lockdown_active", False) else discord.Color.green()
        )
        embed.add_field(
            name="Canais na Whitelist (não afetados)",
            value="\n".join(channels) or "Nenhum canal na whitelist",
            inline=False
        )
        embed.add_field(
            name="Cargos que podem falar durante o lockdown",
            value="\n".join(roles) or "Nenhum cargo permitido",
            inline=False
        )
        embed.set_footer(text=f"Última atualização: {discord.utils.format_dt(datetime.datetime.utcnow(), 'F')}")
        embed.timestamp = datetime.datetime.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Lockdown(bot))