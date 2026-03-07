import discord
from discord import app_commands, Interaction, Embed, Colour, SelectOption
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput


class EmbedBuilderModal(Modal):
    def __init__(self, view: 'EmbedBuilderView', field: str):
        super().__init__(title=f"Editar {field.replace('_', ' ').title()}")
        self.view = view
        self.field = field

        embed = self.view.current_embed

        if field == 'title':
            current_title = embed.title if embed.title else ""
            current_url = embed.url if embed.url else ""
            self.add_item(TextInput(
                label="Título",
                placeholder="Digite o título",
                default=current_title,
                max_length=256,
                required=False
            ))
            self.add_item(TextInput(
                label="URL do Título (opcional)",
                placeholder="Link ao clicar no título",
                default=current_url,
                required=False
            ))

        elif field == 'description':
            current_desc = embed.description if embed.description and embed.description != "ㅤ" else ""
            self.add_item(TextInput(
                label="Descrição",
                placeholder="Digite a descrição",
                style=discord.TextStyle.paragraph,
                default=current_desc,
                max_length=4000,
                required=False
            ))

        elif field == 'color':
            current_color = ""
            if embed.color and embed.color.value:
                current_color = f"#{embed.color.value:06x}"
            self.add_item(TextInput(
                label="Cor (hex)",
                placeholder="#FF0000 ou 0xFF0000",
                default=current_color,
                required=False
            ))

        elif field == 'footer':
            current_text = embed.footer.text if embed.footer.text else ""
            current_icon = embed.footer.icon_url if embed.footer.icon_url else ""
            self.add_item(TextInput(
                label="Texto do Footer",
                placeholder="Texto pequeno embaixo",
                default=current_text,
                max_length=2048,
                required=False
            ))
            self.add_item(TextInput(
                label="Ícone do Footer (URL)",
                placeholder="Link da imagem",
                default=str(current_icon) if current_icon else "",
                required=False
            ))

        elif field == 'author':
            current_name = embed.author.name if embed.author.name else ""
            current_url = embed.author.url if embed.author.url else ""
            current_icon = embed.author.icon_url if embed.author.icon_url else ""
            self.add_item(TextInput(
                label="Nome do Autor",
                default=current_name,
                max_length=256,
                required=False
            ))
            self.add_item(TextInput(
                label="URL do Autor (opcional)",
                placeholder="Link ao clicar",
                default=current_url,
                required=False
            ))
            self.add_item(TextInput(
                label="Ícone do Autor (URL)",
                placeholder="Link da imagem",
                default=str(current_icon) if current_icon else "",
                required=False
            ))

        elif field == 'image':
            current_image = embed.image.url if embed.image.url else ""
            self.add_item(TextInput(
                label="URL da Imagem",
                placeholder="Link da imagem principal",
                default=current_image,
                required=False
            ))

        elif field == 'thumbnail':
            current_thumb = embed.thumbnail.url if embed.thumbnail.url else ""
            self.add_item(TextInput(
                label="URL da Thumbnail",
                placeholder="Link da imagem pequena",
                default=current_thumb,
                required=False
            ))

        elif field == 'add_field':
            # Para adicionar campo novo, não pré-preenche (é sempre novo)
            self.add_item(TextInput(label="Nome do Campo", max_length=256, required=True))
            self.add_item(TextInput(
                label="Valor do Campo",
                style=discord.TextStyle.paragraph,
                max_length=1024,
                required=True
            ))
            self.add_item(TextInput(
                label="Inline? (sim/não)",
                placeholder="sim ou não",
                default="não",
                required=False
            ))

    async def on_submit(self, interaction: Interaction):
        if self.field == 'title':
            title = self.children[0].value.strip()
            url = self.children[1].value.strip()
            if title:
                self.view.current_embed.title = title
            else:
                self.view.current_embed.title = None
            if url:
                self.view.current_embed.url = url
            else:
                self.view.current_embed.url = None

        elif self.field == 'description':
            desc = self.children[0].value.strip()
            self.view.current_embed.description = desc if desc else None

        elif self.field == 'color':
            color_str = self.children[0].value.strip()
            if color_str:
                try:
                    if color_str.startswith('#'):
                        color_int = int(color_str[1:], 16)
                    elif color_str.startswith('0x'):
                        color_int = int(color_str, 16)
                    else:
                        color_int = int(color_str, 16)
                    self.view.current_embed.color = Colour(color_int)
                except ValueError:
                    await interaction.followup.send("Cor inválida. Use formato #RRGGBB.", ephemeral=True)
                    return

        elif self.field == 'footer':
            text = self.children[0].value.strip()
            icon = self.children[1].value.strip()
            self.view.current_embed.set_footer(
                text=text if text else None,
                icon_url=icon if icon else None
            )

        elif self.field == 'author':
            name = self.children[0].value.strip()
            url = self.children[1].value.strip()
            icon = self.children[2].value.strip()
            self.view.current_embed.set_author(
                name=name if name else None,
                url=url if url else None,
                icon_url=icon if icon else None
            )

        elif self.field == 'image':
            url = self.children[0].value.strip()
            if url:
                self.view.current_embed.set_image(url=url)
            else:
                self.view.current_embed.set_image(url=None)

        elif self.field == 'thumbnail':
            url = self.children[0].value.strip()
            if url:
                self.view.current_embed.set_thumbnail(url=url)
            else:
                self.view.current_embed.set_thumbnail(url=None)

        elif self.field == 'add_field':
            name = self.children[0].value.strip()
            value = self.children[1].value.strip()
            inline_str = self.children[2].value.strip().lower()
            inline = inline_str in ('sim', 's', 'yes', 'y', 'true', '1')
            self.view.current_embed.add_field(name=name, value=value or "ㅤ", inline=inline)

        await interaction.response.defer()
        await self.view.update_preview()


