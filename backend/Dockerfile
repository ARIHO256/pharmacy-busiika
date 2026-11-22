FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 mydoctor
COPY --chown=mydoctor:mydoctor . .
RUN mkdir -p /app/private-media /app/media /app/staticfiles && chown -R mydoctor:mydoctor /app
USER mydoctor
EXPOSE 4000
CMD ["daphne", "-b", "0.0.0.0", "-p", "4000", "config.asgi:application"]
