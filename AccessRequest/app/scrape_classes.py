import os
import aiohttp
import asyncio
from pathlib import Path
from bs4 import BeautifulSoup
import orjson
import locale
import time
import re
import datetime
import psycopg2

# ---------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------
DB = psycopg2.connect(
    host="localhost",
    database="DL_access_manager",
    user="postgres",
    password="heslo"
)

DAY_MAP = {
    "po": "Pondělí",
    "út": "Úterý",
    "st": "Středa",
    "čt": "Čtvrtek",
    "pá": "Pátek"
}

# ---------------------------------------------------------
# Extract date from subject text
# ---------------------------------------------------------
def extract_date(subjecttext):
    # Example: "Matematika | po 15.12. | 3 (9:55 - 10:40)"
    part = subjecttext.split("|")[1].strip()  # "po 15.12."
    raw_date = part.split(" ")[1].replace(".", "")  # "15.12."
    day, month = map(int, raw_date.split("."))

    today = datetime.date.today()
    year = today.year if month < 9 else today.year - 1

    return datetime.date(year, month, day)

# ---------------------------------------------------------
# Insert lesson into DB
# ---------------------------------------------------------
def insert_lesson(class_name, subjecttext, teacher, hour_number):
    weekday_raw = subjecttext.split("|")[1].strip().split(" ")[0]
    weekday = DAY_MAP.get(weekday_raw, weekday_raw)
    subject_name = subjecttext.split("|")[0].strip()

    lesson_date = extract_date(subjecttext)

    cur = DB.cursor()
    cur.execute("""
        INSERT INTO internal.lesson_hours
            (weekday, class_name, subject_name, teacher_name, hour_number, lesson_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
    """, (weekday, class_name, subject_name, teacher, hour_number, lesson_date))

    DB.commit()
    cur.close()

# ---------------------------------------------------------
# LESSON PARSER
# ---------------------------------------------------------
def process_lessons_html(class_name, html):
    soup = BeautifulSoup(html, "lxml")
    hours = soup.find_all("div", class_="bk-timetable-cell")

    hour_index = 0

    for hour in hours:
        cells = hour.find_all("div", class_="day-item-hover")

        for cell in cells:
            detail_raw = cell.get("data-detail")
            if not detail_raw:
                continue

            detail = orjson.loads(detail_raw.encode("utf-8"))
            if detail.get("type") != "atom":
                continue

            subjecttext = detail["subjecttext"]
            teacher = detail["teacher"]

            # Extract hour number
            match = re.search(r"\|\s*\w+\s+\d+\.\d+\.\s*\|\s*(\d+)", subjecttext)
            hour_number = int(match.group(1)) if match else hour_index

            insert_lesson(class_name, subjecttext, teacher, hour_number)

        hour_index += 1

# ---------------------------------------------------------
# FETCH helpers
# ---------------------------------------------------------
SEMAPHORE = asyncio.Semaphore(50)

async def fetch(url, session):
    async with SEMAPHORE:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()

# ---------------------------------------------------------
# Extract class list
# ---------------------------------------------------------
def extract_classes(html):
    soup = BeautifulSoup(html, "lxml")
    links = (
        soup.find("div", {"id": "class_canvas"})
            .find("div", class_="bk-canvas-body")
            .find_all("a")
    )

    result = []
    for link in links:
        name = link.text.strip()
        result.append({
            name: { 
                "Next": link["href"].replace("Actual", "Next").replace("/bakaweb/timetable/public/", "")
            }
        })

    locale.setlocale(locale.LC_COLLATE, "cs_CZ.UTF-8")
    return sorted(result, key=lambda x: locale.strxfrm(list(x.keys())[0]))

# ---------------------------------------------------------
# PROCESS CLASS TIMETABLE (Actual + Next)
# ---------------------------------------------------------
async def process_class(name, urls, session):
    base = "https://bakalari.spssecb.cz/bakaweb/Timetable/Public/"

    for key, path in urls.items():
        url = base + path
        print(f"[SCRAPE] {name} → {key}")

        try:
            html = await fetch(url, session)
            process_lessons_html(name, html)

            print(f"[OK] {name}: {key}")

        except Exception as e:
            print(f"[ERR] {name} {key}: {e}")

# ---------------------------------------------------------
# MAIN SCRAPER
# ---------------------------------------------------------
async def scrape_classes():
    MAIN_URL = "https://bakalari.spssecb.cz/bakaweb/Timetable/Public/"

    async with aiohttp.ClientSession() as session:
        print("[INFO] Fetching class list…")
        html = await fetch(MAIN_URL, session)

        CLASSES = extract_classes(html)
        print(f"[INFO] Found {len(CLASSES)} classes.")

        # SCRAPE ALL CLASSES
        tasks = []
        for obj in CLASSES:
            name = list(obj.keys())[0]
            urls = obj[name]
            tasks.append(process_class(name, urls, session))

        await asyncio.gather(*tasks)

    print("[DONE] All classes updated directly into DB.")