class EmbedBuilderView(View):
    def __init__(self, interaction: Interaction):
        super().__init__(timeout=1800)
        self.original_interaction = interaction
        self.preview_message = None
        self.current_embed = Embed(
            title="Pré-visualização do Embed",
            description="Use o menu para editar",
            color=Colour.blurple()
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    async def update_preview(self):
        embed = self.current_embed.copy()
        if not embed.description:
            embed.description = "ㅤ"
        if not embed.title:
            embed.title = "Pré-visualização do Embed"

        if self.preview_message:
            try:
                await self.preview_message.edit(embed=embed, view=self)
            except discord.NotFound:
                self.preview_message = None

        if not self.preview_message:
            self.preview_message = await self.original_interaction.followup.send(
                embed=embed, view=self, ephemeral=True
            )

    @discord.ui.select(
        placeholder="Escolha o que editar...",
        options=[
            SelectOption(label="Título + URL", value="title", emoji="✏️"),
            SelectOption(label="Descrição", value="description", emoji="📝"),
            SelectOption(label="Cor", value="color", emoji="🎨"),
            SelectOption(label="Autor", value="author", emoji="👤"),
            SelectOption(label="Footer", value="footer", emoji="📌"),
            SelectOption(label="Imagem Principal", value="image", emoji="🖼️"),
            SelectOption(label="Thumbnail", value="thumbnail", emoji="🖼️"),
            SelectOption(label="Adicionar Campo", value="add_field", emoji="➕"),
        ],
        custom_id="embed_edit_select",
        row=0
    )
    async def edit_select(self, interaction: Interaction, select: Select):
        selected = select.values[0]
        modal = EmbedBuilderModal(self, selected)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Limpar Campos", style=discord.ButtonStyle.grey, row=1)
    async def clear_fields(self, interaction: Interaction, _):
        self.current_embed.clear_fields()
        await interaction.response.defer()
        await self.update_preview()

    @discord.ui.button(label="Enviar Embed", style=discord.ButtonStyle.green, row=1)
    async def send_embed(self, interaction: Interaction, _):
        await interaction.channel.send(embed=self.current_embed)
        await interaction.response.send_message("Embed enviado com sucesso!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, row=1)
    async def cancel(self, interaction: Interaction, _):
        await interaction.response.send_message("Criação cancelada.", ephemeral=True)
        self.stop()


class EmbedCreator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embedcreator", description="Cria um embed personalizado com preview em tempo real")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embedcreator(self, interaction: Interaction):
        view = EmbedBuilderView(interaction)
        await interaction.response.send_message("Iniciando criador de embed...", ephemeral=True)
        await view.update_preview()


async def setup(bot):
    await bot.add_cog(EmbedCreator(bot))