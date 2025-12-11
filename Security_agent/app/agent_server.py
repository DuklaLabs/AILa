from flask import Flask, request, jsonify
from agent import run_agent

app = Flask(__name__)

@app.post("/run")
def run():
    data = request.json
    
    email = data.get("email")
    hour = data.get("hour_id")

    user_message = {
        "role": "user",
        "content": f"Uvolni studenta s emailem {email} na hodinu ID {hour}."
    }

    result = run_agent(user_message)
    return jsonify(result)

if __name__ == "__main__":
    # DŮLEŽITÉ ⇒ BĚŽ NA PORTU 8004
    app.run(host="0.0.0.0", port=8004)
