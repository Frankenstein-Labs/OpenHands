# Cortex.ai — Audit complet d'implémentation

**Date :** 2026-11-23
**Dépôt :** `Frankenstein-Labs/OpenHands`
**Périmètre :** transformation du dépôt en plateforme SaaS Cortex.ai, en conservant OpenHands Agent Canvas et son moteur d'agents.

> Ce document décrit uniquement l'état **réellement vérifié** du dépôt au moment de l'audit.
> Aucune instance Supabase, aucun compte GitHub App, aucun fournisseur IA et aucun
> environnement de paiement n'est déclaré connecté. Les éléments non exécutables dans
> cet environnement (Docker absent, pas d'accès Supabase) sont marqués explicitement.

---

## 1. Verdict exécutif

Le dépôt n'est **pas** un simple frontend de chatbot. C'est déjà un produit riche
(Agent Canvas : conversations, agents, terminal, Monaco, workspaces, MCP, automatisations,
Git, ACP) **plus** un début de socle SaaS sérieux :

- un backend FastAPI indépendant sous `apps/api/` ;
- une vérification JWT Supabase côté serveur (JWKS, issuer, audience, expiration) ;
- un client Supabase REST côté serveur ;
- des routes organisations et memberships avec RBAC ;
- trois migrations SQL versionnées (fondation, invitations, RBAC) ;
- 14 tests backend qui passent réellement dans cet environnement.

Le socle est donc **crédible et réutilisable**. Il manque toutefois l'essentiel d'un SaaS
commercialisable : profils, catalogue de modèles, AI Gateway, agents/runs persistés,
quotas serveur, fichiers privés, facturation, GitHub App multi-tenant, workers, UI SaaS,
et surtout **la preuve d'exécution contre une vraie base Supabase**.

**Niveau de maturité estimé :** fondation multi-tenant ~40 %, plateforme SaaS complète ~10 %.

---

## 2. Méthode d'audit

Inspection directe du dépôt (arborescence, `package.json`, `vercel.json`, `apps/api/`,
`supabase/`, `docs/`, `.github/workflows/`), lecture intégrale du code backend et des
migrations, puis exécution de la suite de tests backend dans un virtualenv local.

Commandes exécutées et résultats :

| Vérification | Commande | Résultat réel |
|---|---|---|
| Python | `python --version` | 3.13.15 |
| Dépendances backend | `pip install -e '.[test]'` | OK |
| Tests backend | `python -m pytest -q` | **14 passed** |
| État Git | `git status -sb` | branche `main`, clone superficiel (`shallow`) |
| Docker | non installé | migrations SQL **non exécutées** contre Postgres |
| Supabase CLI | non requis pour l'audit | non vérifié en local |

---

## 3. Ce qui existe réellement

### 3.1 Frontend (Agent Canvas)

- React 19 + TypeScript + React Router 8 + Vite + Tailwind v4.
- **697 fichiers `.tsx` et 816 fichiers `.ts`** sous `src/`.
- Modules produit : `src/api`, `src/components`, `src/hooks`, `src/services`, `src/stores`,
  `src/routes`, `src/extensions`, `src/i18n`, `src/themes`, `src/ui`.
- Fonctionnalités déjà présentes : conversations, éditeur Monaco, terminal xterm,
  navigateur, fichiers, settings, sidebar, ACP, MCP, automatisations, intégrations Git.
- Chaîne de vérification : `npm run typecheck`, `npm run lint`, `npm test` (Vitest),
  `npm run build`, `npm run build:lib`, Playwright (live / mock-LLM / docker).
- `docs/IMPLEMENTATION_STATUS.md` rapporte 931 fichiers de test, 11 029 tests passés
  (non re-exécutés dans cet audit : trop coûteux, et aucun fichier frontend n'a été modifié).

### 3.2 Backend FastAPI (`apps/api/`)

- `app/main.py` : application FastAPI, CORS, handler d'exception global, routeurs `/api/v1`.
- `app/core/config.py` : `pydantic-settings`, dérivation de l'issuer et du JWKS Supabase.
- `app/security/jwt.py` : vérification RS256/ES256 via JWKS + cache, ou HS256 si secret
  configuré ; `exp`, `sub`, `iss`, `aud` obligatoires ; algorithme contrôlé.
- `app/database/supabase.py` : client REST httpx, mode token utilisateur (RLS) et mode
  admin (`service_role`), RPC, erreurs typées, timeout.
- Modules livrés : `health`, `auth/me`, `organizations` (list/create/get/patch),
  `memberships` (list/add/update/remove/transfer-ownership).
- Tests : 14, dont cas négatifs cross-tenant et élévation de privilèges refusée.
- `Dockerfile`, `.env.example`, `pyproject.toml` (Python ≥ 3.12).

### 3.3 Base de données et sécurité (`supabase/`)

- `config.toml` local (aucun credential hébergé).
- Migration `20261123040000_saas_foundation.sql` : `organizations`, `organization_memberships`,
  `plans`, `organization_entitlements`, `usage_events`, `audit_logs`, helpers RLS
  (`is_org_member`, `has_org_role`), politiques RLS, 3 buckets Storage privés
  (`org-files`, `conversation-exports`, `run-artifacts`) + politiques Storage.
- Migration `20261123041000_organizations_invitations.sql` : rôle `viewer`, table
  `organization_invitations`, fonction `create_organization_with_owner`.
- Migration `20261123042000_membership_rbac.sql` : mutations membership via fonctions
  `SECURITY DEFINER` avec contrôles owner/admin, protection du propriétaire.
- Écritures `usage_events` et `audit_logs` réservées au serveur (aucune politique client).

### 3.4 Chaîne CI / déploiement existante

- `.github/workflows/` : `ci.yml`, `pr.yml`, `docker.yml`, `release.yml`, `npm-publish.yml`,
  tests E2E (mock-LLM, docker), desktop (macOS/Linux/Windows), vérification d'isolation
  des skills, etc. — orientés Agent Canvas, pas encore orientés SaaS.
- `vercel.json` minimal (install command), `Dockerfile` racine, `helm/agent-canvas`.

---

## 4. Ce qui fonctionne / partiellement terminé / absent

### 4.1 Fonctionne (vérifié)

- Frontend Agent Canvas (bâti et testé en amont ; non modifié).
- Backend FastAPI : démarrage, health/ready, validation JWT, routes organisations et
  memberships (logique testée via doubles).
- Migrations SQL : **écrites et cohérentes à la lecture**, mais **non exécutées** ici.

### 4.2 Partiellement terminé

| Élément | État | Manque |
|---|---|---|
| Multi-tenancy | RLS + RBAC + fonctions SQL | profils, invitations API, preuve RLS réelle à 2 utilisateurs/2 orgs |
| FastAPI | auth + orgs + memberships | models, agents, runs, usage, files, billing, invitations |
| Usage/plans | tables + limites en JSON | API usage/entitlements, réservation/débit idempotents |
| Storage | buckets + politiques | endpoints presign, validation MIME/taille/quota, métadonnées fichiers |
| Audit | table + politiques | service d'écriture d'audit exposé |

### 4.3 Absent

- Profils utilisateurs liés à `auth.users`.
- Catalogue de modèles / fournisseurs IA.
- AI Gateway (abstraction fournisseurs, routage, coûts, budgets).
- Agents et runs persistés (statuts, événements, annulation).
- Quotas/concurrence appliqués côté serveur avant lancement.
- Fichiers privés via Supabase Storage (presign, checksum, quota).
- Facturation (plans API, abonnements, factures, abstraction provider).
- GitHub App multi-tenant (installations, tokens courts, webhooks signés).
- Workers Redis (`apps/worker/` inexistant).
- RAG / pgvector.
- UI SaaS (profil, organisation, IA, projets, usage, admin).
- Tests d'isolation réels sur Postgres, tests de charge, staging.

---

## 5. Problèmes de sécurité identifiés

1. **Aucune preuve d'exécution RLS** : les politiques sont écrites mais jamais exécutées.
   Un bug de politique ne serait pas détecté aujourd'hui. Risque : fuite cross-tenant.
2. **`service_role`** : le mode admin existe côté client Supabase mais n'est pas encore
   utilisé ; toute future utilisation doit rester exceptionnelle et auditée.
3. **Absence de rate limiting** sur l'API FastAPI (DoS / abus de coût IA).
4. **Absence de vérification d'appartenance centralisée** pour les futures ressources
   (agents, runs, files) : à factoriser via une dépendance « contexte organisation ».
5. **Invitations** : table présente, mais aucun endpoint ni fonction d'acceptation ;
   le `token_hash` impose un hachage côté serveur (non implémenté).
6. **Secrets** : `.env` ignoré, aucun secret commité — correct. Aucune stratégie de
   rotation/coffre formalisée.
7. **Webhooks** (GitHub, paiement) : non implémentés, donc non signés/dédupliqués.
8. **Sandbox d'exécution** : non implémentée ; ne jamais exécuter de commandes utilisateur
   dans le processus FastAPI.

---

## 6. Problèmes d'architecture

1. `apps/api` n'a pas encore de dépendance « organisation active » partagée : chaque
   ressource future doit vérifier la membership côté serveur, jamais faire confiance au
   `organization_id` du navigateur.
2. Pas de séparation `repositories`/`services` homogène sur toutes les futures ressources
   (à reproduire sur le modèle orgs/memberships).
3. `vercel.json` ne décrit pas encore de routage API ; le backend doit rester un conteneur
   séparé (jamais d'Agent Server persistant dans une fonction serverless).
4. Pas de contrats typés partagés entre frontend et backend (`packages/contracts` proposé).
5. CI orientée produit, pas encore de job backend/SQL.

---

## 7. Tests disponibles et manquants

**Disponibles (backend) :** health, readiness, JWT valide/expiré, auth sans token,
organisations (liste/404 cross-tenant/création), memberships (liste, élévation refusée,
non-membre, transfert owner-only), client Supabase (token+apikey, admin sans clé).

**Manquants :**
- Tests SQL/RLS réels (2 utilisateurs, 2 organisations).
- Tests des futures API (profils, models, agents, runs, usage, files, billing, invitations).
- Tests AI Gateway (streaming, erreurs, fallback, coûts, budgets).
- Tests runner (isolation, timeout, annulation, nettoyage).
- Tests GitHub App (installation, tokens, webhooks, révocation).
- Tests de concurrence (10/25/50/100 utilisateurs réels).
- Tests frontend des écrans SaaS.

---

## 8. Dépendances nécessaires (par phase)

- **Backend :** `fastapi`, `httpx`, `pydantic-settings`, `PyJWT[crypto]`, `uvicorn`,
  `pytest`, `pytest-asyncio` (déjà). À ajouter selon phase : client Redis (`redis`),
  client Stripe (mode test), bibliothèque de hachage (stdlib `hashlib` suffit).
- **Infra :** Supabase (Postgres/Auth/Storage), Redis, plateforme conteneur pour backend
  et workers, Vercel pour le frontend.
- **IA :** credentials par fournisseur (serveur uniquement), endpoint Cortex-0 distant.

---

## 9. Plan d'exécution retenu (et ordre)

1. **Audit** (ce document).
2. **Migrations correctives** : profils, agents/runs/événements, catalogue IA, fichiers,
   facturation, GitHub App, acceptation d'invitation — *nouvelles migrations*, sans
   réécrire les trois existantes.
3. **Backend** : contexte organisation, profils, catalogue modèles, AI Gateway,
   agents, runs (+quotas/concurrence), usage/entitlements, fichiers (presign), facturation,
   invitations — avec tests.
4. **Worker** : squelette de contrats de tâches + file Redis abstraite + tests.
5. **Documentation** : architecture, sécurité, déploiement, accès Supabase, AI Gateway,
   Agent Runner, tests, statut.
6. **Vérification** : `pytest`, `ruff`, validation syntaxique SQL (pglast), frontend intact.
7. **Arrêt explicite** avant toute opération nécessitant Supabase/GitHub/IA/paiement :
   voir `docs/SUPABASE_ACCESS_REQUIREMENTS.md`.

---

## 10. Décisions d'architecture prises pendant cet audit

- **AI Gateway** implémentée comme package Python interne (`apps/api/app/ai_gateway/`)
  plutôt qu'un microservice séparé : conformément à la consigne finale (« privilégier une
  architecture simple et modulaire plutôt qu'une multiplication de microservices »), elle
  reste indépendante des fournisseurs et importable/testable isolément.
- **Runner** : contrats et contrôles de quotas implémentés dans le backend ; l'exécution
  réelle réutilise l'Agent Server OpenHands existant et reste hors du processus FastAPI.
- **Facturation** : abstraction provider + mode « non configuré » honnête (aucun appel
  réel, aucune fausse réussite) tant qu'aucun compte Stripe n'est fourni.
- **Migrations** : jamais de réécriture des migrations déjà potentiellement appliquées ;
  uniquement des migrations correctives nouvelles et idempotentes quand possible.

---

## 11. Prochaines actions immédiates

Voir `docs/IMPLEMENTATION_STATUS.md` (mis à jour) et `docs/SUPABASE_ACCESS_REQUIREMENTS.md`
pour les accès nécessaires. Le travail indépendant (code + migrations + tests + docs) est
réalisé avant de demander un accès Supabase de développement.
