import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


# Classes auxiliares movidas para fora da cog para persistência
class CorSelect(Select):
    def __init__(self, cog, cores_dict, placeholder="Escolha uma cor...", custom_id=None):
        self.cog = cog
        options = [discord.SelectOption(label=nome, value=nome) for nome in cores_dict.keys()]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        # Garante que a configuração existe
        if guild_id not in self.cog.config:
            self.cog.config[guild_id] = self.cog.load_config(guild_id)
        
        tipo_cores = self.cog.config[guild_id]["tipo_cores"]
        cores = self.cog.get_cores_ativas(tipo_cores)
        cor_hex = cores[self.values[0]]
        
        # Verifica e remove roles de cores antigas da paleta ativa
        user = interaction.user
        guild = interaction.guild
        
        # Remove todas as roles de cor existentes do usuário
        roles_removidos = 0
        cores_ativas = self.cog.get_cores_ativas(tipo_cores)
        
        for role in user.roles:
            if role.name in cores_ativas.keys():
                try:
                    await user.remove_roles(role)
                    roles_removidos += 1
                except discord.Forbidden:
                    print(f"Não foi possível remover a role {role.name}")
                except discord.HTTPException as e:
                    print(f"Erro ao remover role {role.name}: {e}")
        
        # Tenta encontrar a role da nova cor
        role = discord.utils.get(guild.roles, name=self.values[0])
        
        # Se a role não existir, cria ela
        if not role:
            try:
                role = await guild.create_role(
                    name=self.values[0],
                    color=discord.Color(cor_hex),
                    reason=f"Role de cor criada para {user.name}"
                )
                print(f"Role '{self.values[0]}' criada com sucesso")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Não tenho permissão para criar roles. Verifique a hierarquia de cargos.",
                    ephemeral=True
                )
                return
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    f"Erro ao criar role: {e}",
                    ephemeral=True
                )
                return
        
        # Atribui a nova cor ao usuário
        try:
            await user.add_roles(role)
            
            if roles_removidos > 0:
                await interaction.response.send_message(
                    f"Cor '{self.values[0]}' atribuída a você! ({roles_removidos} cor(es) antiga(s) removida(s))",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Cor '{self.values[0]}' atribuída a você!",
                    ephemeral=True
                )
                    
        except discord.Forbidden:
            await interaction.response.send_message(
                "Não tenho permissão para atribuir cargos. Verifique a hierarquia de cargos.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Erro ao atribuir cor: {e}",
                ephemeral=True
            )


