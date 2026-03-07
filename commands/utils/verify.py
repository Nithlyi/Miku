import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Classes auxiliares movidas para fora da cog para persistência
class VerifySelect(Select):
    def __init__(self, cog, roles_dict, categoria, placeholder="Escolha uma opção..."):
        self.cog = cog
        self.categoria = categoria
        options = [discord.SelectOption(label=nome, value=nome) for nome in roles_dict.keys()]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, custom_id=f"verify:{categoria}")

    async def callback(self, interaction: discord.Interaction):
        opcao_nome = self.values[0]
        roles_dict = getattr(self.cog, f"roles_{self.categoria}")
        cor_hex = roles_dict[opcao_nome]
        
        # Verifica e remove roles antigos da categoria
        user = interaction.user
        roles_removidos = 0
        for r in user.roles:
            if r.name in roles_dict.keys():
                await user.remove_roles(r)
                roles_removidos += 1
        
        # Tenta encontrar ou criar o role
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=opcao_nome)
        if not role:
            role = await guild.create_role(name=opcao_nome, color=discord.Color(cor_hex))
        
        # Atribui o novo role
        await user.add_roles(role)
        
        # Mensagem de confirmação
        if roles_removidos > 0:
            await interaction.response.send_message(f"'{opcao_nome}' atribuído a você! ({roles_removidos} opção(ões) antiga(s) removida(s) da categoria {self.categoria})", ephemeral=True)
        else:
            await interaction.response.send_message(f"'{opcao_nome}' atribuído a você!", ephemeral=True)

