# Base image (slim for faster docker file)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# going to the directory
WORKDIR /app

# setting up the dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# copying the requirements.txt file first \
COPY requirements.txt .
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

ARG DEV=0
RUN if [ "$DEV" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# create a non-root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser \
    && useradd -m -u ${UID} -g ${GID} appuser \
    && chown -R appuser:appuser /app

USER appuser

# copying the project code \
COPY . .

# Expose the port here
EXPOSE 8000


# default command when the container starts
# runs gunicorn in production
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
