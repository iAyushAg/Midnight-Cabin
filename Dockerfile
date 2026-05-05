FROM jrottenberg/ffmpeg:4.4-ubuntu2004

USER root

RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    curl \
    bc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "worker.sh"]