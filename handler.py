# handler.py
import os
import logging
from discord.ext import commands

logger = logging.getLogger(__name__)

# ==============================================
#  CONFIGURAÇÃO DE COGS ATIVADOS - POR CATEGORIA
# ==============================================
# Basta adicionar/remover caminhos aqui.
# Formato: "commands.categoria.nome_do_arquivo" (sem .py)
# Comente ou remova para desativar temporariamente.

COGS_ENABLED = {
    
    "moderation": [
        "commands.moderation.security",
        "commands.moderation.embedcreator",
        "commands.moderation.clear",
        "commands.moderation.lockdown",
        "commands.moderation.moderation",
        "commands.moderation.slowmode",
        "commands.moderation.automod",
    ],

    "levels": [
        "commands.levels.levels",
        "commands.levels.rank",            
    ],
    
    "tickets": [
        "commands.tickets.tickets",
    ],
    "owner":  [
        "commands.owner.botupdate",
    ],
    
    "welcome": [
        "commands.welcome.welcome",
        "commands.welcome.autoresponse",
        "commands.welcome.goodbye",
    ],

    "utils": [
        "commands.utils.maintenance",
        "commands.utils.color",
        "commands.utils.register",
        "commands.utils.ping",
        "commands.utils.verify",
        "commands.utils.avatar",
        "commands.utils.botinfo",
        "commands.utils.serverinfo",
        "commands.utils.sorteio",
    ],

}

# ==============================================
# FUNÇÃO PRINCIPAL DE CARREGAMENTO
# ==============================================

async def load_cogs(bot: commands.Bot):
    """
    Carrega apenas os cogs listados acima.
    Mostra no console por categoria: o que foi ativado, falhas e avisos.
    """
    logger.info("═" * 50)
    logger.info("INICIANDO CARREGAMENTO DE COGS (por categoria)")
    logger.info("═" * 50)

    total_loaded = 0
    total_failed = 0
    total_skipped = 0

    for category, cog_list in COGS_ENABLED.items():
        logger.info(f"→ Categoria: {category.upper():<12} ({len(cog_list)} cogs configurados)")

        category_loaded = 0
        category_failed = 0

        for cog_path in cog_list:
            try:
                await bot.load_extension(cog_path)
                logger.info(f"   ✓ ATIVADO: {cog_path}")
                category_loaded += 1
                total_loaded += 1
            except commands.ExtensionNotFound:
                logger.warning(f"   ✗ NÃO ENCONTRADO: {cog_path}")
                category_failed += 1
                total_failed += 1
            except commands.ExtensionFailed as e:
                logger.error(f"   ✗ FALHA AO CARREGAR: {cog_path} → {e}")
                category_failed += 1
                total_failed += 1
            except Exception as e:
                logger.error(f"   ✗ ERRO INESPERADO: {cog_path} → {e}")
                category_failed += 1
                total_failed += 1

        if category_failed == 0 and category_loaded > 0:
            logger.info(f"   → Sucesso total na categoria {category}")
        elif category_loaded == 0:
            logger.info(f"   → Nenhum cog carregado nesta categoria")

        logger.info("")  # linha em branco entre categorias

    # Aviso: cogs na pasta que NÃO estão na lista
    all_possible_cogs = set()
    for root, _, files in os.walk('commands'):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                rel = os.path.relpath(os.path.join(root, file), start='.')
                module = rel.replace(os.sep, '.')[:-3]
                all_possible_cogs.add(module)

    enabled_flat = {cog for cats in COGS_ENABLED.values() for cog in cats}
    not_listed = all_possible_cogs - enabled_flat

    if not_listed:
        logger.warning("═" * 50)
        logger.warning("AVISO: Cogs encontrados na pasta mas NÃO ativados:")
        for cog in sorted(not_listed):
            logger.warning(f"   - {cog}")
        logger.warning("Adicione-os em COGS_ENABLED se quiser usar.")
        logger.warning("═" * 50)

    # Resumo final
    logger.info("═" * 50)
    logger.info(f"RESUMO FINAL:")
    logger.info(f"   Cogs ativados com sucesso: {total_loaded}")
    logger.info(f"   Falhas / não encontrados:   {total_failed}")
    logger.info(f"   Total configurados:         {sum(len(lst) for lst in COGS_ENABLED.values())}")
    logger.info("═" * 50)
