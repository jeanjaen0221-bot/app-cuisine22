# Consignes pour Claude

- Quand un travail est terminé (tests passés, commit poussé), toujours le
  fusionner dans `main` : ouvrir la pull request puis la fusionner, sans attendre
  de demande. Ne fusionner que du travail terminé et vérifié.
- Tests du backend : `python -m pytest app/backend/tests`.
- Build du frontend : `cd app/frontend && npx tsc -b && npx vite build`.
