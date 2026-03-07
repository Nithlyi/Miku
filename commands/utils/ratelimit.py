# utils/ratelimit.py
import discord
from discord.ext import commands
from discord import app_commands
import time
from typing import Dict

class UserCooldown:
    """Cooldown simples por usuário (global para todos comandos)"""
    def __init__(self, cooldown_seconds: float = 6.0):
        self.cooldown = cooldown_seconds
        self.last_used: Dict[int, float] = {}  # user_id → timestamp da última execução

    def is_on_cooldown(self, user_id: int) -> bool:
        now = time.time()
        last = self.last_used.get(user_id, 0)
        return now - last < self.cooldown

    def update(self, user_id: int):
        self.last_used[user_id] = time.time()

    def remaining(self, user_id: int) -> float:
        now = time.time()
        last = self.last_used.get(user_id, 0)
        remaining = self.cooldown - (now - last)
        return max(0, remaining)


# Instância global (pode ser importada em qualquer lugar)
cooldown_manager = UserCooldown(cooldown_seconds=6.0)