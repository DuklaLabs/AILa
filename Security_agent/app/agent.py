import json
import requests
from typing import List, Dict, Any
from ollama import chat, ChatResponse


from tools import (
    db_query,
    send_email,
    generate_weekly_report,
    generate_student_status_email,
    process_teacher_reply
)

# =====================================================
# 1) Deklarace nástrojů (v češtině)
# =====================================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "db_query",
            "description": "Proveď SQL dotaz nad interní databází.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Odešli e-mail pomocí SMTP serveru.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_weekly_report",
            "description": "Vytvoř text týdenního reportu pro učitele ze seznamu hodin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "teacher_name": {"type": "string"},
                    "lessons": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["teacher_name", "lessons"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_student_status_email",
            "description": "Vytvoř informační e-mail pro studenta o stavu jeho žádostí.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "lessons": {"type": "array", "items": {"type": "object"}}
                },
                "required": ["first_name", "last_name", "lessons"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_teacher_reply",
            "description": "Zpracuj odpověď učitele. Pokud obsahuje NESOUHLASÍM, zamítni uvolnění studentů.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_body": {"type": "string"}
                },
                "required": ["email_body"]
            }
        }
    }
]

# Mapa toolů → Python funkcí
available_functions = {
    "db_query": db_query,
    "send_email": send_email,
    "generate_weekly_report": generate_weekly_report,
    "generate_student_status_email": generate_student_status_email,
    "process_teacher_reply": process_teacher_reply,
}
# =======================================
#             ReAct Agent
# =======================================
class OllamaReactAgent:
    def __init__(self, model: str = "llama3.2:8b-instruct"):
        self.model = model
        self.max_iterations = 10

    def run(self, messages: List[Dict[str, Any]]) -> str:

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n=== Iterace {iteration} ===")

            response: ChatResponse = chat(
                model=self.model,
                messages=messages,
                tools=tools,     # OLLAMA AUTOMATICKY SIGNÁLUJE tool_calls
                stream=False
            )

            print("LLM odpověď:", response.message)
            print("Tool calls:", response.message.tool_calls)
            print("tools_calls RAW:", response.tools)
            # ======== POKUD MODEL CHCE ZAVOLAT FUNKCI ========
            if response.message.tool_calls:
                messages.append(response.message)

                for call in response.message.tool_calls:
                    fn_name = call.function.name
                    fn_args = call.function.arguments
                    print(f"Volám tool: {fn_name}({fn_args})")

                    if fn_name not in available_functions:
                        raise Exception(f"Funkce {fn_name} neexistuje v agentovi!")

                    result = available_functions[fn_name](**fn_args)

                    messages.append({
                        "role": "tool",
                        "name": fn_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

                continue

            # ======== KONEČNÁ ODPOVĚĎ ========
            final = response.message.content
            messages.append(response.message)
            return final

        return "ERROR: Vyčerpány iterace"


# =======================================
#  API VOLÁNÍ PRO FASTAPI / FLASK
# =======================================
def run_agent(user_message: Dict[str, Any]):
    system_prompt = {
    "role": "system",
    "content": """
Jsi DuklaLabs Access Agent.

DŮLEŽITÉ POKYNY PRO TVOJI PRÁCI:

1. Pokud potřebuješ zavolat funkci, MUSÍŠ použít formát Ollama tool_calls:
   {
     "tool_calls": [
       {
         "function": {
           "name": "function_name",
           "arguments": { ... }
         }
       }
     ]
   }

2. NESMÍŠ psát žádné jiné formáty jako:
   - <tool_call>...</tool_call>
   - text smíchaný s JSON
   - plain JSON bez "tool_calls"

3. Pokud voláš více funkcí, udělej více položek v "tool_calls".

4. Jakmile máš hotové všechny tool calls, vrať jen běžný text bez dalších požadavků.

5. Nepiš nic okolo JSONu, žádné vysvětlování.

Máš povoleny tyto funkce:
- db_query
- send_email
- generate_weekly_report
- generate_student_status_email
- process_teacher_reply

Tvým úkolem je:
- ověřit studenta
- ověřit hodinu
- zapsat žádost do DB
- poslat email učiteli
- poslat email studentovi o výsledku
"""
}


    messages = [system_prompt, user_message]

    agent = OllamaReactAgent()
    return agent.run(messages)