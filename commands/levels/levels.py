import discord
from discord import app_commands, Interaction, Embed, Colour, SelectOption
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput
import datetime

class LevelRewardModal(Modal, title="Adicionar Recompensa por Nível"):
    def __init__(self, view: 'RewardView'):
        super().__init__()
        self.view = view

    nivel = TextInput(
        label="Nível",
        placeholder="Digite o número do nível (ex: 5, 10, 20)",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: Interaction):
        try:
            nivel = int(self.nivel.value.strip())
            if nivel < 1:
                await interaction.response.send_message("O nível deve ser maior que 0.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("Digite um número válido para o nível.", ephemeral=True)
            return

        self.view.selected_level = nivel
        await interaction.response.defer(ephemeral=True)

        select_view = View()
        role_select = discord.ui.RoleSelect(placeholder="Selecione o cargo da recompensa")
        
        async def role_callback(inter: Interaction):
            role = role_select.values[0]
            await self.view.add_reward(inter, nivel, role)

        role_select.callback = role_callback
        select_view.add_item(role_select)
        
        await interaction.followup.send(
            f"Você escolheu o nível **{nivel}**. Agora selecione o cargo:",
            view=select_view,
            ephemeral=True
        )


class RewardView(View):
    def __init__(self, interaction: Interaction, bot):
        super().__init__(timeout=300)
        self.original_interaction = interaction
        self.bot = bot
        self.guild_id = interaction.guild_id
        self.selected_level = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.original_interaction.user.id

    async def get_config(self):
        return self.bot.db.guild_configs.find_one({"guild_id": self.guild_id}) or {}

    async def save_config(self, config):
        self.bot.db.guild_configs.replace_one({"guild_id": self.guild_id}, config, upsert=True)

    async def update_message(self):
        config = await self.get_config()
        rewards = config.get("level_rewards", [])
        xp_enabled = config.get("xp_enabled", True)  # Pega o status do sistema
        
        # Status do sistema
        status_emoji = "✅" if xp_enabled else "❌"
        status_text = f"{status_emoji} Sistema de XP: **{'ATIVADO' if xp_enabled else 'DESATIVADO'}**\n\n"
        
        if not rewards:
            description = status_text + "Nenhuma recompensa configurada ainda."
        else:
            lines = [status_text]
            for r in rewards:
                role = self.bot.get_guild(self.guild_id).get_role(int(r["role_id"]))
                role_name = role.name if role else f"ID {r['role_id']} (cargo deletado)"
                lines.append(f"Nível **{r['level']}** → {role_name}")
            description = "\n".join(lines)

        embed = Embed(
            title="⚙️ Configuração do Sistema de Níveis",
            description=description,
            color=discord.Color.from_str("#1A1A1A")
        )
        embed.set_footer(text="Use o menu abaixo para gerenciar")

        try:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            await self.original_interaction.followup.send(embed=embed, view=self, ephemeral=True)

    @discord.ui.select(
        placeholder="O que você deseja fazer?",
        options=[
            SelectOption(label="Adicionar recompensa", value="add", emoji="➕"),
            SelectOption(label="Remover recompensa", value="remove", emoji="➖"),
            SelectOption(label="Atualizar lista", value="refresh", emoji="🔄"),
            SelectOption(label="Ativar/Desativar XP", value="toggle", emoji="🔌"),
        ],
        row=0
    )
    async def main_menu(self, interaction: Interaction, select: Select):
        choice = select.values[0]

        if choice == "add":
            modal = LevelRewardModal(self)
            await interaction.response.send_modal(modal)

        elif choice == "remove":
            config = await self.get_config()
            rewards = config.get("level_rewards", [])
            if not rewards:
                await interaction.response.send_message("Não há recompensas para remover.", ephemeral=True)
                return

            select_view = View()
            remove_select = Select(placeholder="Selecione a recompensa para remover")
            
            for r in rewards:
                role = self.bot.get_guild(self.guild_id).get_role(int(r["role_id"]))
                role_name = role.name if role else f"ID {r['role_id']}"
                remove_select.add_option(
                    label=f"Nível {r['level']} → {role_name}",
                    value=str(r["level"])
                )

            async def remove_callback(inter: Interaction):
                level_to_remove = int(remove_select.values[0])
                rewards[:] = [r for r in rewards if r["level"] != level_to_remove]
                config["level_rewards"] = rewards
                await self.save_config(config)
                await inter.response.send_message(f"Recompensa do nível {level_to_remove} removida.", ephemeral=True)
                await self.update_message()

            remove_select.callback = remove_callback
            select_view.add_item(remove_select)
            
            await interaction.response.send_message("Selecione a recompensa para remover:", view=select_view, ephemeral=True)

        elif choice == "refresh":
            await interaction.response.defer(ephemeral=True)
            await self.update_message()
            
        elif choice == "toggle":
            config = await self.get_config()
            current_status = config.get("xp_enabled", True)
            new_status = not current_status
            
            config["xp_enabled"] = new_status
            await self.save_config(config)
            
            status_msg = "✅ **ATIVADO**" if new_status else "❌ **DESATIVADO**"
            await interaction.response.send_message(
                f"Sistema de XP {status_msg} com sucesso!",
                ephemeral=True
            )
            await self.update_message()

    async def add_reward(self, interaction: Interaction, level: int, role: discord.Role):
        config = await self.get_config()
        rewards = config.get("level_rewards", [])

        # Atualiza se já existir para esse nível
        rewards = [r for r in rewards if r["level"] != level]
        rewards.append({"level": level, "role_id": str(role.id)})

        config["level_rewards"] = rewards
        await self.save_config(config)

        await interaction.followup.send(
            f"Recompensa adicionada: **Nível {level}** → **{role.name}**",
            ephemeral=True
        )
        await self.update_message()


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Pega a configuração do servidor
        config = self.bot.db.guild_configs.find_one({"guild_id": message.guild.id}) or {
            "xp_per_msg": 10,
            "xp_cooldown": 45,
            "xp_multiplier": 1.0,
            "xp_curve": 1.5,
            "level_rewards": [],
            "xp_enabled": True  # Default: ativado
        }

        # Verifica se o sistema de XP está ativado
        if not config.get("xp_enabled", True):
            return  # Sai da função sem processar XP

        guild_id = message.guild.id
        user_id = message.author.id
        now = datetime.datetime.utcnow()

        user_filter = {"guild_id": guild_id, "user_id": user_id}
        user_data = self.bot.db.levels.find_one(user_filter)

        if user_data is None:
            user_data = {
                "guild_id": guild_id,
                "user_id": user_id,
                "xp": 0,
                "level": 0,
                "last_xp": now - datetime.timedelta(seconds=config["xp_cooldown"] + 1),
                "messages": 0
            }
            self.bot.db.levels.insert_one(user_data)
        else:
            if "last_xp" not in user_data:
                user_data["last_xp"] = now - datetime.timedelta(seconds=config["xp_cooldown"] + 1)
                self.bot.db.levels.replace_one(user_filter, user_data, upsert=True)

        time_since_last = (now - user_data["last_xp"]).total_seconds()
        if time_since_last < config["xp_cooldown"]:
            return

        xp_gain = int(config["xp_per_msg"] * config["xp_multiplier"])
        user_data["xp"] += xp_gain
        user_data["last_xp"] = now
        user_data["messages"] = user_data.get("messages", 0) + 1

        old_level = user_data["level"]
        level = 0
        required = 0
        curve = config["xp_curve"]
        while required <= user_data["xp"]:
            level += 1
            required += int(100 * (level ** curve))

        if level > old_level:
            user_data["level"] = level
            embed = discord.Embed(
                title="↑ Level Up!",
                description=f"Parabéns {message.author.mention}! Você alcançou o **nível {level}**!",
                color=discord.Color.from_str("#1A1A1A")
            )
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else None)
            await message.channel.send(embed=embed)

            # Sistema de recompensa
            rewards = config.get("level_rewards", [])
            for reward in rewards:
                if reward["level"] == level:
                    try:
                        role = message.guild.get_role(int(reward["role_id"]))
                        if role and role not in message.author.roles:
                            await message.author.add_roles(role, reason=f"Recompensa automática - Nível {level}")
                            reward_embed = discord.Embed(
                                title="Nova Recompensa!",
                                description=f"{message.author.mention} ganhou o cargo **{role.name}** ao atingir o nível {level}!",
                                color=discord.Color.green()
                            )
                            await message.channel.send(embed=reward_embed)
                    except Exception as e:
                        print(f"Erro ao dar recompensa: {e}")

        self.bot.db.levels.replace_one(user_filter, user_data, upsert=True)

    # Comando /reward (gerenciamento)
    @app_commands.command(name="reward", description="Gerenciar recompensas e configurações do sistema de níveis (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def reward(self, interaction: Interaction):
        view = RewardView(interaction, self.bot)
        await interaction.response.send_message(
            "⚙️ Gerenciando sistema de níveis...",
            view=view,
            ephemeral=True
        )
        await view.update_message()

    # Comando /xp (ver progresso)
    @app_commands.command(name="xp", description="Veja seu progresso de XP e nível")
    @app_commands.describe(member="Ver o XP de outro usuário (opcional)")
    async def xp(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer(ephemeral=False)

        target = member or interaction.user
        guild_id = interaction.guild_id
        user_id = target.id

        data = self.bot.db.levels.find_one({"guild_id": guild_id, "user_id": user_id}) or {"xp": 0, "level": 0}
        config = self.bot.db.guild_configs.find_one({"guild_id": guild_id}) or {"xp_curve": 1.5}

        xp = data["xp"]
        curve = config["xp_curve"]

        level = 0
        total_required = 0
        while True:
            next_required = total_required + int(100 * ((level + 1) ** curve))
            if next_required > xp:
                break
            level += 1
            total_required = next_required

        xp_for_next = int(100 * ((level + 1) ** curve))
        xp_in_level = xp - total_required
        xp_needed = xp_for_next

        bar_length = 20
        filled = int(bar_length * (xp_in_level / xp_needed)) if xp_needed > 0 else bar_length
        bar = "█" * filled + "░" * (bar_length - filled)

        embed = discord.Embed(
            title=f"Progresso de {target.name}",
            description=f"**Nível {level}**\nXP: **{xp_in_level:,} / {xp_needed:,}** ({(xp_in_level / xp_needed * 100):.1f}%)\n\n`{bar}`",
            color=discord.Color.from_str("#1A1A1A")
        )
        embed.set_thumbnail(url=target.avatar.url if target.avatar else None)
        embed.set_footer(text=f"Total XP: {xp:,}")

        await interaction.followup.send(embed=embed, ephemeral=False)

    # Comando para ver status do sistema
    @app_commands.command(name="xpstatus", description="Verifica se o sistema de XP está ativo no servidor")
    async def xp_status(self, interaction: discord.Interaction):
        config = self.bot.db.guild_configs.find_one({"guild_id": interaction.guild_id}) or {}
        xp_enabled = config.get("xp_enabled", True)
        
        status = "✅ **ATIVADO**" if xp_enabled else "❌ **DESATIVADO**"
        embed = discord.Embed(
            title="📊 Status do Sistema de XP",
            description=f"Sistema de XP: {status}",
            color=discord.Color.green() if xp_enabled else discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Levels(bot))