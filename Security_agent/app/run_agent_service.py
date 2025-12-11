import threading
import time
from flask import Flask, request, jsonify

from agent import run_agent
from scheduler import start_scheduler


# ==============================
# Flask server pro příjem příkazů
# ==============================
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


# ===========================================
# Vlastní thread na Scheduler (důležité!)
# ===========================================
def scheduler_thread():
    print("Scheduler thread started…")
    start_scheduler()  # funkce z scheduler.py
    # běží asynchronně a nikdy se neukončí


# ===========================================
# Hlavní spuštění: Server + Scheduler
# ===========================================
if __name__ == "__main__":
    print("Starting DuklaLabs Agent Service…")

    # SPUŠŤÍME SCHULENDER PARALELNĚ
    thread = threading.Thread(target=scheduler_thread, daemon=True)
    thread.start()

    # SPUŠŤÍME AGENT SERVER NA PORTU 8004
    app.run(host="0.0.0.0", port=8004)
