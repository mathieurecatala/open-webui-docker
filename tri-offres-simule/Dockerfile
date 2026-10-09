# Service simulé qui reprend le contrat de l'API tri-offres (GET /offres, GET /health).
# Bibliothèque standard Python uniquement : rien à installer.
FROM python:3.12.15-slim
RUN useradd --uid 10001 --no-create-home tri
WORKDIR /app
COPY serveur.py .
USER tri
EXPOSE 8000
CMD ["python", "serveur.py"]
