"""Naseeduje demo data projektového systému z databanky DuklaLabs.

    docker compose exec projects-server python -m app.seed_demo
    # nebo lokálně:  POSTGRES_HOST=localhost python -m app.seed_demo

Vytvoří projekty odpovídající tématům z `dukulabs-databanka-projektu.md`
(rozdělené do složek Komerční prototypy / Interní R&D / Globální přehledy),
ke každému 5 fází z šablony a realistické úkoly napříč fázemi: řešitelé
z reálných účtů, stavy-semafor, timeline, verze prototypů, finanční pole
u fáze Nákupy, měřený čas a pár závislostí. Přidá i 3 čekající návrhy od AI.

Skript je destruktivní: nejdřív smaže VŠECHNA data v `projects.projects`
a `projects.proposals` (workspace, složky a šablonu fází z migrace nechává).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import random

from ailacore.db import close_pool, get_pool

SEED = 20260909
random.seed(SEED)

# ---------------------------------------------------------------------------
# Projekty z databanky:  (název, složka-kind, stav, rozpočet Kč | None, popis)
# ---------------------------------------------------------------------------
COMMERCIAL, RND, OVERVIEW = "commercial", "internal_rnd", "overview"

PROJECTS = [
    # --- Vlna 0 / jádro (Interní R&D) ---
    ("Sdílené API jádro + RFID SSO", RND, "done", None,
     "Architektonický základ pro všechny moduly – DB schéma, jednotné přihlášení přes RFID/heslo, DB pool."),
    ("Jednotný systém rolí a oprávnění (RBAC)", RND, "done", None,
     "Granulární oprávnění napříč všemi moduly (schema.resource:action), admin konzole."),
    ("Auditní log napříč celým systémem", RND, "active", None,
     "Kdo co změnil a kdy – nutné pro důvěru při větším počtu lidí s přístupem."),

    # --- Vlna 1 ---
    ("RFID docházkový terminál (web + čtečka)", COMMERCIAL, "active", 4500,
     "Prohlížeč v kiosk módu + USB RFID/NFC čtečka (HID). Offline cache, napojení na rozvrh."),
    ("Skladový systém – web/API nad ESP32+LED", COMMERCIAL, "active", 9000,
     "WS2812B LED pásky do šuplíků + ESP32 řadič (rozjeto), chybí webová/API vrstva."),
    ("Přihlašovací formulář a kapacity kroužku ZŠ", RND, "active", None,
     "Přihlášky na kroužek Technická škola nanečisto, potvrzení, upomínky, hlídání kapacity stanic."),
    ("Projektový/task management systém (kanban)", RND, "active", None,
     "Tento systém. Hierarchie, datová karta úkolu, time tracking, audit log, MCP napojení na AI."),
    ("Wiki / knowledge base laborky", RND, "active", None,
     "Návody, troubleshooting, verzování stránek. Základ pro chatbota nad wiki."),
    ("CRM na partnery a sponzory", RND, "on_hold", None,
     "Kontakty, zápůjčky (Festo Didactic), historie spolupráce."),
    ("Grantový tracker", RND, "active", None,
     "Termíny a vykazování grantů, upomínky na deadliny."),
    ("Nástroj na rychlé ankety a hlasování", RND, "on_hold", None,
     "Rychlé rozhodnutí napříč skupinou bez svolávání schůzky."),
    ("Interní helpdesk pro IT požadavky", RND, "active", None,
     "Žádosti o přístup, reset hesla, podpora na jednom místě."),
    ("Sledování energií a prostředí v laborce (senzory)", COMMERCIAL, "active", 6500,
     "BME280/SCD30 (teplota, vlhkost, CO2), PZEM-004T (spotřeba), grafy v čase přes MQTT."),

    # --- Vlna 2 ---
    ("Evidence skupin ZŠ a docházka na kroužek", RND, "active", 3000,
     "Jednorázové NFC náramky + webový kiosek. Děti nemají trvalou kartu školy."),
    ("Evidence proškolení a oprávnění na stroje", COMMERCIAL, "active", 5500,
     "Identifikace kartou přes web/USB čtečku; malý ESP32+relé modul u stroje přijme pokyn k odemčení."),
    ("Objednávkový systém se schvalováním a rozpočtem", RND, "active", None,
     "Role, napojení na grantové rozpočty, propojení se skladem."),
    ("Rezervační systém vybavení a laborky", COMMERCIAL, "active", 4000,
     "Stav fronty na tabletu; volitelně ESP32+relé pro fyzické blokování stroje. Konflikty, notifikace."),
    ("Notifikační bot (Telegram/Discord)", RND, "active", None,
     "Malý integrační projekt – události ze skladu/objednávek do chatu."),
    ("AI zpracování zápisů schůzek → úkoly", RND, "active", None,
     "Vložení zápisu → LLM extrahuje úkoly → návrh k potvrzení → zápis do DB úkolů. Fuzzy mapování jmen."),
    ("Organizace do týmů a skupin s vedoucími", RND, "on_hold", None,
     "Přiřazení do soutěžních týmů/ročníků/kroužků, delegace schvalování na vedoucí skupin."),

    # --- Vlna 3 ---
    ("Fronta na 3D tiskárny a laser", COMMERCIAL, "active", 3500,
     "Tablet/monitor s frontou, volitelně USB webkamera na sledování tisku. Odhad doby dokončení."),
    ("Kapacitní plánování strojového času", COMMERCIAL, "on_hold", 7000,
     "Proudový senzor (SCT-013 / PZEM-004T) – vytíženost a úzká hrdla bez ručního zápisu."),
    ("Plánování údržby a kalibrace strojů", COMMERCIAL, "active", 5000,
     "Vibrační senzor/akcelerometr, počítadlo motohodin. Prediktivní údržba z provozních dat."),
    ("BOZP / revizní dokumentace a přeškolení", COMMERCIAL, "on_hold", 4500,
     "Dveřní kontakty na skříních s nebezpečnými nástroji, propojení nouzového zastavení. Termíny revizí."),
    ("Napojení e-mailu → automatické úkoly (AI)", RND, "on_hold", None,
     "OAuth schránka → LLM klasifikátor → návrh úkolu s odkazem na email. Práh jistoty, bezpečnost."),
    ("OTA update a zabezpečení ESP32 firmware (sklad)", COMMERCIAL, "on_hold", 2000,
     "Embedded-security rovina nad rozjetým skladovým HW."),

    # --- Vlna 4 / Globální přehledy ---
    ("Rozpočtový přehled laborky", OVERVIEW, "active", None,
     "Agregace grantů + provozu + sponzoringu z více zdrojů."),
    ("Kiosk dashboard pro laborku (TV displej)", OVERVIEW, "active", 3000,
     "Raspberry Pi + TV/monitor. Frontend nad hotovým API."),
    ("Analytický dashboard napříč moduly", OVERVIEW, "on_hold", None,
     "Potřebuje data z docházky + skladu + objednávek. Zdraví portfolia, vytížení lidí, timesheety."),
    ("Automatický generátor výkazů a reportů", OVERVIEW, "on_hold", None,
     "Agregace dat napříč docházkou, skladem a rozpočtem do hotového dokumentu pro granty/vedení."),
    ("Mobilní appka pro studenty", COMMERCIAL, "on_hold", 8000,
     "Docházka, rezervace, stav objednávek. Potřebuje stabilní API napříč moduly."),
    ("Prediktivní odhad potřeby zdrojů", OVERVIEW, "on_hold", None,
     "Plánování materiálu/rozpočtu dopředu podle očekávaného růstu počtu lidí."),
]

# ---------------------------------------------------------------------------
# Úkoly – pool na fázi (index 0..4). U fáze „Nákupy" se doplní finanční pole.
# ---------------------------------------------------------------------------
PHASE_TASKS = [
    [  # 1 Koncept & Specifikace
        "Analýza požadavků a use-case",
        "Bloková architektura systému",
        "Rešerše existujících řešení",
        "Specifikace rozhraní (API / HW piny)",
        "Rozpočtový a časový odhad",
        "Schválení zadání vedoucím",
    ],
    [  # 2 Vývoj & Návrh
        "Návrh datového modelu / DB schématu",
        "Kreslení schématu zapojení",
        "PCB layout",
        "CAD model mechaniky",
        "Návrh UI/UX obrazovek",
        "Interní revize návrhu s kolegou",
    ],
    [  # 3 Nákupy & Logistika
        "Objednávka součástek (Mouser / DigiKey)",
        "Výroba DPS (JLCPCB)",
        "3D tisk krabičky",
        "Nákup měřáku / nářadí",
        "Evidence došlého materiálu",
    ],
    [  # 4 Výroba & Oživení
        "Osazení desky",
        "První oživení v laboratoři",
        "Ladění napájení 5V / 3.3V",
        "Sestavení funkčního vzorku",
        "Fotodokumentace prototypu",
    ],
    [  # 5 Firmware & Integrace
        "Bring-up firmware / kostra aplikace",
        "Implementace hlavní logiky",
        "Integrace s API jádrem (ailacore)",
        "Ladění chyb (debugging)",
        "Testy a předání funkčního vzorku",
    ],
]

COST_TYPE_BY_TASK = {
    "Objednávka součástek (Mouser / DigiKey)": ("components", 400, 9000),
    "Výroba DPS (JLCPCB)": ("pcb", 600, 4000),
    "3D tisk krabičky": ("mechanical", 150, 1200),
    "Nákup měřáku / nářadí": ("tools", 800, 12000),
}
ORDER_STATES = ["cart", "ordered", "in_lab"]

# stav-semafor podle fáze: dřívější fáze víc hotové, pozdější víc backlog
STATUS_BY_PHASE = [
    ["done", "done", "done", "in_progress", "design_review"],
    ["done", "done", "in_progress", "in_progress", "design_review", "blocked"],
    ["done", "in_progress", "ordered_marker", "backlog", "backlog"],
    ["in_progress", "design_review", "backlog", "backlog", "blocked"],
    ["backlog", "backlog", "backlog", "in_progress", "backlog"],
]
REAL_STATUSES = {"backlog", "in_progress", "design_review", "blocked", "done"}
PROTO_VERSIONS = [None, None, "Proto-V1", "Proto-V1", "Proto-V2"]


async def _users(conn) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, full_name, username FROM auth.users "
        "WHERE is_active AND username <> 'admin' ORDER BY id"
    )
    return [dict(r) for r in rows] or [{"id": 1, "full_name": "admin", "username": "admin"}]


def _pick_status(phase_idx: int) -> str:
    s = random.choice(STATUS_BY_PHASE[phase_idx])
    return s if s in REAL_STATUSES else "backlog"


async def main() -> None:
    pool = await get_pool()
    today = dt.date.today()

    async with pool.acquire() as conn:
        users = await _users(conn)
        leads = users[: min(8, len(users))]

        async with conn.transaction():
            await conn.execute("DELETE FROM projects.proposals")
            await conn.execute("DELETE FROM projects.projects")  # cascade fáze/úkoly/čas/závislosti

            folder_id = {
                r["kind"]: r["id"]
                for r in await conn.fetch("SELECT id, kind FROM projects.folders")
            }
            phase_templates = [
                dict(r) for r in await conn.fetch(
                    "SELECT name, position FROM projects.phase_templates ORDER BY position"
                )
            ]

            n_tasks = n_time = n_dep = 0

            for pi, (name, kind, status, budget, desc) in enumerate(PROJECTS):
                due = today + dt.timedelta(days=30 * (2 + pi % 7) + 10 * (pi % 3))
                start = today - dt.timedelta(days=20 + pi * 3)
                lead = random.choice(leads)["id"]
                proj_id = await conn.fetchval(
                    """
                    INSERT INTO projects.projects
                        (folder_id, name, description, status, planned_budget_czk,
                         started_on, due_on, baseline_due_on, lead_user_id, created_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$7,$8,$8) RETURNING id
                    """,
                    folder_id[kind], name, desc, status, budget, start, due, lead,
                )

                phase_ids: list[int] = []
                for tpl in phase_templates:
                    phase_ids.append(await conn.fetchval(
                        "INSERT INTO projects.phases (project_id, name, position) "
                        "VALUES ($1,$2,$3) RETURNING id",
                        proj_id, tpl["name"], tpl["position"],
                    ))

                # kolik úkolů na fázi: 2–5, u pozdějších projektů (on_hold) míň
                base = 5 if status == "active" else 3
                by_phase_tasks: list[list[int]] = []

                for phase_idx, phase_id in enumerate(phase_ids):
                    pool_titles = PHASE_TASKS[phase_idx][:]
                    random.shuffle(pool_titles)
                    k = max(2, min(len(pool_titles), base - (1 if phase_idx >= 3 else 0)))
                    titles = pool_titles[:k]
                    created: list[int] = []

                    for pos, title in enumerate(titles):
                        st = _pick_status(phase_idx)
                        assignee = random.choice(users)["id"] if random.random() < 0.75 else None
                        proto = random.choice(PROTO_VERSIONS) if kind == COMMERCIAL else None
                        est_h = random.choice([None, 2, 3, 4, 6, 8, 12, 16]) if random.random() < 0.7 else None
                        s_on = start + dt.timedelta(days=phase_idx * 18 + pos * 4)
                        d_on = s_on + dt.timedelta(days=random.choice([3, 5, 7, 10, 14]))

                        cost_type = est_cost = act_cost = order_status = None
                        if title in COST_TYPE_BY_TASK:
                            cost_type, lo, hi = COST_TYPE_BY_TASK[title]
                            est_cost = round(random.uniform(lo, hi), -1)
                            order_status = random.choice(ORDER_STATES)
                            if order_status == "in_lab":
                                act_cost = round(est_cost * random.uniform(0.85, 1.2), -1)
                                st = "done" if random.random() < 0.6 else st

                        done_at = "NOW()" if st == "done" else None
                        tid = await conn.fetchval(
                            """
                            INSERT INTO projects.tasks
                                (phase_id, project_id, title, assignee_user_id, status,
                                 start_on, due_on, baseline_due_on, proto_version,
                                 estimated_hours, cost_type, estimated_cost_czk,
                                 actual_cost_czk, order_status, position, created_by,
                                 done_at)
                            VALUES ($1,$2,$3,$4,$5::text,$6,$7,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                                    CASE WHEN $5::text = 'done' THEN NOW() END)
                            RETURNING id
                            """,
                            phase_id, proj_id, title, assignee, st, s_on, d_on, proto,
                            est_h, cost_type, est_cost, act_cost, order_status, pos, lead,
                        )
                        created.append(tid)
                        n_tasks += 1

                        # spolupracovníci
                        if random.random() < 0.25:
                            others = [u["id"] for u in random.sample(users, k=min(2, len(users)))
                                      if u["id"] != assignee]
                            for uid in others:
                                await conn.execute(
                                    "INSERT INTO projects.task_collaborators (task_id, user_id) "
                                    "VALUES ($1,$2) ON CONFLICT DO NOTHING", tid, uid)

                        # měřený čas u rozdělané / hotové práce
                        if st in ("in_progress", "design_review", "done") and random.random() < 0.8:
                            for _ in range(random.randint(1, 3)):
                                mins = random.choice([25, 45, 60, 90, 120, 180, 240])
                                s_at = dt.datetime.combine(
                                    s_on + dt.timedelta(days=random.randint(0, 6)),
                                    dt.time(hour=random.randint(8, 15)))
                                await conn.execute(
                                    """
                                    INSERT INTO projects.time_entries
                                        (task_id, user_id, started_at, ended_at, minutes, source, note)
                                    VALUES ($1,$2,$3,$4,$5,'manual','demo')
                                    """,
                                    tid, assignee or lead, s_at,
                                    s_at + dt.timedelta(minutes=mins), mins)
                                n_time += 1
                    by_phase_tasks.append(created)

                # závislost: úkol z fáze 4 závisí na úkolu z fáze 3
                if by_phase_tasks[3] and by_phase_tasks[2]:
                    await conn.execute(
                        "INSERT INTO projects.task_dependencies (task_id, depends_on_task_id) "
                        "VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        random.choice(by_phase_tasks[3]), random.choice(by_phase_tasks[2]))
                    n_dep += 1

            # --- 3 čekající návrhy od AI ---
            some_proj = await conn.fetch(
                "SELECT id, name, planned_budget_czk FROM projects.projects "
                "WHERE planned_budget_czk IS NOT NULL ORDER BY id LIMIT 2")
            some_task = await conn.fetchrow(
                "SELECT id, title FROM projects.tasks WHERE status = 'backlog' ORDER BY id LIMIT 1")
            actor = leads[0]["id"]
            proposals = []
            if some_proj:
                p = some_proj[0]
                proposals.append((
                    "finance.update", "project", p["id"],
                    {"planned_budget_czk": float(p["planned_budget_czk"]) * 1.35},
                    f"Navýšit rozpočet projektu {p['name']} o 35 % kvůli iteraci Proto-V2."))
            if len(some_proj) > 1:
                p = some_proj[1]
                proposals.append((
                    "project.lifecycle", "project", p["id"], {"status": "on_hold"},
                    f"Pozastavit projekt {p['name']} – čeká se na dodávku součástek."))
            if some_task:
                proposals.append((
                    "task.delete", "task", some_task["id"], {},
                    f"Smazat duplicitní úkol: {some_task['title']}."))

            for kind_, ttype, tid_, payload, summary in proposals:
                await conn.execute(
                    """
                    INSERT INTO projects.proposals
                        (requested_by_user_id, origin, kind, target_type, target_id,
                         payload, summary, status)
                    VALUES ($1,'mcp',$2,$3,$4,$5::jsonb,$6,'pending')
                    """,
                    actor, kind_, ttype, tid_,
                    json.dumps(payload, ensure_ascii=False), summary)

    print(f"Seed OK: {len(PROJECTS)} projektů, {n_tasks} úkolů, {n_time} záznamů času, "
          f"{n_dep} závislostí, {len(proposals)} návrhů AI.")
    print("Otevři /app/projects/ (login admin/admin).")
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
