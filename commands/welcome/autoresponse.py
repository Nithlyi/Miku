import discord
from discord.ext import commands

class AutoResponseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        config = self.bot.db.guild_configs.find_one({"guild_id": guild_id}) or {}
        responses = config.get("auto_responses", {})  # ex: {"oi": "Olá!", "tchau": "Até mais!"}

        content_lower = message.content.lower()
        for trigger, reply in responses.items():
            if trigger in content_lower:
                await message.channel.send(reply)
                break  # responde só uma vez por mensagem

async def setup(bot):
    await bot.add_cog(AutoResponseCog(bot))