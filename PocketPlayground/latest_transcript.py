"""Print the most recently completed (transcribed) Pocket recording.

    python PocketPlayground/latest_transcript.py

Needs POCKET_API_KEY in PocketPlayground/.env (see .env.example).
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(Path(__file__).parent / ".env")

from ailacore import pocket  # noqa: E402 (must import after load_dotenv)


async def main() -> None:
    listing = await pocket.list_recordings(limit=20)
    completed = [r for r in listing["data"] if r["state"] == "completed"]
    if not completed:
        print("Žádná přepsaná nahrávka nenalezena.")
        return

    latest = completed[0]
    detail = await pocket.get_recording(
        latest["id"], include_transcript=True, include_summarizations=False
    )
    recording = detail["data"]

    print(f"{recording['title']} ({recording['recording_at']})")
    print("-" * 60)
    for segment in recording["transcript"]["segments"]:
        print(f"{segment['speaker']}: {segment['text']}")


if __name__ == "__main__":
    asyncio.run(main())
