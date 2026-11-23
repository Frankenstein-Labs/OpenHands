# Audit de préparation production — OpenHands Agent Canvas

**Dépôt audité :** `Frankenstein-Labs/OpenHands`
**Branche :** `main`
**Révision auditée :** `7eb410802717996cf568deb67faee224863219ec`
**Dernier commit observé :** `chore(deps): bump framer-motion from 14.12.0 to 14.14.0 (#19918)`
**Date de l’audit :** 23 novembre 2026
**Méthode :** copie locale shallow clone, inspection du code/configuration/CI/Docker/docs, installation verrouillée des dépendances et contrôles locaux. Aucun push, aucune modification du dépôt distant.

## Verdict exécutif

Le dépôt est **avancé et exploitable comme client OpenHands Agent Canvas self-hosted**, pas comme une plateforme SaaS d’intelligence artificielle complète prête à vendre au public.

La partie livrée couvre principalement :

- interface React/React Router de conversations et de contrôle d’agents ;
- profils d’agents, profils LLM, fournisseurs et secrets ;
- MCP, extensions, skills, fichiers/workspace, terminal et éditeur ;
- automatisations planifiées ou déclenchées par événements ;
- connexions Git et plusieurs backends agent ;
- intégration OpenHands Cloud/Enterprise via des API distantes ;
- empaquetage npm, Electron, Docker et publication GHCR multi-architecture ;
- une suite importante de tests unitaires, intégration et E2E.

Il ne contient pas le socle nécessaire à une plateforme commerciale autonome : **pas de checkout, pas de webhooks de paiement, pas de catalogue de plans, pas d’entitlements, pas de gestion de facturation, pas de quotas serveur propres à ce dépôt, pas de portail client ni de modèle de données SaaS local**. Les comptes, organisations, licence et une partie des usages Cloud sont délégués aux backends OpenHands.

**Décision recommandée :** ne pas déclarer ce dépôt “production-ready” pour une plateforme IA payante avant d’avoir construit ou raccordé un backend SaaS dédié et d’avoir fermé les points P0/P1 ci-dessous. Pour un usage self-hosted développeur, le projet est proche d’un produit publiable, sous réserve des validations runtime et sécurité opérationnelle.

## État vérifié

| Domaine | État | Preuve / observation |
|---|---|---|
| Build frontend | **Passe** | `npm run build` produit `build/` et les assets de production. |
| TypeScript | **Passe après génération** | `npm run make-i18n && npm run typecheck` passe. Sur checkout propre, `npm run typecheck` seul échoue car `src/i18n/declaration.ts` est généré mais non produit par le script `typecheck`. |
| Lint | **Passe avec warnings** | `npm run lint` termine avec des avertissements de style inline/arbitrary values ; aucun échec bloquant observé. |
| Tests unitaires complets | **Non concluants** | Deux exécutions ont dépassé le délai disponible/été interrompues avant résumé final. Des warnings React/i18next et traces d’erreurs simulées sont visibles, mais aucun verdict global fiable ne doit être annoncé. |
| E2E locaux | **Non validés ici** | Le dépôt les définit, mais ils nécessitent navigateur, backend agent et/ou LLM mock selon la suite. |
| Docker smoke test | **Non validé ici** | Le CLI Docker n’est pas disponible dans l’environnement d’audit. |
| Dépendances | **Risque à traiter** | `npm ci --ignore-scripts` installe 1 322 paquets ; Node local 22 alors que le projet exige Node >=24. |
| Vulnérabilités runtime | **Bloquant avant exposition publique** | `npm audit --omit=dev` : 3 vulnérabilités (1 haute, 2 modérées). |
| CI/CD | **Solide mais à compléter pour SaaS** | 25 workflows, Node 24.22.1, build Docker multi-arch, SBOM/provenance et GHCR présents. |
| Paiement | **Absent du dépôt** | Aucun package/intégration Stripe, PayPal, Paddle ou équivalent détecté ; aucun checkout/webhook/billing service propre au projet. |
| Base de données applicative | **Absente localement** | Aucun schéma/migration Prisma/SQL identifiable dans ce dépôt ; l’application consomme des API agent/cloud distantes et persiste surtout l’état local. |
| Authentification SaaS | **Déléguée / partielle** | Clé de session et écran d’authentification backend ; Cloud/OAuth/organisations via services distants. Pas de gestion locale complète des utilisateurs et abonnements. |
| Déploiement | **Préparé, pas prouvé de bout en bout** | Dockerfile, entrypoint, health routes, Vercel config, self-hosting docs et workflow GHCR présents ; validation image/runtime à faire sur CI ou machine Docker. |

## Ce qui est prêt ou presque prêt

### Produit client

Le périmètre frontend est substantiel : 1 639 fichiers sous `src`, environ 929 fichiers de tests, 21 routes déclarées et des pages pour conversations, automatisations, settings, LLM, agent profiles, MCP, secrets, skills/plugins, Git et extensions.

