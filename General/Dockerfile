FROM python:3.11-slim

WORKDIR /app

# systémové závislosti (když budeš chtít Postgres apod.)
RUN apt-get update && apt-get install -y build-essential && apt-get clean

# requirements.txt předpokládám v General/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# zbytek kódu
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]