class PainelCores(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        
        self.add_item(CorSelect(
            cog, 
            cog.cores_pastel, 
            "Escolha uma cor pastel...", 
            custom_id="color:pastel"
        ))
        self.add_item(CorSelect(
            cog, 
            cog.cores_gothic, 
            "Escolha uma cor gothic...", 
            custom_id="color:gothic"
        ))


class Color(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.collection_name = "color_config"
        self.client = None
        self.collection = None
        self.config = {}  # Armazena configurações por servidor
        self.connect_mongo()
        self.load_all_configs()  # Carrega todas as configurações do MongoDB
        self.bot.add_view(PainelCores(self))

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.collection = self.client[self.db_name][self.collection_name]
            print("Conectado ao MongoDB com sucesso.")
        except ConnectionFailure as e:
            print(f"Erro ao conectar ao MongoDB: {e}. Usando valores padrão.")
            self.client = None
            self.collection = None

    def load_all_configs(self):
        """Carrega todas as configurações do MongoDB para memória"""
        if self.collection is not None:
            try:
                # Busca todos os documentos de configuração
                cursor = self.collection.find({})
                for doc in cursor:
                    guild_id = doc["_id"].replace("guild_", "")
                    self.config[guild_id] = {
                        "tipo_cores": doc.get("tipo_cores", 'all'),
                        "embed_title": doc.get("embed_title", "🎨 Painel de Cores"),
                        "embed_description": doc.get("embed_description", "Escolha uma cor abaixo para mudar sua cor de nome:"),
                        "embed_color": doc.get("embed_color", 0x2F3136),
                        "embed_footer": doc.get("embed_footer", "Clique em uma opção para selecionar"),
                        "embed_thumbnail": doc.get("embed_thumbnail", None),
                        "embed_image": doc.get("embed_image", None)
                    }
                print(f"Carregadas {len(self.config)} configurações de servidores do MongoDB.")
            except Exception as e:
                print(f"Erro ao carregar configurações: {e}")

    def get_guild_id(self, guild_id):
        return f"guild_{guild_id}"

    def load_config(self, guild_id):
        """Carrega configuração de um servidor específico"""
        if self.collection is not None:
            try:
                doc = self.collection.find_one({"_id": self.get_guild_id(guild_id)})
                if doc:
                    return {
                        "tipo_cores": doc.get("tipo_cores", 'all'),
                        "embed_title": doc.get("embed_title", "🎨 Painel de Cores"),
                        "embed_description": doc.get("embed_description", "Escolha uma cor abaixo para mudar sua cor de nome:"),
                        "embed_color": doc.get("embed_color", 0x2F3136),
                        "embed_footer": doc.get("embed_footer", "Clique em uma opção para selecionar"),
                        "embed_thumbnail": doc.get("embed_thumbnail", None),
                        "embed_image": doc.get("embed_image", None)
                    }
            except Exception as e:
                print(f"Erro ao carregar configuração: {e}")
        
        return {
            "tipo_cores": 'all',
            "embed_title": "🎨 Painel de Cores",
            "embed_description": "Escolha uma cor abaixo para mudar sua cor de nome:",
            "embed_color": 0x2F3136,
            "embed_footer": "Clique em uma opção para selecionar",
            "embed_thumbnail": None,
            "embed_image": None
        }

    def save_config(self, guild_id, config):
        """Salva configuração de um servidor específico"""
        if self.collection is not None:
            try:
                data = {
                    "_id": self.get_guild_id(guild_id),
                    "tipo_cores": config["tipo_cores"],
                    "embed_title": config["embed_title"],
                    "embed_description": config["embed_description"],
                    "embed_color": config["embed_color"],
                    "embed_footer": config["embed_footer"],
                    "embed_thumbnail": config["embed_thumbnail"],
                    "embed_image": config["embed_image"]
                }
                self.collection.replace_one({"_id": self.get_guild_id(guild_id)}, data, upsert=True)
                print(f"Configuração salva para o servidor {guild_id}")
            except Exception as e:
                print(f"Erro ao salvar configuração: {e}")

    # Dicionários de cores
    cores_pastel = {
        "Rosa Pastel": 0xFFB6C1,
        "Azul Pastel": 0x87CEEB,
        "Verde Pastel": 0x98FB98,
        "Amarelo Pastel": 0xFFFACD,
        "Roxo Pastel": 0xDDA0DD,
        "Laranja Pastel": 0xFFDAB9,
        "Ciano Pastel": 0xE0FFFF,
        "Magenta Pastel": 0xFF69B4,
        "Cinza Pastel": 0xD3D3D3,
        "Branco": 0xFFFFFF,
        "Lavanda Pastel": 0xE6E6FA,
        "Menta Pastel": 0xF5FFFA,
        "Pêssego Pastel": 0xFFDAB9,
        "Lilás Pastel": 0xC8A2C8,
        "Aqua Pastel": 0xB0E0E6,
        "Champanhe Pastel": 0xF7E7CE,
        "Coral Pastel": 0xFAD5A5,
        "Melão Pastel": 0xFDBCB4,
        "Azul Céu Pastel": 0x87CEFA,
        "Verde Lima Pastel": 0xCCFFCC
    }

    cores_gothic = {
        "Preto Gothic": 0x000000,
        "Roxo Escuro": 0x4B0082,
        "Vermelho Sangue": 0x8B0000,
        "Cinza Escuro": 0x2F4F4F,
        "Azul Noite": 0x191970,
        "Verde Floresta": 0x006400,
        "Dourado Escuro": 0xB8860B,
        "Prata": 0xC0C0C0,
        "Marrom Antigo": 0x8B4513,
        "Violeta": 0x9400D3,
        "Preto Ébano": 0x1A1A1A,
        "Roxo Sombrio": 0x2E003E,
        "Vermelho Escarlate": 0x660000,
        "Cinza Sepulcral": 0x1C1C1C,
        "Azul Abismo": 0x000080,
        "Verde Sombra": 0x004400,
        "Dourado Antigo": 0x8B7355,
        "Prata Lunar": 0xA9A9A9,
        "Marrom Terreno": 0x5C4033,
        "Violeta Noturno": 0x4B0082,
        "Preto Profundo": 0x0A0A0A,
        "Roxo Enigmático": 0x301934,
        "Vermelho Carmesim": 0x8B0000,
        "Cinza Espectral": 0x696969,
        "Azul Profundo": 0x00008B
    }

    def get_cores_ativas(self, tipo_cores):
        if tipo_cores == 'pastel':
            return self.cores_pastel
        elif tipo_cores == 'gothic':
            return self.cores_gothic
        else:
            return {**self.cores_pastel, **self.cores_gothic}

    class EditModal(Modal):
        def __init__(self, cog, field, title, label, placeholder, interaction, current_value="", guild_id=None):
            super().__init__(title=title)
            self.cog = cog
            self.field = field
            self.interaction = interaction
            self.guild_id = guild_id
            self.input = TextInput(
                label=label, 
                placeholder=placeholder, 
                style=discord.TextStyle.paragraph, 
                required=True, 
                default=current_value
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            value = self.input.value
            
            if self.field == 'color':
                try:
                    value = value.replace('#', '')
                    self.cog.config[self.guild_id][f"embed_{self.field}"] = int(value, 16)
                except ValueError:
                    await interaction.response.send_message(
                        "Cor inválida. Use formato hex (ex: 000000 ou #000000).",
                        ephemeral=True
                    )
                    return
            elif self.field == 'tipo_cores':
                if value.lower() not in ['pastel', 'gothic', 'all']:
                    await interaction.response.send_message(
                        "Tipo inválido. Use: pastel, gothic ou all",
                        ephemeral=True
                    )
                    return
                self.cog.config[self.guild_id][f"embed_{self.field}"] = value.lower()
            else:
                self.cog.config[self.guild_id][f"embed_{self.field}"] = value
            
            self.cog.save_config(self.guild_id, self.cog.config[self.guild_id])
            
            try:
                embed = self.cog.create_preview_embed(self.guild_id)
                await self.interaction.edit_original_response(embed=embed, view=self.cog.ConfigView(self.cog, self.interaction, self.guild_id))
                await interaction.response.send_message("Configuração atualizada!", ephemeral=True)
            except (discord.errors.InteractionResponded, discord.errors.NotFound, AttributeError):
                await interaction.response.send_message(
                    "A interação expirou. Reabra o painel com /config_cores.",
                    ephemeral=True
                )

    class ConfigView(View):
        def __init__(self, cog, interaction, guild_id):
            super().__init__(timeout=None)
            self.cog = cog
            self.interaction = interaction
            self.guild_id = guild_id

        @discord.ui.button(label="Editar Título", style=discord.ButtonStyle.primary)
        async def edit_title(self, interaction: discord.Interaction, button):
            modal = self.cog.EditModal(
                self.cog, "title", "Editar Título", "Novo Título",
                "Digite o título do embed...", self.interaction,
                current_value=self.cog.config[self.guild_id]["embed_title"],
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Descrição", style=discord.ButtonStyle.primary)
        async def edit_description(self, interaction: discord.Interaction, button):
            modal = self.cog.EditModal(
                self.cog, "description", "Editar Descrição", "Nova Descrição",
                "Digite a descrição do embed...", self.interaction,
                current_value=self.cog.config[self.guild_id]["embed_description"],
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Cor", style=discord.ButtonStyle.primary)
        async def edit_color(self, interaction: discord.Interaction, button):
            current_color = f"{self.cog.config[self.guild_id]['embed_color']:06X}"
            modal = self.cog.EditModal(
                self.cog, "color", "Editar Cor do Embed", "Nova Cor (hex)",
                "Ex: 000000 ou #2F3136", self.interaction,
                current_value=current_color,
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Footer", style=discord.ButtonStyle.secondary)
        async def edit_footer(self, interaction: discord.Interaction, button):
            modal = self.cog.EditModal(
                self.cog, "footer", "Editar Footer", "Novo Footer",
                "Digite o texto do footer...", self.interaction,
                current_value=self.cog.config[self.guild_id]["embed_footer"],
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Thumbnail", style=discord.ButtonStyle.secondary, emoji="🖼️")
        async def edit_thumbnail(self, interaction: discord.Interaction, button):
            current_thumb = self.cog.config[self.guild_id]["embed_thumbnail"] or ""
            modal = self.cog.EditModal(
                self.cog, "thumbnail", "Editar Thumbnail", "URL do Thumbnail",
                "Cole a URL de uma imagem...", self.interaction,
                current_value=current_thumb,
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Editar Imagem", style=discord.ButtonStyle.secondary, emoji="🖼️")
        async def edit_image(self, interaction: discord.Interaction, button):
            current_image = self.cog.config[self.guild_id]["embed_image"] or ""
            modal = self.cog.EditModal(
                self.cog, "image", "Editar Imagem", "URL da Imagem",
                "Cole a URL de uma imagem...", self.interaction,
                current_value=current_image,
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Remover Thumbnail", style=discord.ButtonStyle.danger, emoji="❌")
        async def remove_thumbnail(self, interaction: discord.Interaction, button):
            self.cog.config[self.guild_id]["embed_thumbnail"] = None
            self.cog.save_config(self.guild_id, self.cog.config[self.guild_id])
            
            embed = self.cog.create_preview_embed(self.guild_id)
            await interaction.response.edit_message(embed=embed, view=self.cog.ConfigView(self.cog, self.interaction, self.guild_id))
            await interaction.followup.send("Thumbnail removida!", ephemeral=True)

        @discord.ui.button(label="Remover Imagem", style=discord.ButtonStyle.danger, emoji="❌")
        async def remove_image(self, interaction: discord.Interaction, button):
            self.cog.config[self.guild_id]["embed_image"] = None
            self.cog.save_config(self.guild_id, self.cog.config[self.guild_id])
            
            embed = self.cog.create_preview_embed(self.guild_id)
            await interaction.response.edit_message(embed=embed, view=self.cog.ConfigView(self.cog, self.interaction, self.guild_id))
            await interaction.followup.send("Imagem removida!", ephemeral=True)

        @discord.ui.button(label="Mudar Tipo de Cores", style=discord.ButtonStyle.secondary)
        async def change_type(self, interaction: discord.Interaction, button):
            modal = self.cog.EditModal(
                self.cog, "tipo_cores", "Mudar Tipo de Cores", "Novo Tipo",
                "pastel, gothic ou all", self.interaction,
                current_value=self.cog.config[self.guild_id]["tipo_cores"],
                guild_id=self.guild_id
            )
            await interaction.response.send_modal(modal)

        @discord.ui.button(label="Resetar Configurações", style=discord.ButtonStyle.danger)
        async def reset_config(self, interaction: discord.Interaction, button):
            self.cog.config[self.guild_id] = {
                "tipo_cores": 'all',
                "embed_title": "🎨 Painel de Cores",
                "embed_description": "Escolha uma cor abaixo para mudar sua cor de nome:",
                "embed_color": 0x2F3136,
                "embed_footer": "Clique em uma opção para selecionar",
                "embed_thumbnail": None,
                "embed_image": None
            }
            self.cog.save_config(self.guild_id, self.cog.config[self.guild_id])
            
            embed = self.cog.create_preview_embed(self.guild_id)
            await interaction.response.edit_message(embed=embed, view=self.cog.ConfigView(self.cog, self.interaction, self.guild_id))
            await interaction.followup.send("Configurações resetadas para o padrão!", ephemeral=True)

    def create_preview_embed(self, guild_id):
        config = self.config.get(guild_id, {})
        embed = discord.Embed(
            title=config.get("embed_title", "🎨 Painel de Cores"),
            description=config.get("embed_description", "Escolha uma cor abaixo para mudar sua cor de nome:"),
            color=config.get("embed_color", 0x2F3136)
        )
        if config.get("embed_footer"):
            embed.set_footer(text=config.get("embed_footer"))
        if config.get("embed_thumbnail"):
            embed.set_thumbnail(url=config.get("embed_thumbnail"))
        if config.get("embed_image"):
            embed.set_image(url=config.get("embed_image"))
        return embed

    @app_commands.command(name="config_cores", description="Abre o painel de configuração das cores (apenas administradores)")
    async def config_cores(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Você precisa ser administrador para usar este comando.",
                ephemeral=True
            )
            return
        
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = self.load_config(guild_id)
        
        embed = self.create_preview_embed(guild_id)
        view = self.ConfigView(self, interaction, guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="painel_cores", description="Envia o painel de seleção de cores neste canal")
    async def painel_cores(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = self.load_config(guild_id)
        
        tipo_cores = self.config[guild_id]["tipo_cores"]
        cores = self.get_cores_ativas(tipo_cores)
        
        if not cores:
            await interaction.response.send_message(
                "Nenhuma cor disponível. Configure com /config_cores.",
                ephemeral=True
            )
            return
        
        guild = interaction.guild
        bot_member = guild.me
        
        if not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "O bot não tem permissão para gerenciar cargos.",
                ephemeral=True
            )
            return
        
        if bot_member.top_role.position <= 0:
            await interaction.response.send_message(
                "O cargo do bot está em uma posição muito baixa.",
                ephemeral=True
            )
            return
        
        embed = self.create_preview_embed(guild_id)
        view = PainelCores(self)
        
        await interaction.channel.send(embed=embed, view=view)
        
        await interaction.response.send_message(
            "Painel de cores enviado no canal com sucesso!",
            ephemeral=True
        )

    @app_commands.command(name="resetar_cor", description="Remove sua cor atual")
    async def resetar_cor(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        
        guild_id = str(guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = self.load_config(guild_id)
        
        tipo_cores = self.config[guild_id]["tipo_cores"]
        cores_ativas = self.get_cores_ativas(tipo_cores)
        
        roles_removidos = 0
        
        for role in user.roles:
            if role.name in cores_ativas.keys():
                try:
                    await user.remove_roles(role)
                    roles_removidos += 1
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "Não tenho permissão para remover cargos.",
                        ephemeral=True
                    )
                    return
                except discord.HTTPException as e:
                    await interaction.response.send_message(
                        f"Erro ao remover cargo: {e}",
                        ephemeral=True
                    )
                    return
        
        if roles_removidos > 0:
            await interaction.response.send_message(
                f"Sua cor foi removida! ({roles_removidos} cor(es) removida(s))",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Você não tinha nenhuma cor atribuída.",
                ephemeral=True
            )

    @app_commands.command(name="listar_cores", description="Lista todas as cores disponíveis")
    async def listar_cores(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = self.load_config(guild_id)
        
        pastel_count = len(self.cores_pastel)
        gothic_count = len(self.cores_gothic)
        
        embed = discord.Embed(
            title="🎨 Cores Disponíveis",
            description=f"Total: {len(self.cores_pastel) + len(self.cores_gothic)} cores",
            color=self.config[guild_id]["embed_color"]
        )
        
        pastel_list = "\n".join([f"• {nome}" for nome in self.cores_pastel.keys()])
        embed.add_field(
            name=f"🌸 Pastel ({pastel_count})",
            value=pastel_list,
            inline=True
        )
        
        gothic_list = "\n".join([f"• {nome}" for nome in self.cores_gothic.keys()])
        embed.add_field(
            name=f"🖤 Gothic ({gothic_count})",
            value=gothic_list,
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Color(bot))