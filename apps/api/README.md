# OpenHands SaaS API

Backend FastAPI indépendant, versionné sous `/api/v1`. Il ne remplace pas le frontend Agent Canvas existant.

## Développement local

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Endpoints sans compte externe :

- `GET /api/v1/health` : vérifie que le processus répond.
- `GET /api/v1/ready` : expose l’état de configuration des dépendances et renvoie `503` tant que les dépendances requises ne sont pas configurées.
- `GET /docs` : documentation OpenAPI FastAPI.

La validation JWT Supabase est serveur uniquement. Aucun JWT n’est accepté parce qu’il est simplement décodable : signature, `exp`, `sub`, `iss`, `aud` et algorithme autorisé sont vérifiés.

## Configuration

Copier `.env.example` vers `.env` et renseigner les variables dans l’environnement d’exécution. Ne jamais commiter `.env`, les clés Supabase, les clés privées ou les tokens.

Les tests unitaires utilisent des clés et des réponses JWKS générées en mémoire. Ils ne prétendent pas valider une instance Supabase distante.
