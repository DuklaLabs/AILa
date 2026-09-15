"""Zpětně kompatibilní re-export.

Klient duklamaps rozvrhu se přesunul do sdíleného balíčku jako
`ailacore.dukla`, ať ho můžou používat i agenti mimo tuhle službu
(agentní vrstva, §21). Tady zůstává jen tenký re-export, aby stávající
importy `from app.dukla_db import ...` fungovaly beze změny.
"""
from ailacore.dukla import *  # noqa: F401,F403
from ailacore.dukla import _DAY_BASE, get_dukla_pool  # noqa: F401
