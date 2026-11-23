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
- `GET /api/v1/organizations` et `POST /api/v1/organizations` : liste et création via RLS/RPC Supabase avec le bearer token utilisateur vérifié.
- `GET/PATCH /api/v1/organizations/{organization_id}` : consultation et modification filtrées côté serveur et côté RLS.
- `GET/POST /api/v1/organizations/{organization_id}/members` : lecture et ajout contrôlés par rôle.
- `PATCH/DELETE /api/v1/organizations/{organization_id}/members/{user_id}` : modification ou retrait contrôlés par rôle.
- `POST /api/v1/organizations/{organization_id}/members/transfer-ownership` : transfert réservé au propriétaire.
- `GET /docs` : documentation OpenAPI FastAPI.

La validation JWT Supabase est serveur uniquement. Aucun JWT n’est accepté parce qu’il est simplement décodable : signature, `exp`, `sub`, `iss`, `aud` et algorithme autorisé sont vérifiés.

## Configuration

Copier `.env.example` vers `.env` et renseigner les variables dans l’environnement d’exécution. Ne jamais commiter `.env`, les clés Supabase, les clés privées ou les tokens.

Les tests unitaires utilisent des clés et des réponses JWKS générées en mémoire. Ils ne prétendent pas valider une instance Supabase distante.

Le client Supabase REST est serveur uniquement. `SUPABASE_ANON_KEY` est utilisé avec le JWT de l’utilisateur pour conserver les politiques RLS; `SUPABASE_SERVICE_ROLE_KEY`, lorsqu’elle sera configurée, est réservée aux opérations administratives et n’est jamais renvoyée au frontend.
