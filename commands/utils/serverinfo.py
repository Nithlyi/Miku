import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="Mostra informações do servidor")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"Informações do Servidor: {guild.name}",
            color=0x040505
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        embed.add_field(name="📋 Nome", value=guild.name, inline=True)
        embed.add_field(name="🆔 ID", value=guild.id, inline=True)
        embed.add_field(name="👑 Dono", value=guild.owner.mention if guild.owner else "Desconhecido", inline=True)
        
        embed.add_field(name="👥 Membros", value=f"{guild.member_count} membros", inline=True)
        embed.add_field(name="💬 Canais de Texto", value=len(guild.text_channels), inline=True)
        embed.add_field(name="🔊 Canais de Voz", value=len(guild.voice_channels), inline=True)
        
        embed.add_field(name="🏷️ Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="🚀 Boosts", value=guild.premium_subscription_count, inline=True)
        embed.add_field(name="📅 Criado em", value=guild.created_at.strftime("%d/%m/%Y %H:%M"), inline=True)
        
        embed.add_field(name="🔒 Nível de Verificação", value=str(guild.verification_level).capitalize(), inline=True)
        embed.add_field(name="🌍 Região", value=str(guild.preferred_locale), inline=True)
        embed.add_field(name="📊 Status", value="Online" if guild.system_channel else "Offline", inline=True)
        
        embed.set_footer(text=f"Solicitado por {interaction.user}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerInfo(bot))