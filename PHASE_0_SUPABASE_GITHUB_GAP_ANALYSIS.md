# Phase 0 — Analyse des écarts Supabase + GitHub

**Statut :** audit et planification uniquement. Aucun changement applicatif important n’est engagé.

## 1. Nouvelles contraintes d’architecture retenues

Le second cahier des charges rend obligatoires :

- Supabase PostgreSQL comme source durable des données métier ;
- Supabase Auth pour l’identité ;
- PostgreSQL RLS comme défense supplémentaire d’isolation multi-tenant ;
- Supabase Storage pour les fichiers privés ;
- migrations SQL versionnées et Supabase CLI ;
- backend indépendant FastAPI en `/api/v1` ;
- Redis et workers asynchrones ;
- GitHub App avec permissions minimales, installation par client et révocation ;
- aucun token GitHub global partagé ;
- OpenHands conservé comme moteur d’agents ;
- AI Gateway indépendant des fournisseurs ;
- validation explicite avant toute transformation majeure.

Ces contraintes remplacent le choix générique “PostgreSQL/S3/Auth au choix” de la proposition précédente. La cible devient donc **Supabase + FastAPI + Redis + OpenHands + GitHub App**, avec Stripe découplé derrière une abstraction de billing.

## 2. État réel du dépôt audité

Le dépôt contient un frontend Agent Canvas riche, des services de conversations, secrets, backends, Cloud, Git, MCP, automations et une chaîne npm/Electron/Docker. Il sait déjà communiquer avec des backends Git/Cloud et possède plusieurs services cloud côté client.

Il ne contient pas encore, comme socle SaaS indépendant :

- dossier `supabase/` avec `config.toml`, migrations et fonctions ;
- client serveur Supabase Auth validant les JWT ;
- backend FastAPI indépendant ;
- middleware d’authentification et d’autorisation tenant-aware ;
- politiques RLS et tests d’isolation ;
- buckets Supabase Storage privés et règles d’accès ;
- modèle métier Supabase pour users, organizations, memberships, plans, subscriptions, usage, agents et audit ;
- GitHub App multi-client avec installations et tokens d’installation à durée limitée ;
- AI Gateway serveur contrôlant clés, modèles, tokens et coûts ;
- workers Redis pour runs, webhooks, ingestion et traitements différés ;
- billing provider branché et entitlements serveur.

## 3. Adaptation à Supabase

### Auth

Supabase Auth devient le fournisseur d’identité. Le frontend ne doit recevoir que la clé publique/anon nécessaire au flux client ; la clé `service_role` reste uniquement côté backend et secrets d’exécution. FastAPI doit vérifier la signature, l’expiration, l’audience et le sujet du JWT Supabase avant de charger la membership active.

Le `user_id` métier doit être aligné avec le `sub` Supabase Auth. Les profils et memberships doivent être créés par un flux serveur ou une fonction contrôlée, jamais par une écriture frontend libre.

### RLS

Chaque table métier sensible doit porter `organization_id` lorsque c’est pertinent. Les politiques RLS doivent dériver l’identité du JWT et vérifier la membership, sans faire confiance à un `organization_id` envoyé par le navigateur.

Les accès backend privilégiés utilisant `service_role` doivent rester exceptionnels, courts, audités et limités à des opérations qui ont déjà validé user/tenant/permission dans FastAPI. Le backend ne doit pas devenir un moyen de contourner RLS sans contrôles explicites.

### Storage

Créer des buckets privés séparés logiquement par domaine, par exemple `org-files`, `conversation-exports` et `run-artifacts`. Le chemin d’objet doit commencer par l’identifiant organisationnel généré côté serveur. Les uploads doivent utiliser des URLs présignées courtes après validation de taille, MIME, extension, checksum et quota.

Les téléchargements doivent retourner des URLs signées limitées dans le temps. Aucun bucket de données client ne doit être public. Les suppressions, exports, accès administratifs et expirations doivent apparaître dans `audit_logs`.

### Migrations

Créer `supabase/config.toml` et `supabase/migrations/` dans une phase dédiée, avec migrations idempotentes et environnement local reproductible. Chaque migration doit être testée sur une base vide et sur une base contenant les versions précédentes. Les changements RLS doivent être versionnés avec le schéma qu’ils protègent.

## 4. Adaptation à GitHub

### GitHub App

Créer une GitHub App dédiée à la plateforme avec permissions minimales : metadata en lecture, contents selon le besoin, pull requests/issues uniquement si la fonctionnalité les utilise, et webhooks strictement nécessaires. Les installations doivent être rattachées à une organisation SaaS et enregistrées dans une table de connexions.

