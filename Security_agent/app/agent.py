from typing import List, Dict, Any
from ollama import chat
import json

from tools import (
    db_query, send_email, generate_weekly_report,
    generate_student_status_email, process_teacher_reply
)


tools = {
    "db_query": {"function": db_query},
    "send_email": {"function": send_email},
    "generate_weekly_report": {"function": generate_weekly_report},
    "generate_student_status_email": {"function": generate_student_status_email},
    "process_teacher_reply": {"function": process_teacher_reply},
}

available_functions = {
    "db_query": db_query,
    "send_email": send_email,
    "generate_weekly_report": generate_weekly_report,
    "generate_student_status_email": generate_student_status_email,
    "process_teacher_reply": process_teacher_reply,
}


class OllamaReactAgent:
    def __init__(self, model="llama3.2"):
        self.model = model
        self.max_iterations = 10

    def run(self, messages: List[Dict[str, Any]]) -> str:
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            response = chat(
                self.model,
                messages=messages,
                tools=tools
            )

            # TOOL CALL
            if response.message.tool_calls:
                messages.append(response.message)

                for call in response.message.tool_calls:
                    fn = available_functions[call.function.name]
                    args = call.function.arguments
                    result = fn(**args)

                    messages.append({
                        "role": "tool",
                        "name": call.function.name,
                        "content": json.dumps(result),
                    })

                continue

            # FINAL ANSWER
            else:
                messages.append(response.message)
                return response.message.content

        return "ERROR: Too many iterations"
