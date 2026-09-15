import json

import httpx
from ailacore.llm import complete

from app.agents.inventory import get_low_stock
from app.agents.messenger import send_email
from app.agents.procurement import create_order_from_low_stock
from app.agents.students import active_student_emails
from app.history import load_history, save_message

SYSTEM_PROMPT = """Jsi *Generál*, hlavní orchestrátor laboratoře DuklaLabs – přátelský
asistent, co s uživatelem mluví volně česky o čemkoli (odpovídej na otázky,
pokecej, poraď).

Navíc umíš spustit tyhle konkrétní akce, když o ně uživatel jasně žádá:
- CHECK_STOCK    → zkontrolovat skladové zásoby materiálu
- CREATE_ORDER   → vytvořit objednávku chybějícího materiálu
- DRAFT_EMAIL    → připravit návrh e-mailového oznámení studentům DuklaLabs
                   (vyplň "subject" a "body"). NIKDY e-mail neodešli rovnou –
                   vždy nejdřív jen ukaž návrh a počkej na výslovné potvrzení.
                   Jinou cílovou skupinu než "studenti DuklaLabs" zatím
                   neumíš – pokud o ni uživatel požádá, v "reply" to
                   zdvořile vysvětli a DRAFT_EMAIL nepoužívej.
- CONFIRM_SEND   → uživatel právě potvrdil odeslání dříve navrženého
                   e-mailu. Tuhle akci vracej JEN když v konverzaci vidíš
                   nevyřízený návrh (dole je na to upozornění) a uživatel ho
                   zjevně potvrzuje (např. "ano, pošli to", "odešli").
- CANCEL_DRAFT   → uživatel nevyřízený návrh zrušil / nechce pokračovat.

Odpověz VÝHRADNĚ JSON objektem (žádný text ani markdown blok okolo):
{"action": "CHECK_STOCK" | "CREATE_ORDER" | "DRAFT_EMAIL" | "CONFIRM_SEND" | "CANCEL_DRAFT" | "CHAT", "reply": "<tvoje odpověď uživateli>", "subject": "<jen u DRAFT_EMAIL>", "body": "<jen u DRAFT_EMAIL>"}

"action" je "CHAT" vždy, když nejde jasně o žádnou z ostatních akcí – pak je
"reply" normální konverzační odpověď na to, co uživatel napsal. U
CHECK_STOCK/CREATE_ORDER/CONFIRM_SEND napiš do "reply" krátké potvrzení
(výsledek akce se k tvé odpovědi připojí automaticky). U DRAFT_EMAIL napiš
do "reply" jen krátký úvod (např. "Připravil jsem návrh:") – samotný
předmět/text e-mailu a příjemce zobrazí systém sám z "subject"/"body"."""


def _parse_action(raw: str) -> dict:
    """Some chat models wrap JSON in a markdown code fence even with
    response_format=json_object. If parsing still fails, treat the whole
    reply as free-form chat text instead of erroring out – a badly
    formatted answer shouldn't break the conversation."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        data = None
    if not isinstance(data, dict) or "reply" not in data:
        return {"action": "CHAT", "reply": raw.strip()}
    return data


def _format_history(history: list[dict]) -> str:
    lines = []
    for m in history:
        speaker = "Uživatel" if m.get("from") == "user" else "Generál"
        text = (m.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def _pending_draft(history: list[dict]) -> dict | None:
    """Poslední zpráva od Generála v historii nese nevyřízený návrh e-mailu
    v `data.pending_email`, dokud ho neschválí/nezruší nebo dokud Generál
    neodpoví něčím jiným (i jen CHAT) – pak přirozeně "vyprchá", žádný
    zvláštní úklid není potřeba."""
    for m in reversed(history):
        if m.get("from") == "agent":
            data = m.get("data")
            if isinstance(data, dict) and "pending_email" in data:
                return data["pending_email"]
            return None
    return None


async def run_general_command(user_id: int, user_input: str) -> dict:
    # Historie žije v general.chat_messages (per uživatel), ne v tom, co
    # pošle klient – ať konverzace přežije i přihlášení z jiného zařízení.
    history = await load_history(user_id)
    pending = _pending_draft(history)
    transcript = _format_history(history)
    if pending:
        transcript += f"\n[Systém: čeká nevyřízený návrh e-mailu – předmět: {pending['subject']!r}]"
    prompt = f"{transcript}\nUživatel: {user_input}" if transcript else user_input

    # sensitive=False: běžný chat o laborce, dotazy na sklad/objednávky ani
    # návrhy oznámení studentům nenesou osobní údaje.
    raw = await complete(prompt, sensitive=False, system=SYSTEM_PROMPT, json_mode=True)
    parsed = _parse_action(raw)
    action = str(parsed.get("action", "CHAT")).strip().upper()
    reply = (parsed.get("reply") or "").strip() or "Nejsem si jistý, jak na to reagovat."
    print(f"[General] user={user_id} prompt={user_input!r} -> action={action!r}", flush=True)

    await save_message(user_id, "user", user_input)

    data = None
    if action == "CHECK_STOCK":
        try:
            data = await get_low_stock()
        except httpx.HTTPError as e:
            reply = f"{reply}\n\n(Nepodařilo se spojit se skladem: {e})"
    elif action == "CREATE_ORDER":
        try:
            data = await create_order_from_low_stock()
        except httpx.HTTPError as e:
            reply = f"{reply}\n\n(Nepodařilo se spojit s nákupčím: {e})"
    elif action == "DRAFT_EMAIL":
        subject = (parsed.get("subject") or "").strip() or "(bez předmětu)"
        body = (parsed.get("body") or "").strip()
        recipients = await active_student_emails()
        data = {"pending_email": {"subject": subject, "body": body, "to": recipients}}
        reply = f"{reply}\n\nPředmět: {subject}\n{body}\n\nPříjemci: {len(recipients)} aktivních studentů."
    elif action == "CONFIRM_SEND":
        if not pending:
            reply = "Nemám žádný rozpracovaný návrh e-mailu k odeslání."
        else:
            try:
                await send_email(pending["to"], pending["subject"], pending["body"])
                reply = f"{reply}\n\nOdesláno {len(pending['to'])} příjemcům."
            except httpx.HTTPError as e:
                reply = f"{reply}\n\n(Nepodařilo se odeslat e-mail: {e})"

    await save_message(user_id, "agent", reply, data)
    return {"reply": reply, "data": data} if data is not None else {"reply": reply}
