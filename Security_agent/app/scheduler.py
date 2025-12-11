from apscheduler.schedulers.blocking import BlockingScheduler
from agent import OllamaReactAgent

agent = OllamaReactAgent()
scheduler = BlockingScheduler()


# -------------------------------------------------------
# ČTVRTEK 12:00 — týdenní report pro učitele
# -------------------------------------------------------
def teacher_weekly_job():
    messages = [{
        "role": "user",
        "content": """
        Najdi všechny uvolněné studenty v příštím týdnu.
        Seskup je podle učitele.
        Pro každého učitele vytvoř e-mail pomocí toolu
        generate_weekly_report.
        Každý email odešli pomocí toolu send_email.
        """
    }]
    agent.run(messages)


# -------------------------------------------------------
# PÁTEK 12:00 — přehled pro studenty o stavu
# -------------------------------------------------------
def student_status_job():
    messages = [{
        "role": "user",
        "content": """
        Najdi všechny žádosti studentů o uvolnění
        na další týden, včetně schválení a zamítnutí.
        Seskup je podle studenta.
        Vygeneruj email pomocí generate_student_status_email
        a odešli pomocí send_email každému studentovi.
        """
    }]
    agent.run(messages)


def start_scheduler():
    
    # Výuka učitelům každý čtvrtek 12:00
    scheduler.add_job(send_teacher_reports, 'cron', day_of_week='thu', hour=12, minute=0)

    # Výuka studentům každý pátek 12:00
    scheduler.add_job(send_student_updates, 'cron', day_of_week='fri', hour=12, minute=0)

    scheduler.start()

    print("Scheduler started!")

    # Scheduler potřebuje nekonečnou smyčku JEN když je volaný samostatně
    while True:
        time.sleep(1)
