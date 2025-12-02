from app.llm import ask_model
from app.agents.inventory import get_low_stock
from app.agents.procurement import create_order_from_low_stock


SYSTEM_PROMPT = """
Jsi *Generál*, hlavní orchestrátor laboratoře DuklaLabs.

Mluvíš výhradně česky.

Tvým úkolem je pochopit, co uživatel chce, a přeložit to do jedné
z těchto vnitřních akcí:

- CHECK_STOCK  → zkontrolovat skladové zásoby (volá skladníka)
- CREATE_ORDER → vytvořit objednávku (volá nákupčího)
- UNKNOWN      → pokud nevíš

Odpověz pouze samotným názvem akce. Nic jiného!
"""

INVENTORY_URL = "http://skladnik:8001"
PROCUREMENT_URL = "http://nakupcik:8002"


async def run_general_command(user_input: str):

    intent = await ask_model(f"""
{SYSTEM_PROMPT}

Uživatel říká:
{user_input}
""")

    intent = intent.strip().upper()

    if "CHECK_STOCK" in intent:
        return await get_low_stock()

    if "CREATE_ORDER" in intent:
        return await create_order_from_low_stock()

    return {"chyba": "Nerozumím příkazu", "detaily": intent}
