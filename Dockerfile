FROM python:3.12-slim

# Install supercronic for cron scheduling (auto-detect arch)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && ARCH=$(dpkg --print-architecture) \
    && curl -fsSLO "https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-${ARCH}" \
    && chmod +x "supercronic-linux-${ARCH}" \
    && mv "supercronic-linux-${ARCH}" /usr/local/bin/supercronic \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Asia/Taipei
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY main.py .
COPY src/ src/

# Create data directory
RUN mkdir -p /app/data

# Cron schedule: 08:00 Taipei daily (container TZ=Asia/Taipei)
RUN echo "0 8 * * * /usr/local/bin/python /app/main.py run" > /app/crontab

# Default: run cron scheduler
CMD ["supercronic", "/app/crontab"]
