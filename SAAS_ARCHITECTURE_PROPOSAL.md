# Proposition d’architecture — Plateforme IA SaaS basée sur OpenHands Agent Canvas

**Statut :** proposition soumise à validation — aucune modification importante du code applicatif n’est engagée.

## 1. Décision d’architecture

Conserver OpenHands Agent Canvas comme frontend principal et comme surface de travail agentique. Ajouter un **backend SaaS indépendant** devant les backends OpenHands/agent-server existants au lieu de réécrire le frontend ou de transformer le client en monolithe.

Architecture recommandée pour le MVP commercial : **monolithe modulaire FastAPI + workers asynchrones**, PostgreSQL, Redis et stockage S3-compatible. Les frontières de modules doivent être propres afin de pouvoir extraire plus tard l’AI Gateway, le billing ou le runner en services séparés si la charge l’exige.

Le backend SaaS devient l’autorité pour : identité, tenant, permissions, plans, entitlements, quotas, usage, facturation, fichiers et audit. Agent Canvas reste l’autorité d’interface et de session conversationnelle côté client, mais ne décide jamais seul de l’accès ou du coût.

## 2. Composants cibles

### Frontend

- OpenHands Agent Canvas existant, React/TypeScript.
- Ajout minimal de `SaaS API client`, contexte tenant, état subscription/entitlements et écrans pricing/billing/admin.
- Aucun secret fournisseur IA ou paiement dans le bundle navigateur.
- Les appels vers Agent Server passent par des credentials de session courts ou des tokens backend, jamais par des clés maîtres.

### Backend SaaS

- FastAPI REST versionnée `/api/v1`.
- WebSocket ou SSE pour événements de job et progression agent.
- Modules : `auth`, `tenants`, `rbac`, `billing`, `entitlements`, `usage`, `ai_gateway`, `agents`, `conversations`, `files`, `integrations`, `audit`.
- OPA légère par dépendances FastAPI : `current_user`, `current_membership`, `require_permission`, `require_entitlement`.
- Workers Celery/RQ/Arq sur Redis pour webhooks, embeddings, ingestion RAG, runs longs et notifications.

### Données

- PostgreSQL comme source durable.
- Redis pour rate limits, verrous, cache court et files ; jamais comme source unique de facturation.
- S3-compatible pour documents, pièces jointes, exports et artefacts volumineux.
- Alembic pour migrations versionnées.

### IA

- AI Gateway interne avec interface provider-neutral.
- Adaptateurs OpenAI-compatible, Anthropic, Google et providers self-hosted à ajouter progressivement.
- Routage par modèle, fallback explicite, budgets et tokens comptés au niveau gateway.
- Les modèles ne reçoivent que les données autorisées par le tenant et le run.
- Le runner OpenHands/agent-server reste isolé et reçoit des credentials à portée limitée.

### Paiement

- Stripe Billing en première implémentation.
- Checkout créé côté backend.
- Webhooks Stripe signés, idempotents, persistés dans `provider_events` avant traitement.
- Les droits sont calculés par abonnement et plan, puis matérialisés dans `entitlements`.
- Le frontend ne peut ni créer une entitlement ni augmenter une limite.

## 3. Flux critiques

### Inscription et tenant

1. L’utilisateur s’inscrit ou se connecte.
2. Le backend crée ou rejoint une organisation et une membership.
3. Un tenant courant est choisi via un token ou header validé côté serveur.
4. Chaque requête charge le tenant depuis la membership, jamais depuis un identifiant librement fourni.
5. Toutes les requêtes DB sont filtrées par `organization_id` et protégées par des contraintes/permissions.

### Lancement d’un run IA

1. Frontend demande `POST /api/v1/runs`.
2. Backend vérifie membership, permission, entitlement, quota disponible et limites de concurrence.
3. Backend crée `agent_runs` et réserve un budget.
4. Worker appelle l’AI Gateway/OpenHands avec un credential limité.
5. Les tokens, durée, provider, modèle et coût sont enregistrés dans `usage_events`.
6. Le run est clôturé atomiquement ; le quota est débité côté serveur.

### Paiement

1. Frontend demande une Checkout Session pour un `price_id` autorisé.
2. Backend crée la session Stripe avec `client_reference_id` tenant/user.
3. Stripe redirige vers Checkout.
4. Webhook signé reçu et écrit dans `provider_events` avec event id unique.
5. Worker applique idempotemment l’abonnement et les entitlements.
6. Le frontend relit l’état depuis `GET /api/v1/billing/subscription`.

### RAG