Le backend doit échanger une installation autorisée contre un token d’installation court, le conserver chiffré ou le régénérer, puis le passer au run agent avec scope minimal. Le frontend ne doit jamais recevoir de clé privée GitHub App ni de token d’installation durable.

### Modèle de données GitHub

Prévoir au minimum :

- `github_app_installations(id, organization_id, installation_id, account_login, account_type, status, created_at, revoked_at)` ;
- `github_repositories(id, organization_id, installation_id, github_repo_id, full_name, default_branch, permissions_snapshot, status)` ;
- `github_webhook_events(id, organization_id nullable, delivery_id, event_name, payload_json, processed_at, status)` ;
- `github_repo_access(id, organization_id, repository_id, allowed_actions, created_at, revoked_at)`.

Le `repository_id` du frontend n’est jamais suffisant : le backend doit vérifier l’installation, l’organisation propriétaire, la permission effective et l’action demandée avant chaque opération.

### Révocation et événements

Le webhook d’installation supprimée doit révoquer immédiatement les connexions et empêcher tout nouveau run. Les tokens déjà injectés doivent avoir une durée courte ; les runs en cours doivent vérifier l’état de connexion à des points de contrôle et s’arrêter proprement si l’accès est révoqué.

Les événements GitHub entrants doivent être authentifiés, dédupliqués par delivery id et filtrés par installation/organisation avant traitement.

## 5. Frontières de sécurité obligatoires

1. Supabase Auth identifie l’utilisateur ; FastAPI décide de l’accès.
2. `organization_id` vient du contexte membership serveur, jamais de la confiance frontend.
3. RLS protège les tables même en cas de chemin de requête imprévu.
4. `service_role` est interdit dans le bundle frontend et interdit aux workers non concernés.
5. Les credentials GitHub sont par installation et jamais globaux.
6. Les credentials IA sont détenus par AI Gateway ou un coffre de secrets, jamais par React.
7. Les agents exécutent dans des sandboxes avec filesystem, réseau, CPU, mémoire et durée limités.
8. Les fichiers Supabase Storage sont privés et servis par URLs signées.
9. Les quotas, coûts et entitlements sont recalculés côté serveur.
10. Les webhooks paiement et GitHub sont signés, idempotents et journalisés avant traitement.

## 6. Plan de migration sans régression

### Étape A — fondation indépendante

Créer `apps/api`, `apps/worker`, `packages/contracts` et `supabase/` sans déplacer `src/`. Ajouter health checks et configuration d’environnement, puis les tests de démarrage.

### Étape B — identité et tenants

Ajouter Supabase Auth, profils, organisations, memberships, rôles et RLS. Ajouter deux organisations de test et prouver les lectures/écritures interdites avant d’exposer les ressources OpenHands.

### Étape C — façade Agent Canvas

Ajouter un client API typé côté Canvas. Faire transiter progressivement conversations et runs par FastAPI, tout en conservant l’intégration backend OpenHands existante en fallback contrôlé pendant la migration.

### Étape D — GitHub App et Storage

Ajouter installations GitHub, dépôts autorisés, tokens courts, buckets privés, uploads présignés et tests de révocation/isolation.

### Étape E — AI Gateway et usage

Introduire un premier provider, budgets, token accounting, usage events, rate limits et runner isolé. Les anciens chemins locaux restent utilisables pour développement mais ne doivent pas contourner le plan de production.

### Étape F — Billing

Ajouter plans/subscriptions/entitlements avant le provider de paiement, puis Stripe ou un autre provider derrière une interface. Les webhooks doivent mettre à jour Supabase de façon idempotente.

## 7. Critères de validation de la Phase 0

La Phase 0 est considérée comme documentée, mais pas comme une phase d’implémentation terminée. Les critères techniques à valider avant Phase 1 sont :

- Supabase est confirmé comme choix définitif ;
- le périmètre de la GitHub App est approuvé ;
- le modèle de tenant et de rôles est approuvé ;
- la stratégie de sandbox des agents est approuvée ;
- le premier provider IA et la politique de clés sont définis ;
- la stratégie Storage et rétention est définie ;
- le modèle de billing et de quotas est défini ;
- le budget et la région d’hébergement sont connus ;
- les tests d’isolation attendus sont acceptés comme critères bloquants.

## 8. Prochaine phase proposée

Après validation explicite, commencer par **Phase 1 — Stabilisation**, sans encore activer la facturation : Node 24, typecheck hermétique, dépendances runtime vulnérables, tests et Docker. Ensuite seulement, créer le squelette Supabase/FastAPI et les migrations d’identité/tenant.
