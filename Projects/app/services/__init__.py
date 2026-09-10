"""Servisní vrstva služby Projects.

Veškerá byznys logika je tady jako async funkce `fn(user, ...)` s RBAC kontrolou
uvnitř (přes `ailacore.rbac.user_has_permission`). HTTP routy (`app/routers/`)
i MCP nástroje (`app/mcp_server.py`) jsou jen tenké obaly – hranice
„přímá změna vs. návrh ke schválení“ je pak na jednom místě a nedá se obejít.
"""
