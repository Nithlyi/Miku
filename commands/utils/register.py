import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


# MODAIS PARA ADICIONAR CARGOS POR CATEGORIA
class AddIdadeModal(Modal, title="Adicionar Opção de Idade"):
    def __init__(self, view: 'RegistroConfigView'):
        super().__init__()
        self.view = view

    nome_exibicao = TextInput(
        label="Nome de exibição",
        placeholder="Ex: -18, +18, 18-25...",
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
        
        try:
            cargo_id = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Digite um número válido.", ephemeral=True)
            return

        role = interaction.guild.get_role(cargo_id)
        if not role:
            await interaction.response.send_message("❌ Cargo não encontrado! Verifique o ID.", ephemeral=True)
            return

        await self.view.cog.add_registro_role(interaction, "idade", nome_exibicao, cargo_id, role.name)


class AddGeneroModal(Modal, title="Adicionar Opção de Gênero"):
    def __init__(self, view: 'RegistroConfigView'):
        super().__init__()
        self.view = view

    nome_exibicao = TextInput(
        label="Nome de exibição",
        placeholder="Ex: Homem, Mulher, Não binário...",
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
        
        try:
            cargo_id = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Digite um número válido.", ephemeral=True)
            return

        role = interaction.guild.get_role(cargo_id)
        if not role:
            await interaction.response.send_message("❌ Cargo não encontrado! Verifique o ID.", ephemeral=True)
            return

        await self.view.cog.add_registro_role(interaction, "genero", nome_exibicao, cargo_id, role.name)


class AddPronomeModal(Modal, title="Adicionar Opção de Pronome"):
    def __init__(self, view: 'RegistroConfigView'):
        super().__init__()
        self.view = view

    nome_exibicao = TextInput(
        label="Nome de exibição",
        placeholder="Ex: She/her, He/him, They/them...",
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
        
        try:
            cargo_id = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Digite um número válido.", ephemeral=True)
            return

        role = interaction.guild.get_role(cargo_id)
        if not role:
            await interaction.response.send_message("❌ Cargo não encontrado! Verifique o ID.", ephemeral=True)
            return

        await self.view.cog.add_registro_role(interaction, "pronome", nome_exibicao, cargo_id, role.name)


# SELECTS PARA REMOVER CARGOS POR CATEGORIA
class RemoveIdadeSelect(Select):
    def __init__(self, cog, roles_dict):
        self.cog = cog
        self.categoria = "idade"
        options = []
        for nome_exibicao, role_data in roles_dict.items():
            role_name = role_data.get('role_name', 'Cargo desconhecido')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        if not options:
            options.append(discord.SelectOption(label="Nenhuma opção configurada", value="none", default=True))
        
        super().__init__(
            placeholder="Selecione uma opção de idade para remover...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="register:remove_idade"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há opções para remover.", ephemeral=True)
            return
        await self.cog.remove_registro_role(interaction, self.categoria, self.values[0])


class RemoveGeneroSelect(Select):
    def __init__(self, cog, roles_dict):
        self.cog = cog
        self.categoria = "genero"
        options = []
        for nome_exibicao, role_data in roles_dict.items():
            role_name = role_data.get('role_name', 'Cargo desconhecido')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        if not options:
            options.append(discord.SelectOption(label="Nenhuma opção configurada", value="none", default=True))
        
        super().__init__(
            placeholder="Selecione uma opção de gênero para remover...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="register:remove_genero"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há opções para remover.", ephemeral=True)
            return
        await self.cog.remove_registro_role(interaction, self.categoria, self.values[0])


class RemovePronomeSelect(Select):
    def __init__(self, cog, roles_dict):
        self.cog = cog
        self.categoria = "pronome"
        options = []
        for nome_exibicao, role_data in roles_dict.items():
            role_name = role_data.get('role_name', 'Cargo desconhecido')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        if not options:
            options.append(discord.SelectOption(label="Nenhuma opção configurada", value="none", default=True))
        
        super().__init__(
            placeholder="Selecione uma opção de pronome para remover...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="register:remove_pronome"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há opções para remover.", ephemeral=True)
            return
        await self.cog.remove_registro_role(interaction, self.categoria, self.values[0])


# VIEW DE CONFIGURAÇÃO DO REGISTRO
class RegistroConfigView(View):
    def __init__(self, cog, interaction, guild_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.original_interaction = interaction
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    # IDADE
    @discord.ui.button(label="Adicionar Idade", style=discord.ButtonStyle.success, emoji="➕", row=0, custom_id="reg:add_idade")
    async def add_idade(self, interaction: discord.Interaction, button: Button):
        modal = AddIdadeModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remover Idade", style=discord.ButtonStyle.danger, emoji="➖", row=0, custom_id="reg:remove_idade")
    async def remove_idade(self, interaction: discord.Interaction, button: Button):
        roles_dict = self.cog.registro_roles.get(self.guild_id, {}).get("idade", {})
        if not roles_dict:
            await interaction.response.send_message("Não há opções de idade configuradas.", ephemeral=True)
            return
        
        view = View(timeout=60)
        view.add_item(RemoveIdadeSelect(self.cog, roles_dict))
        await interaction.response.send_message("Selecione a opção de idade para remover:", view=view, ephemeral=True)

    # GÊNERO
    @discord.ui.button(label="Adicionar Gênero", style=discord.ButtonStyle.success, emoji="➕", row=1, custom_id="reg:add_genero")
    async def add_genero(self, interaction: discord.Interaction, button: Button):
        modal = AddGeneroModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remover Gênero", style=discord.ButtonStyle.danger, emoji="➖", row=1, custom_id="reg:remove_genero")
    async def remove_genero(self, interaction: discord.Interaction, button: Button):
        roles_dict = self.cog.registro_roles.get(self.guild_id, {}).get("genero", {})
        if not roles_dict:
            await interaction.response.send_message("Não há opções de gênero configuradas.", ephemeral=True)
            return
        
        view = View(timeout=60)
        view.add_item(RemoveGeneroSelect(self.cog, roles_dict))
        await interaction.response.send_message("Selecione a opção de gênero para remover:", view=view, ephemeral=True)

    # PRONOME
    @discord.ui.button(label="Adicionar Pronome", style=discord.ButtonStyle.success, emoji="➕", row=2, custom_id="reg:add_pronome")
    async def add_pronome(self, interaction: discord.Interaction, button: Button):
        modal = AddPronomeModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remover Pronome", style=discord.ButtonStyle.danger, emoji="➖", row=2, custom_id="reg:remove_pronome")
    async def remove_pronome(self, interaction: discord.Interaction, button: Button):
        roles_dict = self.cog.registro_roles.get(self.guild_id, {}).get("pronome", {})
        if not roles_dict:
            await interaction.response.send_message("Não há opções de pronome configuradas.", ephemeral=True)
            return
        
        view = View(timeout=60)
        view.add_item(RemovePronomeSelect(self.cog, roles_dict))
        await interaction.response.send_message("Selecione a opção de pronome para remover:", view=view, ephemeral=True)

    @discord.ui.button(label="Atualizar Preview", style=discord.ButtonStyle.secondary, emoji="🔄", row=3, custom_id="reg:refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self.update_preview()

    async def update_preview(self):
        embed = self.cog.create_preview_embed(self.guild_id)
        try:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        except:
            pass


# SELECTS PARA USUÁRIOS (PERSISTENTES)
class UserIdadeSelect(Select):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        self.categoria = "idade"
        options = []
        
        guild_roles = cog.registro_roles.get(guild_id, {}).get("idade", {})
        for nome_exibicao, role_data in guild_roles.items():
            role_name = role_data.get('role_name', 'Cargo')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        super().__init__(
            placeholder="Escolha sua idade...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"register:user_idade:{guild_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.cog.handle_registro_selection(interaction, self.guild_id, self.categoria, self.values[0])


class UserGeneroSelect(Select):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        self.categoria = "genero"
        options = []
        
        guild_roles = cog.registro_roles.get(guild_id, {}).get("genero", {})
        for nome_exibicao, role_data in guild_roles.items():
            role_name = role_data.get('role_name', 'Cargo')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        super().__init__(
            placeholder="Escolha seu gênero...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"register:user_genero:{guild_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.cog.handle_registro_selection(interaction, self.guild_id, self.categoria, self.values[0])


class UserPronomeSelect(Select):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        self.categoria = "pronome"
        options = []
        
        guild_roles = cog.registro_roles.get(guild_id, {}).get("pronome", {})
        for nome_exibicao, role_data in guild_roles.items():
            role_name = role_data.get('role_name', 'Cargo')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))
        
        super().__init__(
            placeholder="Escolha seu pronome...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"register:user_pronome:{guild_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        await self.cog.handle_registro_selection(interaction, self.guild_id, self.categoria, self.values[0])


# VIEW PRINCIPAL DO PAINEL DE REGISTRO
class PainelRegistroView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        
        # Adiciona os três selects em linhas diferentes
        idade_select = UserIdadeSelect(cog, guild_id)
        idade_select.row = 0
        self.add_item(idade_select)
        
        genero_select = UserGeneroSelect(cog, guild_id)
        genero_select.row = 1
        self.add_item(genero_select)
        
        pronome_select = UserPronomeSelect(cog, guild_id)
        pronome_select.row = 2
        self.add_item(pronome_select)


# VIEW PARA EDITAR CONFIGURAÇÕES VISUAIS
class EditRegistroConfigView(View):
    def __init__(self, cog, interaction, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.interaction = interaction
        self.guild_id = guild_id

    @discord.ui.button(label="Título", style=discord.ButtonStyle.primary)
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditConfigModal(self.cog, "title", "Editar Título", "Novo título:", 
                                       interaction, self.cog.config[self.guild_id]["embed_title"], self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Descrição", style=discord.ButtonStyle.primary)
    async def edit_description(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditConfigModal(self.cog, "description", "Editar Descrição", "Nova descrição:", 
                                       interaction, self.cog.config[self.guild_id]["embed_description"], self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cor", style=discord.ButtonStyle.primary)
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        current = f"{self.cog.config[self.guild_id]['embed_color']:06X}"
        modal = self.cog.EditConfigModal(self.cog, "color", "Editar Cor", "Nova cor (hex):", 
                                       interaction, current, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.secondary)
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditConfigModal(self.cog, "footer", "Editar Footer", "Novo footer:", 
                                       interaction, self.cog.config[self.guild_id]["embed_footer"], self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Thumbnail", style=discord.ButtonStyle.secondary)
    async def edit_thumbnail(self, interaction: discord.Interaction, button: Button):
        current = self.cog.config[self.guild_id]["embed_thumbnail"] or ""
        modal = self.cog.EditConfigModal(self.cog, "thumbnail", "Editar Thumbnail", "URL da thumbnail:", 
                                       interaction, current, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Imagem", style=discord.ButtonStyle.secondary)
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        current = self.cog.config[self.guild_id]["embed_image"] or ""
        modal = self.cog.EditConfigModal(self.cog, "image", "Editar Imagem", "URL da imagem:", 
                                       interaction, current, self.guild_id)
        await interaction.response.send_modal(modal)


class Register(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.config_collection_name = "register_config"
        self.roles_collection_name = "register_roles"
        self.client = None
        self.config_collection = None
        self.roles_collection = None
        self.config = {}
        self.registro_roles = {}
        
        self.connect_mongo()
        self.load_all_configs()
        self.load_all_roles()
        
        for guild_id in self.registro_roles:
            self.bot.add_view(PainelRegistroView(self, guild_id))

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.config_collection = self.client[self.db_name][self.config_collection_name]
            self.roles_collection = self.client[self.db_name][self.roles_collection_name]
            print("✅ Conectado ao MongoDB com sucesso.")
        except ConnectionFailure as e:
            print(f"❌ Erro ao conectar ao MongoDB: {e}")
            self.client = None
            self.config_collection = None
            self.roles_collection = None

    def load_all_configs(self):
        self.config = {}
        if self.config_collection is not None:
            try:
                cursor = self.config_collection.find({})
                for doc in cursor:
                    guild_id = doc["_id"].replace("guild_", "")
                    self.config[guild_id] = {
                        "embed_title": doc.get("embed_title", "Painel de Registro"),
                        "embed_description": doc.get("embed_description", "Escolha suas opções abaixo para se registrar:"),
                        "embed_color": doc.get("embed_color", 0x2F3136),
                        "embed_footer": doc.get("embed_footer", "Clique em uma opção para selecionar"),
                        "embed_thumbnail": doc.get("embed_thumbnail", None),
                        "embed_image": doc.get("embed_image", None)
                    }
                print(f"📦 Carregadas {len(self.config)} configurações de servidores")
            except Exception as e:
                print(f"❌ Erro ao carregar configurações: {e}")

    def load_all_roles(self):
        self.registro_roles = {}
        if self.roles_collection is not None:
            try:
                cursor = self.roles_collection.find({})
                for doc in cursor:
                    guild_id = doc.get("guild_id")
                    categoria = doc.get("categoria")
                    nome_exibicao = doc.get("nome_exibicao")
                    role_id = doc.get("role_id")
                    role_name = doc.get("role_name", "Cargo desconhecido")
                    
                    if guild_id and categoria and nome_exibicao and role_id:
                        if guild_id not in self.registro_roles:
                            self.registro_roles[guild_id] = {"idade": {}, "genero": {}, "pronome": {}}
                        
                        if categoria in self.registro_roles[guild_id]:
                            self.registro_roles[guild_id][categoria][nome_exibicao] = {
                                'role_id': role_id,
                                'role_name': role_name
                            }
                
                total = sum(len(roles[cat]) for roles in self.registro_roles.values() for cat in roles)
                print(f"📦 Carregados {total} cargos de registro em {len(self.registro_roles)} servidores")
            except Exception as e:
                print(f"❌ Erro ao carregar cargos: {e}")

    def save_config(self, guild_id, config):
        if self.config_collection is not None:
            try:
                data = {
                    "_id": f"guild_{guild_id}",
                    "embed_title": config["embed_title"],
                    "embed_description": config["embed_description"],
                    "embed_color": config["embed_color"],
                    "embed_footer": config["embed_footer"],
                    "embed_thumbnail": config["embed_thumbnail"],
                    "embed_image": config["embed_image"]
                }
                self.config_collection.replace_one({"_id": f"guild_{guild_id}"}, data, upsert=True)
            except Exception as e:
                print(f"❌ Erro ao salvar configuração: {e}")

    async def add_registro_role(self, interaction: discord.Interaction, categoria: str, nome_exibicao: str, role_id: int, role_name: str):
        guild_id = str(interaction.guild_id)
        
        if guild_id not in self.registro_roles:
            self.registro_roles[guild_id] = {"idade": {}, "genero": {}, "pronome": {}}
        
        if nome_exibicao in self.registro_roles[guild_id][categoria]:
            await interaction.response.send_message(f"❌ O nome '{nome_exibicao}' já existe em {categoria}!", ephemeral=True)
            return
        
        self.registro_roles[guild_id][categoria][nome_exibicao] = {
            'role_id': role_id,
            'role_name': role_name
        }
        
        if self.roles_collection is not None:
            self.roles_collection.update_one(
                {"guild_id": guild_id, "categoria": categoria, "nome_exibicao": nome_exibicao},
                {"$set": {
                    "guild_id": guild_id,
                    "categoria": categoria,
                    "nome_exibicao": nome_exibicao,
                    "role_id": role_id,
                    "role_name": role_name
                }},
                upsert=True
            )
        
        embed = self.create_preview_embed(guild_id)
        try:
            await interaction.response.edit_message(embed=embed, view=RegistroConfigView(self, interaction, guild_id))
            await interaction.followup.send(f"✅ Opção '{nome_exibicao}' adicionada em {categoria}!", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ Opção '{nome_exibicao}' adicionada em {categoria}!", ephemeral=True)

    async def remove_registro_role(self, interaction: discord.Interaction, categoria: str, nome_exibicao: str):
        guild_id = str(interaction.guild_id)
        
        if guild_id not in self.registro_roles or nome_exibicao not in self.registro_roles[guild_id][categoria]:
            await interaction.response.send_message(f"❌ Opção '{nome_exibicao}' não encontrada!", ephemeral=True)
            return
        
        del self.registro_roles[guild_id][categoria][nome_exibicao]
        
        if self.roles_collection is not None:
            self.roles_collection.delete_one({"guild_id": guild_id, "categoria": categoria, "nome_exibicao": nome_exibicao})
        
        embed = self.create_preview_embed(guild_id)
        try:
            await interaction.response.edit_message(embed=embed, view=RegistroConfigView(self, interaction, guild_id))
            await interaction.followup.send(f"✅ Opção '{nome_exibicao}' removida de {categoria}!")
        except:
            await interaction.response.send_message(f"✅ Opção '{nome_exibicao}' removida de {categoria}!", ephemeral=True)

    async def handle_registro_selection(self, interaction: discord.Interaction, guild_id: str, categoria: str, nome_exibicao: str):
        role_data = self.registro_roles.get(guild_id, {}).get(categoria, {}).get(nome_exibicao)
        
        if not role_data:
            await interaction.response.send_message("❌ Opção não encontrada!", ephemeral=True)
            return
        
        role_id = role_data['role_id']
        role = interaction.guild.get_role(role_id)
        
        if not role:
            await interaction.response.send_message("❌ O cargo associado não existe mais!", ephemeral=True)
            return
        
        roles_removidos = 0
        categoria_roles = self.registro_roles.get(guild_id, {}).get(categoria, {})
        
        for other_nome, other_data in categoria_roles.items():
            if other_nome != nome_exibicao:
                other_role = interaction.guild.get_role(other_data['role_id'])
                if other_role and other_role in interaction.user.roles:
                    try:
                        await interaction.user.remove_roles(other_role)
                        roles_removidos += 1
                    except:
                        pass
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            msg = f"❌ Opção '{nome_exibicao}' removida"
        else:
            await interaction.user.add_roles(role)
            msg = f"✅ Opção '{nome_exibicao}' selecionada"
        
        if roles_removidos > 0:
            msg += f" (e {roles_removidos} opção(ões) antiga(s) removida(s))"
        
        await interaction.response.send_message(msg, ephemeral=True)

    def create_preview_embed(self, guild_id):
        """Cria embed de preview com as opções configuradas em formato de lista por categoria"""
        config = self.config.get(guild_id, {
            "embed_title": "Painel de Registro",
            "embed_description": "Escolha suas opções abaixo para se registrar:",
            "embed_color": 0x2F3136,
            "embed_footer": "Clique em uma opção para selecionar",
            "embed_thumbnail": None,
            "embed_image": None
        })
        
        embed = discord.Embed(
            title=config["embed_title"],
            description=config["embed_description"],
            color=config["embed_color"]
        )
        
        # Pega as opções configuradas
        guild_roles = self.registro_roles.get(guild_id, {"idade": {}, "genero": {}, "pronome": {}})
        
        # Monta o campo de opções disponíveis
        opcoes_texto = "## Opções Disponíveis\n\n"
        
        # Categoria Idade
        if guild_roles["idade"]:
            opcoes_texto += "### Idade\n"
            for nome, data in guild_roles["idade"].items():
                opcoes_texto += f"- {nome} → @{data['role_name']}\n"
            opcoes_texto += "\n"
        
        # Categoria Gênero
        if guild_roles["genero"]:
            opcoes_texto += "### Gênero\n"
            for nome, data in guild_roles["genero"].items():
                opcoes_texto += f"- {nome} → @{data['role_name']}\n"
            opcoes_texto += "\n"
        
        # Categoria Pronomes
        if guild_roles["pronome"]:
            opcoes_texto += "### Pronomes\n"
            for nome, data in guild_roles["pronome"].items():
                opcoes_texto += f"- {nome} → @{data['role_name']}\n"
            opcoes_texto += "\n"
        
        # Adiciona o campo de opções ao embed
        embed.add_field(name="", value=opcoes_texto, inline=False)
        
        # Adiciona instrução de como usar
        embed.add_field(name="", value="---\n## Como usar\n\nClique em uma opção abaixo para selecionar", inline=False)
        
        if config["embed_footer"]:
            embed.set_footer(text=config["embed_footer"])
        if config["embed_thumbnail"]:
            embed.set_thumbnail(url=config["embed_thumbnail"])
        if config["embed_image"]:
            embed.set_image(url=config["embed_image"])
        
        return embed

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
                style=discord.TextStyle.paragraph if field == "description" else discord.TextStyle.short
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            value = self.input.value
            
            if self.field == 'color':
                try:
                    value = int(value.replace('#', ''), 16)
                except ValueError:
                    await interaction.response.send_message("Cor inválida! Use formato hex (ex: 2F3136).", ephemeral=True)
                    return
            
            self.cog.config[self.guild_id][f"embed_{self.field}"] = value
            self.cog.save_config(self.guild_id, self.cog.config[self.guild_id])
            
            embed = self.cog.create_preview_embed(self.guild_id)
            view = EditRegistroConfigView(self.cog, interaction, self.guild_id)
            await interaction.response.edit_message(embed=embed, view=view)

    @app_commands.command(name="config_registro", description="Configura as opções de registro (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def config_registro(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {
                "embed_title": "Painel de Registro",
                "embed_description": "Escolha suas opções abaixo para se registrar:",
                "embed_color": 0x2F3136,
                "embed_footer": "Clique em uma opção para selecionar",
                "embed_thumbnail": None,
                "embed_image": None
            }
        
        if guild_id not in self.registro_roles:
            self.registro_roles[guild_id] = {"idade": {}, "genero": {}, "pronome": {}}
        
        embed = self.create_preview_embed(guild_id)
        view = RegistroConfigView(self, interaction, guild_id)
        await interaction.response.send_message("⚙️ **Configuração do Registro**", embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="painel_registro", description="Envia o painel de registro no canal atual")
    @app_commands.default_permissions(administrator=True)
    async def painel_registro(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.registro_roles:
            await interaction.response.send_message("❌ Nenhuma opção configurada! Use `/config_registro` primeiro.", ephemeral=True)
            return
        
        has_options = any(self.registro_roles[guild_id][cat] for cat in ["idade", "genero", "pronome"])
        if not has_options:
            await interaction.response.send_message("❌ Nenhuma opção configurada! Use `/config_registro` para adicionar.", ephemeral=True)
            return
        
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Preciso da permissão `Gerenciar Cargos`!", ephemeral=True)
            return
        
        view = PainelRegistroView(self, guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Painel de registro enviado!", ephemeral=True)

    @app_commands.command(name="editar_registro", description="Edita a aparência do painel de registro (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def editar_registro(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.config:
            self.config[guild_id] = {
                "embed_title": "Painel de Registro",
                "embed_description": "Escolha suas opções abaixo para se registrar:",
                "embed_color": 0x2F3136,
                "embed_footer": "Clique em uma opção para selecionar",
                "embed_thumbnail": None,
                "embed_image": None
            }
        
        view = EditRegistroConfigView(self, interaction, guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.response.send_message("🎨 **Editar Aparência do Registro**", embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Register(bot))