1. Upload présigné vers S3 après contrôle de taille/type.
2. Backend crée `files` et un job d’ingestion.
3. Worker extrait, nettoie, segmente et calcule les embeddings via provider configuré.
4. Les chunks/embeddings sont associés à l’organisation et aux ACL du fichier.
5. Retrieval filtre obligatoirement par tenant et visibilité avant insertion dans le contexte modèle.

## 4. Modèle relationnel initial

Tables minimales :

- `users(id, email, password_hash_or_identity, status, created_at, deleted_at)`
- `organizations(id, slug, name, plan_id, status, created_at)`
- `memberships(id, organization_id, user_id, role_id, status, created_at)`
- `roles(id, organization_id nullable, name)`
- `role_permissions(role_id, permission)`
- `sessions(id, user_id, organization_id, token_hash, expires_at, revoked_at)`
- `plans(id, provider, provider_product_id, code, active, limits_json)`
- `subscriptions(id, organization_id, provider, provider_subscription_id, plan_id, status, period_start, period_end, cancel_at)`
- `entitlements(id, organization_id, key, value_json, source_subscription_id, valid_from, valid_until)`
- `usage_events(id, organization_id, user_id, run_id, kind, quantity, unit, provider, model, cost_minor, occurred_at, idempotency_key)`
- `invoices(id, organization_id, provider_invoice_id, status, amount_minor, currency, hosted_url, issued_at, paid_at)`
- `provider_events(id, provider, provider_event_id, type, payload_json, received_at, processed_at, status, error)`
- `conversations(id, organization_id, owner_user_id, external_id, title, status, created_at)`
- `messages(id, conversation_id, role, content_ref, token_count, created_at)`
- `agents(id, organization_id, owner_user_id, name, config_json, status)`
- `agent_runs(id, organization_id, agent_id, conversation_id, status, budget_minor, started_at, finished_at, error_code)`
- `model_providers(id, organization_id nullable, provider, encrypted_config_ref, active)`
- `api_keys(id, organization_id, user_id, name, key_prefix, key_hash, scopes_json, expires_at, revoked_at)`
- `files(id, organization_id, owner_user_id, object_key, content_type, size_bytes, checksum, visibility, status)`
- `audit_logs(id, organization_id, actor_user_id, action, resource_type, resource_id, metadata_json, ip_hash, created_at)`

Contraintes indispensables :

- unique `(organization_id, slug)` ;
- unique `(provider, provider_event_id)` ;
- unique `(provider, provider_subscription_id)` ;
- unique `(organization_id, idempotency_key)` pour usage et opérations financières ;
- index sur toutes les FK tenant et colonnes de recherche temporelle ;
- aucun endpoint ne doit pouvoir lire une ligne sans filtre tenant ;
- RLS PostgreSQL à envisager dès la première version si l’équipe maîtrise son exploitation.