La séparation frontend/backend est claire. Le client sait parler à un agent-server local ou distant, à OpenHands Cloud/Enterprise et à des services d’automatisation. La présence de `src/api/cloud/*`, de registres de backends, de services de secrets et de services d’usage indique un client multi-backend plutôt qu’un backend SaaS autonome.

### Build et livraison

Le dépôt possède :

- `package-lock.json` et versions de toolchain explicites ;
- workflows CI avec Node `24.22.1` ;
- build Vite/React Router ;
- packaging npm et Electron ;
- Dockerfile multi-stage avec frontend, agent-server et automation ;
- publication GHCR multi-architecture amd64/arm64 ;
- SBOM et provenance Buildx ;
- routes `/health`, `/alive`, `/ready`, `/server_info` et script `docker/smoke-test.sh` ;
- documentation de self-hosting avec reverse proxy TLS, clé backend et volumes persistants ;
- dépendances Renovate/Dependabot et nombreux tests ciblés.

### Sécurité déjà présente

Plusieurs garde-fous sont bien conçus : génération/persistance de clé de session, mode public sans clé injectée, politique de bind loopback/LAN, séparation des secrets, chiffrement de certains réglages, cookies HttpOnly pour le bridge MARS, contrôle d’origines et refus cross-origin sur des chemins sensibles.

Cela ne remplace pas une sécurité de production complète : le dépôt recommande lui-même TLS/reverse proxy, firewall, durcissement de l’hôte et isolation des workspaces.

## Ce qui reste à construire pour votre plateforme IA

### P0 — indispensable avant paiement ou ouverture publique

1. **Backend SaaS et comptes utilisateurs**
   - inscription, connexion, reset mot de passe, MFA/SSO si nécessaire ;
   - utilisateurs, organisations, équipes, rôles et permissions ;
   - isolation stricte tenant/user des conversations, workspaces, secrets et fichiers ;
   - gestion des invitations, suspension, suppression et export des données ;
   - sessions serveur, rotation/révocation et audit log.

2. **Paiement et abonnement**
   - choix du provider (Stripe Billing est le chemin le plus naturel) ;
   - produits/prix mensuels/annuels, essai, coupons, taxes si nécessaires ;
   - Checkout ou Payment Element côté frontend avec création de session côté serveur ;
   - webhooks signés et idempotents pour `checkout.session.completed`, paiement échoué, renouvellement, annulation et remboursement ;
   - table de souscription et état de facturation côté serveur ;
   - portail de facturation client ;
   - aucune donnée de carte stockée par votre application.

3. **Entitlements, quotas et contrôle de coût IA**
   - plans et limites : messages, tokens, minutes, tâches, stockage, exécutions concurrentes ;
   - compteur d’usage serveur fiable, non modifiable par le client ;
   - pré-autorisation/rate limit avant lancement d’un agent coûteux ;
   - arrêt ou dégradation contrôlée à la limite ;
   - journal d’usage, coût par fournisseur/modèle et rapprochement avec les factures ;
   - protections contre abus, boucles d’agents et création massive d’automatisations.

4. **Backend de données et stockage durable**
   - PostgreSQL/MySQL managé avec migrations versionnées ;
   - stockage objet pour fichiers/trajectoires/exports ;
   - Redis ou file de jobs pour limites, verrous et tâches asynchrones ;
   - sauvegardes testées, restauration et politique de rétention ;
   - chiffrement, rotation des secrets et séparation staging/production.

### P1 — indispensable pour un SaaS exploitable

- observabilité structurée : logs corrélés, métriques, traces, alertes et Sentry/OpenTelemetry ;
- support client et mécanisme d’incidents ;
- pages légales : CGU, confidentialité, DPA, sous-traitants, rétention et suppression ;
- consentement analytics et conformité selon les marchés visés ;
- limitation des uploads, antivirus/sandbox, filtrage SSRF et protection des callbacks/webhooks ;
- tests de charge et de concurrence sur conversations, automations et quotas ;
- stratégie de migration et compatibilité des versions agent-server/automation ;
- blue/green ou rolling deploy, rollback vérifié et health checks externes ;
- gestion des domaines, DNS, TLS, secrets CI et environnements ;
- accessibilité, traduction et tests navigateur sur les parcours d’onboarding et de paiement.

### P2 — produit et croissance

- landing page et onboarding commercial ;
- page pricing et comparaison des plans ;
- dashboard usage/factures ;
- self-serve upgrade/downgrade ;
- affiliation/referrals et coupons ;
- équipe/admin console ;
- marketplace/intégrations validées ;
- SLA, disponibilité multi-région et plan de reprise après sinistre.

## Paiement : conclusion précise

Dans la révision auditée, je n’ai identifié :

- aucune dépendance runtime de paiement ;
- aucun endpoint de checkout ;
- aucun endpoint de webhook signé ;
- aucune table ou migration de souscription/facture ;
- aucune page pricing/checkout/billing dans les routes du client ;
- aucun mécanisme d’entitlement local bloquant une action IA ;
- aucun secret de provider de paiement documenté dans `.env.sample`.

