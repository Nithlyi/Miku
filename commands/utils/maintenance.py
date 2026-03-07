# commands/utils/maintenance.py
import discord
from discord import app_commands, ui
from discord.ext import commands

# Seu ID de dono (substitua pelo seu real!)
OWNER_ID = 123456789012345678  # ← COLOQUE SEU ID AQUI

class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Carrega o estado do banco (ou False se não existir)
        doc = self.bot.db.configs.find_one({"key": "maintenance_mode"})
        self.maintenance_mode = doc["value"] if doc else False

    async def cog_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID

    @app_commands.command(name="maintenance", description="Ativa ou desativa o modo de manutenção (apenas dono)")
    @app_commands.describe(ativar="True para ativar, False para desativar")
    async def maintenance(self, interaction: discord.Interaction, ativar: bool):
        self.maintenance_mode = ativar

        # Salva no banco
        self.bot.db.configs.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"value": ativar}},
            upsert=True
        )

        if ativar:
            embed = discord.Embed(
                title="🔧 Modo de Manutenção Ativado",
                description=(
                    "O bot agora está em **manutenção**.\n"
                    "Todos os comandos foram temporariamente bloqueados (exceto este).\n"
                    "Eventos automáticos (welcome, goodbye, tickets, etc.) continuam funcionando normalmente."
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="Use /maintenance false para desativar")
        else:
            embed = discord.Embed(
                title="✅ Manutenção Encerrada",
                description="O bot voltou ao modo normal.\nTodos os comandos estão liberados novamente.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Status atual: Operacional")

        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Bloqueia comandos quando em manutenção
    @commands.Cog.listener()
    async def on_app_command_invoke(self, interaction: discord.Interaction):
        if self.maintenance_mode:
            # Permite apenas o comando de manutenção
            if interaction.command.name == "maintenance":
                return

            embed = discord.Embed(
                title="🔧 Bot em Manutenção",
                description=(
                    "Desculpe, o bot está passando por manutenção no momento.\n"
                    "Todos os comandos estão temporariamente bloqueados.\n"
                    "Volte mais tarde ou entre em contato com o dono para mais informações."
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="Manutenção ativa • Não afeta eventos automáticos")
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1268456789012345678.webp?size=96")  # emoji de ferramenta ou use um seu

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False  # Cancela o comando


async def setup(bot):
    await bot.add_cog(Maintenance(bot))