FROM python:3.11-slim

# ffmpeg is required by yt-dlp to merge separate audio/video streams
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN mkdir -p /app/downloads

CMD ["python", "bot.py"]