Les notions de Cloud, organisations, licence et usage visibles dans le code correspondent à des API OpenHands distantes ou à des fonctions de contrôle du backend, pas à une implémentation de facturation SaaS dans ce repository.

## Risques techniques relevés

### R1 — vulnérabilités runtime

`npm audit --omit=dev` rapporte :

- `zod` : haute, risque d’épuisement mémoire lors de la validation de collections contraintes trop grandes ;
- `fflate` : modérée, boucle infinie possible sur des ZIP64 malformés ;
- `moment` : modérée, path traversal via un nom de locale non-string forgé.

Les trois sont transitives. Il faut remonter leurs arbres (`npm ls zod fflate moment`), mettre à jour les dépendances parentes ou forcer une résolution sûre si compatible, puis relancer audit, tests et build. Ne pas utiliser `npm audit fix --force` sans revue de compatibilité.

### R2 — typecheck non hermétique sur checkout propre

`npm run typecheck` appelle `react-router typegen && tsc`, mais ne lance pas `npm run make-i18n`. Une checkout fraîche échoue donc avec des imports `#/i18n/declaration` manquants. Le CI peut masquer ce défaut si une étape précédente génère les traductions. À corriger en rendant le script hermétique ou en ajoutant explicitement l’étape dans tous les jobs concernés.

### R3 — compatibilité Node locale

`package.json` exige Node `>=24` et le CI utilise 24.22.1, mais l’audit local a été lancé avec Node 22.23.4/npm 10.9.9. Les validations finales doivent utiliser Node 24.22.1 et npm compatible avec le lockfile.

### R4 — tests complets non qualifiés

La suite Vitest produit des warnings React `act(...)`, warning de bouton imbriqué et warnings `react-i18next` sans instance initialisée dans certains tests. Ces messages ne prouvent pas une régression fonctionnelle, mais ils réduisent le signal du CI. Le résultat global doit être obtenu dans un runner Node 24 avec timeout adapté, puis les warnings doivent être classés ou supprimés.

### R5 — image Docker non testée dans cet audit

Le Dockerfile et le workflow existent, mais le CLI Docker n’était pas installé dans l’environnement d’audit. Il reste à exécuter le build, le smoke test `/health`, le test de stabilité et les E2E Docker sur amd64 et, idéalement, arm64.

### R6 — production internet-facing dépendante de l’opérateur

L’image expose un serveur qui écoute dans le conteneur et persiste l’état via volumes. TLS, reverse proxy, firewall, sauvegardes, rotation de secrets, stockage durable et restauration sont documentés comme responsabilités de self-hosting. Ce n’est pas un défaut pour un outil self-hosted, mais ce n’est pas une plateforme SaaS managée prête à l’emploi.

## Plan recommandé de construction

### Phase 1 — stabiliser le socle existant

1. Fixer Node 24.22.1 dans `.nvmrc`/Volta ou équivalent et documenter le runtime.
2. Rendre `typecheck` hermétique avec la génération i18n.
3. Résoudre les 3 vulnérabilités runtime et vérifier les chemins ZIP/locale/validation exposés.
4. Faire passer tests unitaires, typecheck, lint et build dans un CI reproductible.
5. Exécuter Docker build + smoke + E2E avec agent-server et automation épinglés.
6. Ajouter une checklist release avec rollback, sauvegarde et scan de secrets.

### Phase 2 — créer le backend SaaS

1. Service API séparé, base relationnelle et migrations.
2. Auth, tenants, rôles, sessions, audit logs.
3. Modèle `plans`, `subscriptions`, `entitlements`, `usage_events`, `invoices` et `provider_events` idempotents.
4. Service de quota/coût côté serveur devant chaque lancement et chaque appel facturable.
5. Stockage objet, jobs asynchrones, retry et observabilité.

### Phase 3 — brancher le paiement

1. Créer les Products/Prices dans Stripe en mode test.
2. Implémenter Checkout côté serveur et redirect sécurisé.
3. Implémenter vérification de signature webhook, idempotence et journalisation.
4. Calculer les entitlements depuis l’état de souscription, jamais depuis le frontend.
5. Ajouter pricing, billing portal, facture et état d’abonnement dans l’UI.
6. Tester cartes de test, renouvellement, paiement échoué, annulation, remboursement, downgrade et webhook hors ordre.

### Phase 4 — ouverture commerciale

1. Privacy/legal/support et politique de rétention.
2. Tests de charge et tests d’abus.
3. Monitoring/alerting et runbooks.
4. Déploiement canary/rollback.
5. Revue sécurité externe avant production.

## Conclusion

**Prêt aujourd’hui :** un client Agent Canvas self-hosted riche, avec une chaîne de build/release sérieuse et une base de tests importante.

**Pas prêt aujourd’hui :** une plateforme IA SaaS autonome avec comptes, paiement, plans, quotas, factures, stockage multi-tenant et contrôle des coûts.

Le prochain travail ne doit donc pas commencer par “ajouter Stripe dans ce frontend” seulement. Il faut d’abord définir l’architecture SaaS et son backend d’autorité, puis connecter Agent Canvas comme client authentifié et soumis aux entitlements serveur.
