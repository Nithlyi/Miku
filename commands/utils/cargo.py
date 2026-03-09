import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, Button, View, Modal, TextInput
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


# Modal para adicionar novo cargo pelo ID
class AddCargoModal(Modal, title="Adicionar Cargo por ID"):
    def __init__(self, view: 'CargoConfigView'):
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

        try:
            cargo_id = int(self.cargo_id.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido! Digite um número válido.", ephemeral=True)
            return

        role = interaction.guild.get_role(cargo_id)
        if not role:
            await interaction.response.send_message("❌ Cargo não encontrado! Verifique o ID.", ephemeral=True)
            return

        await self.view.cog.add_cargo_role(interaction, nome_exibicao, cargo_id, role.name)


# Select para remover cargos
class RemoveCargoSelect(Select):
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
            custom_id="cargo:remove_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos para remover.", ephemeral=True)
            return

        nome_exibicao = self.values[0]
        await self.cog.remove_cargo_role(interaction, nome_exibicao)


# View de configuração dos cargos (para /config_cargo)
class CargoConfigView(View):
    def __init__(self, cog, interaction):
        super().__init__(timeout=300)
        self.cog = cog
        self.original_interaction = interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    @discord.ui.button(label="Adicionar Cargo por ID", style=discord.ButtonStyle.success, emoji="➕", row=0, custom_id="cargo:add_btn")
    async def add_button(self, interaction: discord.Interaction, button: Button):
        modal = AddCargoModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remover Cargo", style=discord.ButtonStyle.danger, emoji="➖", row=0, custom_id="cargo:remove_btn")
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        guild_id = str(interaction.guild_id)
        roles_dict = self.cog.roles_cargos.get(guild_id, {})

        if not roles_dict:
            await interaction.response.send_message("Não há cargos configurados para remover.", ephemeral=True)
            return

        view = View(timeout=60)
        view.add_item(RemoveCargoSelect(self.cog, roles_dict))
        await interaction.response.send_message("Selecione o cargo para remover:", view=view, ephemeral=True)

    @discord.ui.button(label="Atualizar Preview", style=discord.ButtonStyle.secondary, emoji="🔄", row=0, custom_id="cargo:refresh_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self.update_preview()

    async def update_preview(self):
        embed = self.cog.create_preview_embed(str(self.original_interaction.guild_id))
        try:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        except:
            pass


# Select para usuários escolherem seus cargos (PERSISTENTE)
class UserCargoSelect(Select):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        options = []

        guild_roles = cog.roles_cargos.get(str(guild_id), {})

        for nome_exibicao, role_data in guild_roles.items():
            role_name = role_data.get('role_name', 'Cargo')
            options.append(discord.SelectOption(
                label=nome_exibicao,
                description=f"Cargo: {role_name}",
                value=nome_exibicao
            ))

        if not options:
            options.append(discord.SelectOption(
                label="Nenhum cargo disponível",
                value="none",
                default=True
            ))

        super().__init__(
            placeholder="Escolha um cargo...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"cargo:user_select:{guild_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("Não há cargos configurados neste servidor.", ephemeral=True)
            return

        nome_exibicao = self.values[0]
        guild_roles = self.cog.roles_cargos.get(str(self.guild_id), {})
        role_data = guild_roles.get(nome_exibicao)

        if not role_data:
            await interaction.response.send_message("❌ Cargo não encontrado na configuração!", ephemeral=True)
            return

        role_id = role_data['role_id']
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message("❌ O cargo associado não existe mais no servidor!", ephemeral=True)
            return

        # Verifica se o bot tem permissão para gerenciar cargos
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ Não tenho a permissão `Gerenciar Cargos`! Avise um administrador.",
                ephemeral=True
            )
            return

        # Verifica se o cargo está abaixo do cargo mais alto do bot (hierarquia)
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                f"❌ Não consigo atribuir o cargo **{role.name}** pois ele está acima ou no mesmo nível que o meu cargo na hierarquia!\n"
                f"Peça a um administrador para mover o cargo do bot acima de **{role.name}**.",
                ephemeral=True
            )
            return

        # Toggle: adiciona ou remove o cargo
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Cargo '{nome_exibicao}' removido!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Cargo '{nome_exibicao}' adicionado!", ephemeral=True)


# View principal do painel de cargos (PERSISTENTE - para /painel_cargo)
class PainelCargoView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.add_item(UserCargoSelect(cog, guild_id))


# View para editar configurações do embed (para /editar_cargo)
class EditCargoConfigView(View):
    def __init__(self, cog, interaction, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.interaction = interaction
        self.guild_id = guild_id

    @discord.ui.button(label="Título", style=discord.ButtonStyle.primary, custom_id="cargo_edit_title_btn")
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditCargoConfigModal(
            self.cog, "title", "Editar Título", "Novo título:",
            interaction, self.cog.embed_configs[self.guild_id]["embed_title"], self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Descrição", style=discord.ButtonStyle.primary, custom_id="cargo_edit_desc_btn")
    async def edit_description(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditCargoConfigModal(
            self.cog, "description", "Editar Descrição", "Nova descrição:",
            interaction, self.cog.embed_configs[self.guild_id]["embed_description"], self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cor", style=discord.ButtonStyle.primary, custom_id="cargo_edit_color_btn")
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        current = f"{self.cog.embed_configs[self.guild_id]['embed_color']:06X}"
        modal = self.cog.EditCargoConfigModal(
            self.cog, "color", "Editar Cor", "Nova cor (hex):",
            interaction, current, self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.primary, custom_id="cargo_edit_footer_btn")
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        modal = self.cog.EditCargoConfigModal(
            self.cog, "footer", "Editar Footer", "Novo footer:",
            interaction, self.cog.embed_configs[self.guild_id]["embed_footer"], self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Thumbnail", style=discord.ButtonStyle.primary, custom_id="cargo_edit_thumb_btn")
    async def edit_thumbnail(self, interaction: discord.Interaction, button: Button):
        current = self.cog.embed_configs[self.guild_id]["embed_thumbnail"] or ""
        modal = self.cog.EditCargoConfigModal(
            self.cog, "thumbnail", "Editar Thumbnail", "URL da thumbnail:",
            interaction, current, self.guild_id
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Imagem", style=discord.ButtonStyle.primary, custom_id="cargo_edit_img_btn")
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        current = self.cog.embed_configs[self.guild_id]["embed_image"] or ""
        modal = self.cog.EditCargoConfigModal(
            self.cog, "image", "Editar Imagem", "URL da imagem:",
            interaction, current, self.guild_id
        )
        await interaction.response.send_modal(modal)


class Cargo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = "discord_bot"
        self.collection_name = "cargo_config"
        self.roles_collection_name = "cargo_roles"
        self.client = None
        self.config_collection = None
        self.roles_collection = None
        self.roles_cargos = {}   # guild_id -> {nome_exibicao: {'role_id': id, 'role_name': nome}}
        self.embed_configs = {}  # guild_id -> {title, description, color, footer, thumbnail, image}

        self.connect_mongo()
        self.load_all_configs()
        self.load_all_roles()

        # Registra views persistentes para cada servidor
        for guild_id in self.roles_cargos:
            self.bot.add_view(PainelCargoView(self, int(guild_id)))

    def connect_mongo(self):
        try:
            self.client = MongoClient(self.mongo_uri)
            self.config_collection = self.client[self.db_name][self.collection_name]
            self.roles_collection = self.client[self.db_name][self.roles_collection_name]
            self.client.admin.command('ping')
            print("✅ [Cargo] Conectado ao MongoDB com sucesso.")
        except ConnectionFailure:
            print("❌ [Cargo] Erro ao conectar ao MongoDB. Usando valores padrão.")
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
                        "embed_title": doc.get("embed_title", "Painel de Cargos"),
                        "embed_description": doc.get("embed_description", "Selecione os cargos que deseja receber:"),
                        "embed_color": doc.get("embed_color", 0x5865F2),
                        "embed_footer": doc.get("embed_footer", "Clique no menu abaixo para pegar/remover um cargo"),
                        "embed_thumbnail": doc.get("embed_thumbnail", None),
                        "embed_image": doc.get("embed_image", None)
                    }
            print(f"📦 [Cargo] Carregadas {len(self.embed_configs)} configurações de servidores")

    def get_guild_config(self, guild_id):
        """Retorna a configuração de um servidor ou cria uma padrão"""
        if guild_id not in self.embed_configs:
            self.embed_configs[guild_id] = {
                "embed_title": "Painel de Cargos",
                "embed_description": "Selecione os cargos que deseja receber:",
                "embed_color": 0x5865F2,
                "embed_footer": "Clique no menu abaixo para pegar/remover um cargo",
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
        """Carrega os cargos do MongoDB por servidor"""
        self.roles_cargos = {}
        if self.roles_collection is not None:
            cursor = self.roles_collection.find({})
            for doc in cursor:
                guild_id = str(doc.get("guild_id"))
                nome_exibicao = doc.get("nome_exibicao")
                role_id = doc.get("role_id")
                role_name = doc.get("role_name", "Cargo desconhecido")

                if guild_id and nome_exibicao and role_id:
                    if guild_id not in self.roles_cargos:
                        self.roles_cargos[guild_id] = {}

                    self.roles_cargos[guild_id][nome_exibicao] = {
                        'role_id': role_id,
                        'role_name': role_name
                    }

            total = sum(len(roles) for roles in self.roles_cargos.values())
            print(f"📦 [Cargo] Carregados {total} cargos em {len(self.roles_cargos)} servidores")

    async def add_cargo_role(self, interaction: discord.Interaction, nome_exibicao: str, role_id: int, role_name: str):
        """Adiciona um novo cargo ao painel"""
        guild_id = str(interaction.guild_id)

        if guild_id not in self.roles_cargos:
            self.roles_cargos[guild_id] = {}

        if nome_exibicao in self.roles_cargos[guild_id]:
            await interaction.response.send_message(f"❌ O nome '{nome_exibicao}' já existe!", ephemeral=True)
            return

        self.roles_cargos[guild_id][nome_exibicao] = {
            'role_id': role_id,
            'role_name': role_name
        }

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

        embed = self.create_preview_embed(guild_id)

        try:
            await interaction.response.edit_message(embed=embed, view=CargoConfigView(self, interaction))
            await interaction.followup.send(f"✅ Cargo '{nome_exibicao}' adicionado! (Cargo: {role_name})", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ Cargo '{nome_exibicao}' adicionado! (Cargo: {role_name})", ephemeral=True)

    async def remove_cargo_role(self, interaction: discord.Interaction, nome_exibicao: str):
        """Remove um cargo do painel"""
        guild_id = str(interaction.guild_id)

        if guild_id not in self.roles_cargos or nome_exibicao not in self.roles_cargos[guild_id]:
            await interaction.response.send_message(f"❌ Cargo '{nome_exibicao}' não encontrado!", ephemeral=True)
            return

        role_data = self.roles_cargos[guild_id][nome_exibicao]
        role_name = role_data.get('role_name', 'Cargo desconhecido')

        del self.roles_cargos[guild_id][nome_exibicao]

        if self.roles_collection is not None:
            self.roles_collection.delete_one({"guild_id": guild_id, "nome_exibicao": nome_exibicao})

        embed = self.create_preview_embed(guild_id)

        try:
            await interaction.response.edit_message(embed=embed, view=CargoConfigView(self, interaction))
            await interaction.followup.send(f"✅ Cargo '{nome_exibicao}' removido! (Cargo: {role_name})", ephemeral=True)
        except:
            await interaction.response.send_message(f"✅ Cargo '{nome_exibicao}' removido! (Cargo: {role_name})", ephemeral=True)

    def create_preview_embed(self, guild_id):
        """Cria embed de preview com a lista de cargos disponíveis"""
        config = self.get_guild_config(guild_id)

        embed = discord.Embed(
            title=config["embed_title"],
            description=config["embed_description"],
            color=config["embed_color"]
        )

        if guild_id in self.roles_cargos and self.roles_cargos[guild_id]:
            cargos_lista = []
            for nome_exibicao, role_data in self.roles_cargos[guild_id].items():
                role_name = role_data.get('role_name', 'Cargo desconhecido')
                cargos_lista.append(f"**{nome_exibicao}** → `@{role_name}`")

            embed.add_field(
                name="Cargos Disponíveis",
                value="\n".join(cargos_lista),
                inline=False
            )
        else:
            embed.add_field(
                name="Cargos Disponíveis",
                value="*Nenhum cargo configurado neste servidor*",
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
    class EditCargoConfigModal(Modal):
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
                    await interaction.response.send_message("Cor inválida! Use formato hex (ex: 5865F2).", ephemeral=True)
                    return

            config = self.cog.get_guild_config(self.guild_id)
            config[f"embed_{self.field}"] = value
            self.cog.save_guild_config(self.guild_id)

            embed = self.cog.create_preview_embed(self.guild_id)
            view = EditCargoConfigView(self.cog, interaction, self.guild_id)
            await interaction.response.edit_message(embed=embed, view=view)

    # ── Comandos slash ──────────────────────────────────────────────────────────

    @app_commands.command(name="config_cargo", description="Configura os cargos do painel (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def config_cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        embed = self.create_preview_embed(guild_id)
        view = CargoConfigView(self, interaction)
        await interaction.response.send_message("⚙️ **Configuração dos Cargos**", embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="painel_cargo", description="Envia o painel de cargos no canal atual (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def painel_cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)

        if guild_id not in self.roles_cargos or not self.roles_cargos[guild_id]:
            await interaction.response.send_message(
                "❌ Não há cargos configurados! Use `/config_cargo` para adicionar.", ephemeral=True
            )
            return

        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Preciso da permissão `Gerenciar Cargos`!", ephemeral=True)
            return

        view = PainelCargoView(self, interaction.guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Painel de cargos enviado com sucesso!", ephemeral=True)

    @app_commands.command(name="editar_cargo", description="Edita a aparência do painel de cargos (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def editar_cargo(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        self.get_guild_config(guild_id)  # garante que a config existe
        view = EditCargoConfigView(self, interaction, guild_id)
        embed = self.create_preview_embed(guild_id)
        await interaction.response.send_message("🎨 **Editar Aparência do Painel de Cargos**", embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Cargo(bot))