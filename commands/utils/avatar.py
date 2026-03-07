import discord
from discord import app_commands
from discord.ext import commands


class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="avatar", description="Mostra o avatar de um usuário")
    @app_commands.describe(usuario="Usuário para ver o avatar")
    async def avatar(self, interaction: discord.Interaction, usuario: discord.Member = None):
        user = usuario or interaction.user
        
        embed = discord.Embed(
            title=f"Avatar de {user.name}",
            color=0x040505
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(name="ID", value=f"`{user.id}`", inline=False)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Baixar Avatar",
            url=user.display_avatar.url,
            style=discord.ButtonStyle.link
        ))
        
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Avatar(bot))