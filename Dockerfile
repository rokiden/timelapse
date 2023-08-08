FROM python:3.9

WORKDIR /app
VOLUME /data

#RUN apt-get update && apt-get install -y python3-opencv ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py", "/data"]
