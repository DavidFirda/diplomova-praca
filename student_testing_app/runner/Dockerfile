FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /runner
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py executor.py ./

RUN useradd -m -u 10001 runneruser
USER runneruser

ENV MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 6000

CMD ["gunicorn", "-b", "0.0.0.0:6000", "-w", "2", "-k", "gthread", "--threads", "4", "--timeout", "120", "app:app"]
