FROM python:3.12-slim

WORKDIR /app

# Set timezone
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies & Cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    zlib1g-dev \
    cron \
    vim \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (optional - only needed for estate/damai crawling)
# Uncomment if you need Playwright:
# RUN pip install playwright && playwright install chromium --with-deps

# Copy source
COPY . .
RUN chmod +x /app/scripts/docker_entrypoint.sh

# Cron is now managed by Ofelia labels in docker-compose.yml
# No need to copy crontab.txt here

# Entrypoint
# Entrypoint
# scripts/docker_entrypoint.sh is already copied in COPY . .
ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]