## 5. Contrats API MVP

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/password/forgot`
- `POST /api/v1/auth/password/reset`
- `GET /api/v1/me`

### Organisations et droits

- `GET /api/v1/organizations`
- `POST /api/v1/organizations`
- `GET /api/v1/organizations/{org_id}`
- `GET /api/v1/organizations/{org_id}/members`
- `POST /api/v1/organizations/{org_id}/invitations`
- `PATCH /api/v1/organizations/{org_id}/members/{member_id}`

### Billing

- `GET /api/v1/billing/plans`
- `GET /api/v1/billing/subscription`
- `POST /api/v1/billing/checkout-session`
- `POST /api/v1/billing/portal-session`
- `GET /api/v1/billing/invoices`
- `POST /api/v1/webhooks/stripe`

### Entitlements et usage

- `GET /api/v1/entitlements`
- `GET /api/v1/usage?from=&to=`
- `GET /api/v1/usage/limits`

### Agents et runs

- `GET/POST /api/v1/agents`
- `GET/PATCH/DELETE /api/v1/agents/{agent_id}`
- `POST /api/v1/agents/{agent_id}/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/cancel`
- `GET /api/v1/runs/{run_id}/events` ou WebSocket équivalent

### Fichiers/RAG

- `POST /api/v1/files/presign`
- `POST /api/v1/files/{file_id}/ingest`
- `GET /api/v1/files`
- `DELETE /api/v1/files/{file_id}`
- `POST /api/v1/search`

Toutes les mutations sensibles acceptent une clé d’idempotence et renvoient un identifiant de corrélation.

## 6. Sécurité

- Cookies HttpOnly Secure SameSite adapté ou tokens courts en mémoire ; refresh rotationné et révocable.
- Hash de mots de passe Argon2id ; MFA et OAuth à ajouter après le chemin email sécurisé.
- RBAC par organisation, vérification d’objet et scopes API.
- Secrets fournisseurs chiffrés avec KMS/envelope encryption ; aucune clé brute en DB ou frontend.
- Rate limiting Redis par IP, utilisateur, organisation et endpoint coûteux.
- Validation stricte Pydantic, limites de taille, content-type allowlist.
- SSRF : egress allowlist/proxy pour URLs distantes, blocage metadata endpoints et résolution DNS contrôlée.
- Sandbox agent par conteneur/VM, filesystem limité, réseau sortant contrôlé et timeout.
- Webhooks : signature, timestamp tolerance, body brut conservé, idempotence et replay protection.
- Logs sans secrets ni prompts sensibles par défaut ; audit des opérations admin/billing.
- Backups chiffrés, restauration testée et séparation des environnements.

## 7. Tests et critères de sortie

### CI obligatoire

- lint, typecheck hermétique, unit tests, coverage seuil ;
- migrations up/down sur DB éphémère ;
- tests contractuels API/OpenAPI ;
- SAST, dependency audit, secret scan, container scan ;
- build frontend et image ;
- smoke `/health`, `/ready`, login et webhook test ;
- E2E paiement Stripe test mode.

### Tests de sécurité

- tenant A ne lit ni ne modifie aucune ressource tenant B ;
- rôle membre/admin/owner vérifié sur chaque mutation ;
- replay et signature webhook ;
- dépassement de quota concurrent ;
- abus de tokens, upload, URL et run ;
- SSRF localhost/metadata/private ranges ;
- révocation de session et rotation refresh ;
- restauration backup vers environnement isolé.

### Charge initiale

Cibler d’abord 100 utilisateurs concurrents, puis 1 000 avant l’ouverture publique. Mesurer p95 API, démarrage run, latence streaming, saturation workers, consommation tokens, coûts et erreurs provider.

## 8. Structure de dépôt proposée

```text
apps/
  canvas/                 # frontend OpenHands conservé/adapté minimalement
  api/                    # FastAPI SaaS
  worker/                 # jobs asynchrones
packages/
  api-client/             # client TypeScript généré/typé
  contracts/              # schémas OpenAPI/JSON
  entitlements/           # types et règles partagées non secrètes
services/
  ai-gateway/
  agent-runner/
infra/
  docker/
  k8s/
  terraform/
migrations/
docs/
  adr/
  architecture/
tests/
  contract/
  security/
  load/
```

Pendant la première phase, il est préférable de créer `apps/api`, `apps/worker` et `migrations` à côté du frontend existant plutôt que de déplacer massivement `src/`.

## 9. Ordre exact d’implémentation

1. Stabiliser Node 24, i18n/typecheck, dépendances vulnérables et tests CI.
2. Créer le squelette FastAPI, configuration, health/readiness et OpenAPI.
3. Ajouter PostgreSQL/Alembic et les tables users/organizations/memberships/roles.
4. Implémenter auth, sessions, RBAC et isolation tenant.
5. Ajouter Redis, rate limits, jobs et audit logs.
6. Ajouter le proxy sécurisé vers Agent Canvas/agent-server et les conversations.
7. Ajouter AI Gateway avec un seul provider puis comptage tokens/coûts.
8. Ajouter agents/runs, budgets et entitlements gratuits.
9. Ajouter fichiers S3 et ingestion RAG limitée.
10. Ajouter plans/Stripe Checkout/webhooks/portal/factures.
11. Ajouter quotas payants, suspension, upgrade/downgrade et usage dashboard.
12. Ajouter dashboard admin, support et export/suppression.
13. Ajouter monitoring, backups, load tests, scans et déploiement staging.
14. Réaliser une beta privée avant toute ouverture publique.

## 10. Décisions à valider avant codage important

1. Stripe Billing ou autre prestataire ?
2. Modèle de facturation : crédits, tokens, runs, abonnement avec limites, ou hybride ?
3. Auth initiale : email/password, OAuth, SSO entreprise ?
4. Agent execution : OpenHands Cloud, self-hosted agent-server, ou les deux ?
5. Région et exigences de résidence des données ?
6. Niveau d’isolation : conteneur par run, sandbox persistant, VM ou fournisseur externe ?
7. Premier périmètre RAG : documents privés par organisation ou base de connaissances partagée ?
8. Seuil cible de charge et budget mensuel infrastructure/LLM ?

Aucune fonctionnalité commerciale ou modification architecturale majeure ne doit être considérée approuvée tant que ces décisions ne sont pas validées.
