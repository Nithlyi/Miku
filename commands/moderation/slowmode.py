import discord
from discord import app_commands
from discord.ext import commands

class Slowmode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slowmode", description="Define o slowmode em um canal")
    @app_commands.describe(duracao="Duração em segundos (0 para desativar)", canal="Canal (padrão: atual)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, duracao: int, canal: discord.TextChannel = None):
        if canal is None:
            canal = interaction.channel
        
        if duracao < 0 or duracao > 21600:  # Máximo 6 horas
            await interaction.response.send_message("Duração inválida. Deve ser entre 0 e 21600 segundos.", ephemeral=True)
            return
        
        try:
            await canal.edit(slowmode_delay=duracao)
            embed = discord.Embed(
                title="Slowmode Definido",
                description=f"Slowmode em {canal.mention} definido para {duracao} segundos.",
                color=0x010202
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("Não tenho permissão para alterar o slowmode neste canal.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Erro: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Slowmode(bot))