class PainelVerify(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(VerifySelect(cog, cog.roles_verify, "verify", "Escolha uma opção de verificação..."))

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"  # Nome do banco
        self.collection_name = "verify_config"
        self.client = None
        self.collection = None
        self.connect_mongo()
        self.load_config()  # Carrega configurações do MongoDB
        # Adiciona views persistentes para sobreviver a reinicializações
        self.bot.add_view(PainelVerify(self))

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.collection = self.client[self.db_name][self.collection_name]
            # Testa conexão
            self.client.admin.command('ping')
            print("Conectado ao MongoDB com sucesso.")
        except ConnectionFailure:
            print("Erro ao conectar ao MongoDB. Usando valores padrão.")
            self.client = None
            self.collection = None

    def load_config(self):
        if self.collection is not None:
            doc = self.collection.find_one({"_id": "config"})
            if doc:
                self.embed_title = doc.get("embed_title", "Painel de Verificação")
                self.embed_description = doc.get("embed_description", "Escolha uma opção de verificação abaixo:")
                self.embed_color = doc.get("embed_color", 0x000000)
                self.embed_footer = doc.get("embed_footer", "")
                self.embed_thumbnail = doc.get("embed_thumbnail", None)
                self.embed_image = doc.get("embed_image", None)
            else:
                self.set_defaults()
        else:
            self.set_defaults()

    def set_defaults(self):
        self.embed_title = "Painel de Verificação"
        self.embed_description = "Escolha uma opção de verificação abaixo:"
        self.embed_color = 0x000000
        self.embed_footer = ""
        self.embed_thumbnail = None
        self.embed_image = None

    def save_config(self):
        if self.collection is not None:
            data = {
                "_id": "config",
                "embed_title": self.embed_title,
                "embed_description": self.embed_description,
                "embed_color": self.embed_color,
                "embed_footer": self.embed_footer,
                "embed_thumbnail": self.embed_thumbnail,
                "embed_image": self.embed_image
            }
            self.collection.replace_one({"_id": "config"}, data, upsert=True)

    # Dicionários de roles: nome -> cor hex (para criar roles automaticamente)
    roles_verify = {
        "Verificado": 0x00FF00  # Verde para verificado
    }

    # Modais para edição
    class EditModal(Modal):
        def __init__(self, cog, field, title, label, placeholder, interaction, current_value=""):
            super().__init__(title=title)
            self.cog = cog
            self.field = field
            self.interaction = interaction
            # Para descrição, usa paragraph para várias linhas
            if field == "description":
                self.input = TextInput(label=label, placeholder=placeholder, style=discord.TextStyle.paragraph, required=True, default=current_value)
            else:
                self.input = TextInput(label=label, placeholder=placeholder, style=discord.TextStyle.short, required=True, default=current_value)
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            value = self.input.value
            if self.field == 'color':
                try:
                    setattr(self.cog, f"embed_{self.field}", int(value, 16))
                except ValueError:
                    await interaction.response.send_message("Cor inválida. Use formato hex (ex: 000000).", ephemeral=True)
                    return
            else:
                setattr(self.cog, f"embed_{self.field}", value)
            
            self.cog.save_config()  # Salva configurações no MongoDB após alteração
            
            # Tenta atualizar o embed preview na resposta original ephemeral
            try:
                embed = self.cog.create_preview_embed()
                await self.interaction.edit_original_response(embed=embed, view=self.cog.ConfigView(self.cog, self.interaction))
                await interaction.response.send_message("Configuração atualizada!", ephemeral=True)
            except (discord.errors.InteractionResponded, discord.errors.NotFound, AttributeError):
                await interaction.response.send_message("A interação expirou (possivelmente após reinicialização do bot). Reabra o painel com /config_verify.", ephemeral=True)

    # View para configuração com botões
    class ConfigView(View):
        def __init__(self, cog, interaction):
            super().__init__(timeout=None)
            self.cog = cog
            self.interaction = interaction

        @discord.ui.button(label="Editar Título", style=discord.ButtonStyle.primary)
        async def edit_title(self, interaction: discord.Interaction, button: Button):
            modal = self.cog.EditModal(self.cog, "title", "Editar Título", "Novo Título", "Digite o título...", self.interaction, current_value=self.cog.embed_title)
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Descrição", style=discord.ButtonStyle.primary)
        async def edit_description(self, interaction: discord.Interaction, button: Button):
            modal = self.cog.EditModal(self.cog, "description", "Editar Descrição", "Nova Descrição", "Digite a descrição (use Enter para quebras de linha)...", self.interaction, current_value=self.cog.embed_description)
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Cor", style=discord.ButtonStyle.primary)
        async def edit_color(self, interaction: discord.Interaction, button: Button):
            current_color = f"{self.cog.embed_color:06X}"
            modal = self.cog.EditModal(self.cog, "color", "Editar Cor", "Nova Cor (hex)", "Ex: 000000", self.interaction, current_value=current_color)
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Footer", style=discord.ButtonStyle.primary)
        async def edit_footer(self, interaction: discord.Interaction, button: Button):
            modal = self.cog.EditModal(self.cog, "footer", "Editar Footer", "Novo Footer", "Digite o footer...", self.interaction, current_value=self.cog.embed_footer)
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Thumbnail", style=discord.ButtonStyle.primary)
        async def edit_thumbnail(self, interaction: discord.Interaction, button: Button):
            current_thumb = self.cog.embed_thumbnail or ""
            modal = self.cog.EditModal(self.cog, "thumbnail", "Editar Thumbnail", "Nova URL", "Digite a URL da imagem...", self.interaction, current_value=current_thumb)
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Imagem", style=discord.ButtonStyle.primary)
        async def edit_image(self, interaction: discord.Interaction, button: Button):
            current_image = self.cog.embed_image or ""
            modal = self.cog.EditModal(self.cog, "image", "Editar Imagem", "Nova URL", "Digite a URL da imagem...", self.interaction, current_value=current_image)
            await interaction.response.send_modal(modal)

    def create_preview_embed(self):
        embed = discord.Embed(title=self.embed_title, description=self.embed_description, color=self.embed_color)
        if self.embed_footer:
            embed.set_footer(text=self.embed_footer)
        if self.embed_thumbnail:
            embed.set_thumbnail(url=self.embed_thumbnail)
        if self.embed_image:
            embed.set_image(url=self.embed_image)
        return embed

    # Slash command para configurar a verificação (apenas admins, ephemeral)
    @app_commands.command(name="config_verify", description="Abre o painel de configuração da verificação com preview (ephemeral)")
    async def config_verify(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Você precisa ser administrador para usar este comando.", ephemeral=True)
            return
        
        embed = self.create_preview_embed()
        view = self.ConfigView(self, interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # Slash command para abrir o painel de verificação (persistente, não ephemeral)
    @app_commands.command(name="painel_verify", description="Abre o painel de seleção de verificação no canal atual")
    async def painel_verify(self, interaction: discord.Interaction):
        embed = self.create_preview_embed()
        view = PainelVerify(self)
        await interaction.channel.send(embed=embed, view=view)  # Envia no canal, persistente
        await interaction.response.send_message("Painel de verificação enviado no canal!", ephemeral=True)  # Confirmação privada

async def setup(bot):
    await bot.add_cog(Verify(bot))