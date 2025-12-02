import psycopg2
import psycopg2.extensions
import json
import time
import requests
import os
import select

DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST")
WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

while True:
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("LISTEN errors_channel;")
        print("Listening on errors_channel...")

        while True:
            if select.select([conn], [], [], None):
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    payload = json.loads(notify.payload)
                    print("Received:", payload)
                    requests.post(WEBHOOK_URL, json=payload)

    except Exception as e:
        print("Listener crashed:", e)
        time.sleep(3)
