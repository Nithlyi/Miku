import discord
from discord import app_commands
from discord.ext import commands
import datetime

class BotInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()

    def get_bot_uptime(self):
        now = datetime.datetime.utcnow()
        delta = now - self.start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    @app_commands.command(name="botinfo", description="✨ Informações do bot")
    async def botinfo(self, interaction: discord.Interaction):
        # Estatísticas básicas
        total_members = sum(guild.member_count for guild in self.bot.guilds)
        uptime = self.get_bot_uptime()
        ping = round(self.bot.latency * 1000)
        
        # Embed dark e minimalista
        embed = discord.Embed(
            title=f"**{self.bot.user.name}**",
            description="Informaçoes do bot:",
            color=0x0a0a0a  # Preto suave
        )
        
        # Avatar do bot como thumbnail
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        # Informações em campos organizados
        embed.add_field(name="👑 **dono**", value="`Evy`", inline=True)
        embed.add_field(name="📊 **servidores**", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 **usuários**", value=f"`{total_members}`", inline=True)
        
        embed.add_field(name="🏓 **ping**", value=f"`{ping}ms`", inline=True)
        embed.add_field(name="⏰ **uptime**", value=f"`{uptime}`", inline=True)
        embed.add_field(name="📁 **comandos**", value="`55`", inline=True)
        
        # Rodapé sutil
        embed.set_footer(
            text=f"solicitado por {interaction.user.name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(BotInfo(bot))