import discord
from discord import app_commands, Interaction
from discord.ext import commands
import asyncio

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Limpa o chat (até 100 mensagens recentes) - Admin")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        quantidade="Número de mensagens a apagar (máx 100)",
        confirm="Digite 'SIM' para confirmar"
    )
    async def clear(self, interaction: Interaction, quantidade: int, confirm: str):
        if confirm.upper() != "SIM":
            return await interaction.response.send_message("Comando cancelado. Para confirmar, digite `SIM` no campo confirm.", ephemeral=True)

        if quantidade < 1 or quantidade > 100:
            return await interaction.response.send_message("Quantidade inválida. Use entre 1 e 100.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=quantidade, bulk=True)
            count = len(deleted)

            embed = discord.Embed(
                title="Chat Limpo",
                description=f"Foram apagadas **{count} mensagens**.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Executado por {interaction.user}")

            await interaction.followup.send(embed=embed, ephemeral=False)

        except discord.Forbidden:
            await interaction.followup.send("Não tenho permissão para apagar mensagens aqui.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Erro ao apagar mensagens: {e}", ephemeral=True)

    @clear.error
    async def clear_error(self, interaction: Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Você precisa da permissão `Gerenciar Mensagens` para usar este comando.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erro inesperado: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Clear(bot))