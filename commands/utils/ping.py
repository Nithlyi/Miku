import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Modal para adicionar novo cargo de ping pelo ID
class AddPingModal(Modal, title="Adicionar Cargo de Ping por ID"):
    def __init__(self, view: 'PingConfigView'):
        super().__init__()
        self.view = view

    nome_exibicao = TextInput(
        label="Nome de exibição",
        placeholder="Como o cargo vai aparecer no painel",
        required=True,
        max_length=50
    )

    cargo_id = TextInput(
        label="ID do Cargo",
        placeholder="Cole o ID do cargo aqui",
        required=True,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        nome_exibicao = self.nome_exibicao.value.strip()
        
        # Valida o ID do cargo
        try:
            cargo_id = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Digite um número válido.", ephemeral=True)
            return

        # Verifica se o cargo existe no servidor
        role = interaction.guild.get_role(cargo_id)
        if not role:
            await interaction.response.send_message("❌ Cargo não encontrado! Verifique o ID.", ephemeral=True)
            return

        # Salva no banco de dados
        await self.view.cog.add_ping_role(interaction, nome_exibicao, cargo_id, role.name)


# Select para remover cargos de ping
class RemovePingSelect(Select):
    def __init__(self, cog, roles_dict):
        self.cog = cog
        options = []
        for nome_exibicao, role_data in roles_dict.items():
            role_name = role_data.get('role_name', 'Cargo desconhecido')
            
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="Nenhum cargo configurado",
                value="none",
                default=True
            ))
        
        super().__init__(
            placeholder="Selecione um cargo para remover...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="ping:remove_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos para remover.", ephemeral=True)
            return
        
        nome_exibicao = self.values[0]
        await self.cog.remove_ping_role(interaction, nome_exibicao)


# View de configuração dos pings (para /config_ping)
class PingConfigView(View):
    def __init__(self, cog, interaction):
        super().__init__(timeout=300)
        self.cog = cog
        self.original_interaction = interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    @discord.ui.button(label="Adicionar Cargo por ID", style=discord.ButtonStyle.success, emoji="➕", row=0, custom_id="ping:add_btn")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        modal = AddPingModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remover Cargo", style=discord.ButtonStyle.danger, emoji="➖", row=0, custom_id="ping:remove_btn")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        guild_id = str(interaction.guild_id)
        roles_dict = self.cog.roles_pings.get(guild_id, {})
        
        if not roles_dict:
            await interaction.response.send_message("Não há cargos configurados para remover.", ephemeral=True)
            return
        
        view = View(timeout=60)
        view.add_item(RemovePingSelect(self.cog, roles_dict))
        await interaction.response.send_message("Selecione o cargo para remover:", view=view, ephemeral=True)

    @discord.ui.button(label="Atualizar Preview", style=discord.ButtonStyle.secondary, emoji="🔄", row=0, custom_id="ping:refresh_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self.update_preview()

    async def update_preview(self):
        embed = self.cog.create_preview_embed(str(self.original_interaction.guild_id))
        try:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        except:
            pass


# Select para usuários escolherem seus pings (PERSISTENTE)
class UserPingSelect(Select):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        options = []
        
        # Pega os cargos configurados para este servidor
        guild_roles = cog.roles_pings.get(str(guild_id), {})
        
        for nome_exibicao, role_data in guild_roles.items():
            role_name = role_data.get('role_name', 'Cargo')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        # Se não houver opções, adiciona uma opção padrão
        if not options:
            options.append(discord.SelectOption(
                label="Nenhum ping disponível",
                value="none",
                default=True
            ))
        
        super().__init__(
            placeholder="Escolha um ping...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"ping:user_select:{guild_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há pings configurados neste servidor.", ephemeral=True)
            return
        
        nome_exibicao = self.values[0]
        
        # Pega os cargos do servidor
        guild_roles = self.cog.roles_pings.get(str(self.guild_id), {})
        role_data = guild_roles.get(nome_exibicao)
        
        if not role_data:
            await interaction.response.send_message("❌ Ping não encontrado na configuração!", ephemeral=True)
            return
        
        role_id = role_data['role_id']
        role = interaction.guild.get_role(role_id)
        
        # Se o cargo não existe mais no servidor
        if not role:
            await interaction.response.send_message("❌ O cargo associado a este ping não existe mais no servidor!", ephemeral=True)
            return
        
        # Verifica se o usuário já tem o cargo
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Ping '{nome_exibicao}' removido!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Ping '{nome_exibicao}' ativado!", ephemeral=True)


# View principal do painel de pings (PERSISTENTE - para /painel_ping)
class PainelPingView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.add_item(UserPingSelect(cog, guild_id))


# View para editar configurações do embed (para /editar_ping)
class EditConfigView(View):
    def __init__(self, cog, interaction, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.interaction = interaction
        self.guild_id = guild_id

    @discord.ui.button(label="Título", style=discord.ButtonStyle.primary, custom_id="edit_title_btn")
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditConfigModal(
            self.cog, "title", "Editar Título", "Novo título:", 
            interaction, self.cog.embed_configs[self.guild_id]["embed_title"], self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Descrição", style=discord.ButtonStyle.primary, custom_id="edit_desc_btn")
    async def edit_description(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditConfigModal(
            self.cog, "description", "Editar Descrição", "Nova descrição:", 
            interaction, self.cog.embed_configs[self.guild_id]["embed_description"], self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cor", style=discord.ButtonStyle.primary, custom_id="edit_color_btn")
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        current = f"{self.cog.embed_configs[self.guild_id]['embed_color']:06X}"
        modal = self.cog.EditConfigModal(
            self.cog, "color", "Editar Cor", "Nova cor (hex):", 
            interaction, current, self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.primary, custom_id="edit_footer_btn")
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditConfigModal(
            self.cog, "footer", "Editar Footer", "Novo footer:", 
            interaction, self.cog.embed_configs[self.guild_id]["embed_footer"], self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Thumbnail", style=discord.ButtonStyle.primary, custom_id="edit_thumb_btn")
    async def edit_thumbnail(self, interaction: discord.Interaction, button: Button):
        current = self.cog.embed_configs[self.guild_id]["embed_thumbnail"] or ""
        modal = self.cog.EditConfigModal(
            self.cog, "thumbnail", "Editar Thumbnail", "URL da thumbnail:", 
            interaction, current, self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Imagem", style=discord.ButtonStyle.primary, custom_id="edit_img_btn")
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        current = self.cog.embed_configs[self.guild_id]["embed_image"] or ""
        modal = self.cog.EditConfigModal(
            self.cog, "image", "Editar Imagem", "URL da imagem:", 
            interaction, current, self.guild_id
        )
        await interaction.response.send_modal(modal)


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.collection_name = "ping_config"
        self.roles_collection_name = "ping_roles"
        self.client = None
        self.config_collection = None
        self.roles_collection = None
        self.roles_pings = {}  # Dicionário: guild_id -> {nome_exibicao: {'role_id': id, 'role_name': nome}}
        self.embed_configs = {}  # Configurações por servidor: guild_id -> {title, description, color, footer, thumbnail, image}
        
        self.connect_mongo()
        self.load_all_configs()
        self.load_all_roles()
        
        # Registra views persistentes para cada servidor
        for guild_id in self.roles_pings:
            self.bot.add_view(PainelPingView(self, int(guild_id)))

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.config_collection = self.client[self.db_name][self.collection_name]
            self.roles_collection = self.client[self.db_name][self.roles_collection_name]
            self.client.admin.command('ping')
            print("✅ Conectado ao MongoDB com sucesso.")
        except ConnectionFailure:
            print("❌ Erro ao conectar ao MongoDB. Usando valores padrão.")
            self.client = None
            self.config_collection = None
            self.roles_collection = None

    def load_all_configs(self):
        """Carrega configurações do embed de todos os servidores do MongoDB"""
        self.embed_configs = {}
        if self.config_collection is not None:
            cursor = self.config_collection.find({})
            for doc in cursor:
                guild_id = doc.get("guild_id")
                if guild_id:
                    self.embed_configs[guild_id] = {
                        "embed_title": doc.get("embed_title", "Painel de Pings"),
                        "embed_description": doc.get("embed_description", "Selecione os pings que deseja receber:"),
                        "embed_color": doc.get("embed_color", 0x2C2F33),
                        "embed_footer": doc.get("embed_footer", "Clique nos botões abaixo para ativar/desativar"),
                        "embed_thumbnail": doc.get("embed_thumbnail", None),
                        "embed_image": doc.get("embed_image", None)
                    }
            print(f"📦 Carregadas {len(self.embed_configs)} configurações de servidores")

    def get_guild_config(self, guild_id):
        """Retorna a configuração de um servidor específico ou cria uma padrão"""
        if guild_id not in self.embed_configs:
            self.embed_configs[guild_id] = {
                "embed_title": "Painel de Pings",
                "embed_description": "Selecione os pings que deseja receber:",
                "embed_color": 0x2C2F33,
                "embed_footer": "Clique nos botões abaixo para ativar/desativar",
                "embed_thumbnail": None,
                "embed_image": None
            }
        return self.embed_configs[guild_id]

    def save_guild_config(self, guild_id):
        """Salva configurações de um servidor no MongoDB"""
        if self.config_collection is not None and guild_id in self.embed_configs:
            config = self.embed_configs[guild_id]
            data = {
                "guild_id": guild_id,
                "embed_title": config["embed_title"],
                "embed_description": config["embed_description"],
                "embed_color": config["embed_color"],
                "embed_footer": config["embed_footer"],
                "embed_thumbnail": config["embed_thumbnail"],
                "embed_image": config["embed_image"]
            }
            self.config_collection.replace_one({"guild_id": guild_id}, data, upsert=True)

    def load_all_roles(self):
        """Carrega os cargos de ping do MongoDB por servidor"""
        self.roles_pings = {}
        if self.roles_collection is not None:
            cursor = self.roles_collection.find({})
            for doc in cursor:
                guild_id = str(doc.get("guild_id"))
                nome_exibicao = doc.get("nome_exibicao")
                role_id = doc.get("role_id")
                role_name = doc.get("role_name", "Cargo desconhecido")
                
                if guild_id and nome_exibicao and role_id:
                    if guild_id not in self.roles_pings:
                        self.roles_pings[guild_id] = {}
                    
                    self.roles_pings[guild_id][nome_exibicao] = {
                        'role_id': role_id,
                        'role_name': role_name
                    }
            
            total = sum(len(roles) for roles in self.roles_pings.values())
            print(f"📦 Carregados {total} cargos de ping do banco em {len(self.roles_pings)} servidores")

    async def add_ping_role(self, interaction: discord.Interaction, nome_exibicao: str, role_id: int, role_name: str):
        """Adiciona um novo cargo de ping por ID"""
        guild_id = str(interaction.guild_id)
        
        # Inicializa o dicionário do servidor se não existir
        if guild_id not in self.roles_pings:
            self.roles_pings[guild_id] = {}
        
        # Verifica se já existe
        if nome_exibicao in self.roles_pings[guild_id]:
            await interaction.response.send_message(f"❌ O nome '{nome_exibicao}' já existe!", ephemeral=True)
            return
        
        # Salva no dicionário
        self.roles_pings[guild_id][nome_exibicao] = {
            'role_id': role_id,
            'role_name': role_name
        }
        
        # Salva no MongoDB
        if self.roles_collection is not None:
            self.roles_collection.update_one(
                {"guild_id": guild_id, "nome_exibicao": nome_exibicao},
                {"$set": {
                    "guild_id": guild_id,
                    "nome_exibicao": nome_exibicao,
                    "role_id": role_id,
                    "role_name": role_name
                }},
                upsert=True
            )
        
        # Atualiza o preview
        embed = self.create_preview_embed(guild_id)
        
        try:
            await interaction.response.edit_message(embed=embed, view=PingConfigView(self, interaction))
            await interaction.followup.send(f"✅ Ping '{nome_exibicao}' adicionado com sucesso! (Cargo: {role_name})", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ Ping '{nome_exibicao}' adicionado com sucesso! (Cargo: {role_name})", ephemeral=True)

    async def remove_ping_role(self, interaction: discord.Interaction, nome_exibicao: str):
        """Remove um cargo de ping"""
        guild_id = str(interaction.guild_id)
        
        if guild_id not in self.roles_pings or nome_exibicao not in self.roles_pings[guild_id]:
            await interaction.response.send_message(f"❌ Ping '{nome_exibicao}' não encontrado!", ephemeral=True)
            return
        
        role_data = self.roles_pings[guild_id][nome_exibicao]
        role_name = role_data.get('role_name', 'Cargo desconhecido')
        
        # Remove do dicionário
        del self.roles_pings[guild_id][nome_exibicao]
        
        # Remove do MongoDB
        if self.roles_collection is not None:
            self.roles_collection.delete_one({"guild_id": guild_id, "nome_exibicao": nome_exibicao})
        
        # Atualiza o preview
        embed = self.create_preview_embed(guild_id)
        
        try:
            await interaction.response.edit_message(embed=embed, view=PingConfigView(self, interaction))
            await interaction.followup.send(f"✅ Ping '{nome_exibicao}' removido! (Cargo: {role_name})", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ Ping '{nome_exibicao}' removido! (Cargo: {role_name})", ephemeral=True)

    def create_preview_embed(self, guild_id):
        """Cria embed de preview com a lista de cargos (sem IDs) para um servidor específico"""
        config = self.get_guild_config(guild_id)
        
        embed = discord.Embed(
            title=config["embed_title"],
            description=config["embed_description"],
            color=config["embed_color"]
        )
        
        # Adiciona a lista de cargos disponíveis para este servidor
        if guild_id in self.roles_pings and self.roles_pings[guild_id]:
            cargos_lista = []
            for nome_exibicao, role_data in self.roles_pings[guild_id].items():
                role_name = role_data.get('role_name', 'Cargo desconhecido')
                # Mostra apenas o nome de exibição e o nome do cargo, sem IDs
                cargos_lista.append(f"**{nome_exibicao}** → `@{role_name}`")
            
            embed.add_field(
                name="Pings Disponíveis",
                value="\n".join(cargos_lista),
                inline=False
            )
        else:
            embed.add_field(
                name="Pings Disponíveis",
                value="*Nenhum ping configurado neste servidor*",
                inline=False
            )
        
        if config["embed_footer"]:
            embed.set_footer(text=config["embed_footer"])
        if config["embed_thumbnail"]:
            embed.set_thumbnail(url=config["embed_thumbnail"])
        if config["embed_image"]:
            embed.set_image(url=config["embed_image"])
        
        return embed

    # Modal para editar configurações do embed
    class EditConfigModal(Modal):
        def __init__(self, cog, field, title, label, interaction, current_value="", guild_id=None):
            super().__init__(title=title)
            self.cog = cog
            self.field = field
            self.interaction = interaction
            self.guild_id = guild_id
            self.input = TextInput(
                label=label,
                default=current_value,
                required=True,
                style=discord.TextStyle.paragraph if field in ["description", "footer"] else discord.TextStyle.short
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            value = self.input.value
            
            if self.field == 'color':
                try:
                    value = int(value.replace('#', ''), 16)
                except ValueError:
                    await interaction.response.send_message("Cor inválida! Use formato hex (ex: 2C2F33).", ephemeral=True)
                    return
            
            # Atualiza a configuração do servidor específico
            config = self.cog.get_guild_config(self.guild_id)
            config[f"embed_{self.field}"] = value
            self.cog.save_guild_config(self.guild_id)
            
            # Atualiza o preview
            embed = self.cog.create_preview_embed(self.guild_id)
            view = EditConfigView(self.cog, interaction, self.guild_id)
            await interaction.response.edit_message(embed=embed, view=view)

    # Comando para configurar os pings (adicionar/remover cargos)
    @app_commands.command(name="config_ping", description="Configura os cargos de ping (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def config_ping(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        embed = self.create_preview_embed(guild_id)
        view = PingConfigView(self, interaction)
        await interaction.response.send_message("⚙️ **Configuração dos Pings**", embed=embed, view=view, ephemeral=True)

    # Comando para enviar o painel no canal (para usuários)
    @app_commands.command(name="painel_ping", description="Envia o painel de pings no canal atual")
    @app_commands.default_permissions(administrator=True)
    async def painel_ping(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        
        # Verifica se há pings configurados
        if guild_id not in self.roles_pings or not self.roles_pings[guild_id]:
            await interaction.response.send_message("❌ Não há pings configurados neste servidor! Use `/config_ping` para adicionar.", ephemeral=True)
            return
        
        # Verifica permissões
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Preciso da permissão `Gerenciar Cargos`!", ephemeral=True)
            return
        
        # Cria view persistente para este servidor
        view = PainelPingView(self, interaction.guild_id)
        
        embed = self.create_preview_embed(guild_id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Painel de pings enviado com sucesso!", ephemeral=True)

    # Comando para editar configurações visuais do embed
    @app_commands.command(name="editar_ping", description="Edita as configurações visuais do painel (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def editar_ping(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        view = EditConfigView(self, interaction, guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.response.send_message("🎨 **Editar Aparência do Painel**", embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Ping(bot))