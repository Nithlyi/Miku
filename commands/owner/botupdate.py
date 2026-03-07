import discord
from discord import app_commands, Interaction, Embed, Colour, SelectOption
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
import aiohttp
import asyncio


# Check local (definido aqui mesmo para evitar import de utils)
async def is_bot_owner(interaction: discord.Interaction) -> bool:
    return await interaction.client.is_owner(interaction.user)


class BotUpdateModal(Modal):
    def __init__(self, view: 'BotUpdateView', feature: str):
        super().__init__(title=f"Atualizar {feature.title()}")
        self.view = view
        self.feature = feature

        if feature == 'status':
            self.add_item(TextInput(
                label="Texto do Status",
                placeholder="Ex: Jogando xAI | /help",
                required=True,
                max_length=128
            ))
            self.add_item(TextInput(
                label="Tipo de Status",
                placeholder="playing | streaming | listening | watching | competing",
                default="playing",
                required=True
            ))

    async def on_submit(self, interaction: Interaction):
        if self.feature == 'status':
            text = self.children[0].value.strip()
            type_str = self.children[1].value.strip().lower()

            activity_map = {
                'playing': discord.Activity(type=discord.ActivityType.playing, name=text),
                'streaming': discord.Activity(type=discord.ActivityType.streaming, name=text, url="https://twitch.tv/exemplo"),
                'listening': discord.Activity(type=discord.ActivityType.listening, name=text),
                'watching': discord.Activity(type=discord.ActivityType.watching, name=text),
                'competing': discord.Activity(type=discord.ActivityType.competing, name=text),
            }

            activity = activity_map.get(type_str, discord.Activity(type=discord.ActivityType.playing, name=text))

            await self.view.bot.change_presence(activity=activity)
            await interaction.response.send_message(
                f"Status atualizado!\n**{type_str.title()} {text}**",
                ephemeral=True
            )


class BotUpdateView(View):
    def __init__(self, interaction: Interaction, bot: commands.Bot):
        super().__init__(timeout=1800)
        self.original_interaction = interaction
        self.bot = bot

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    async def update_bot_image(self, interaction: Interaction, is_banner: bool = False):
        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.followup.send(
                f"Envie a imagem para o **{'banner' if is_banner else 'avatar'}** do bot (anexe na próxima mensagem).\n"
                f"Você tem **60 segundos**.",
                ephemeral=True
            )

            def check(m: discord.Message):
                return m.author.id == interaction.user.id and m.attachments and m.channel == interaction.channel

            msg = await self.bot.wait_for('message', check=check, timeout=60.0)

            attachment = msg.attachments[0]
            if not attachment.content_type.startswith('image/'):
                await interaction.followup.send("Envie uma imagem válida (PNG, JPG, GIF, WEBP).", ephemeral=True)
                return

            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("Falha ao baixar a imagem.", ephemeral=True)
                        return
                    image_data = await resp.read()

            if is_banner:
                await self.bot.user.edit(banner=image_data)
                await interaction.followup.send("**Banner do bot atualizado com sucesso!**", ephemeral=True)
            else:
                await self.bot.user.edit(avatar=image_data)
                await interaction.followup.send("**Avatar do bot atualizado com sucesso!**", ephemeral=True)

        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. Nenhuma imagem enviada.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Erro ao atualizar: {str(e)}", ephemeral=True)

    @discord.ui.select(
        placeholder="O que você deseja atualizar?",
        options=[
            SelectOption(label="Status (jogando, assistindo...)", value="status", emoji="📝"),
            SelectOption(label="Avatar (foto de perfil)", value="avatar", emoji="🖼️"),
            SelectOption(label="Banner (capa do perfil)", value="banner", emoji="🎨"),
        ],
        custom_id="bot_update_select",
        row=0
    )
    async def update_select(self, interaction: Interaction, select: Select):
        selected = select.values[0]

        if selected == 'status':
            modal = BotUpdateModal(self, selected)
            await interaction.response.send_modal(modal)

        elif selected == 'avatar':
            await self.update_bot_image(interaction, is_banner=False)

        elif selected == 'banner':
            await self.update_bot_image(interaction, is_banner=True)


class BotUpdate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="botupdate", description="Atualiza status, avatar ou banner do bot (apenas dono)")
    @app_commands.check(is_bot_owner)
    async def botupdate(self, interaction: Interaction):
        view = BotUpdateView(interaction, self.bot)

        embed = Embed(
            title="Painel de Atualização do Bot",
            description=(
                "Selecione abaixo o que deseja alterar:\n\n"
                "• **Status** → altera a atividade do bot\n"
                "• **Avatar** → foto de perfil\n"
                "• **Banner** → capa do perfil (se suportado)\n\n"
                "**Atenção:**\n"
                "Para avatar/banner: envie a imagem na próxima mensagem após selecionar a opção."
            ),
            color=discord.Color.from_str("#1A1A1A")
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @botupdate.error
    async def botupdate_error(self, interaction: Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ Apenas o **dono do bot** pode usar este comando.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Erro: {str(error)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BotUpdate(bot))