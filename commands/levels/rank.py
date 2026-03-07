# commands/levels/rank.py
import discord
from discord import app_commands, ui
from discord.ext import commands
import math

class RankView(ui.View):
    def __init__(self, bot, interaction: discord.Interaction, is_global: bool = False, page: int = 0):
        super().__init__(timeout=180)
        self.bot = bot
        self.interaction = interaction
        self.guild_id = interaction.guild_id
        self.is_global = is_global
        self.page = page
        self.per_page = 10

    async def get_data(self):
        if self.is_global:
            pipeline = [
                {"$group": {"_id": "$user_id", "total_xp": {"$sum": "$xp"}, "highest_level": {"$max": "$level"}}},
                {"$sort": {"total_xp": -1}},
                {"$limit": 100}
            ]
            return list(self.bot.db.levels.aggregate(pipeline))
        else:
            return list(self.bot.db.levels.find({"guild_id": self.guild_id}).sort("xp", -1).limit(100))

    async def generate_embed(self):
        data = await self.get_data()
        total_entries = len(data)
        total_pages = math.ceil(total_entries / self.per_page) if total_entries > 0 else 1

        start = self.page * self.per_page
        end = min(start + self.per_page, total_entries)
        page_entries = data[start:end]

        embed = discord.Embed(
            title=f"🏆 Leaderboard {'Global' if self.is_global else 'do Servidor'}",
            color=discord.Color.from_str("#1A1A1A"),
            timestamp=discord.utils.utcnow()
        )

        if not page_entries:
            embed.description = "Nenhum dado de XP encontrado ainda."
            return embed

        for idx, entry in enumerate(page_entries, start=start + 1):
            user_id = entry["_id"] if self.is_global else entry["user_id"]
            xp = entry["total_xp"] if self.is_global else entry["xp"]
            level = entry["highest_level"] if self.is_global else entry["level"]

            try:
                user = await self.bot.fetch_user(user_id)
                display_name = user.global_name or user.name  # Prioriza nome de exibição
            except discord.NotFound:
                display_name = f"Usuário desconhecido ({user_id})"

            # Destaca o próprio usuário
            if user_id == self.interaction.user.id:
                name_display = f"**{display_name}** ← você"
            else:
                name_display = display_name

            embed.add_field(
                name=f"#{idx} {name_display}",
                value=f"Nível **{level}** • XP **{xp:,}**",
                inline=False
            )

        embed.set_footer(text=f"Página {self.page + 1}/{total_pages} • Total: {total_entries} membros • Atual: {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}")
        return embed

    @ui.button(label="◀ Anterior", style=discord.ButtonStyle.grey)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.page > 0:
            self.page -= 1
            embed = await self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Próxima ▶", style=discord.ButtonStyle.grey)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        data = await self.get_data()
        if (self.page + 1) * self.per_page < len(data):
            self.page += 1
            embed = await self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Alternar Global / Servidor", style=discord.ButtonStyle.blurple)
    async def toggle_global(self, interaction: discord.Interaction, button: ui.Button):
        self.is_global = not self.is_global
        self.page = 0
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class Rank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rank", description="Leaderboard interativo do servidor ou global")
    async def rank(self, interaction: discord.Interaction):
        view = RankView(self.bot, interaction)
        embed = await view.generate_embed()
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Rank(bot))