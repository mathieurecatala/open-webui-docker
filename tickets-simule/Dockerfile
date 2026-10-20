# Service simulé de tickets de support (GET /tickets, GET /health).
# Bibliothèque standard Python uniquement : rien à installer.
FROM python:3.12.15-slim
RUN useradd --uid 10001 --no-create-home tickets
WORKDIR /app
COPY serveur.py .
USER tickets
EXPOSE 8000
CMD ["python", "serveur.py"]
