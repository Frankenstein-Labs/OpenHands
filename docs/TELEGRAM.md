# Telegram vers OpenHands Cloud

Cette intégration ajoute un webhook Vercel minimal : Telegram reçoit le message, la fonction crée ou reprend la conversation OpenHands Cloud associée au chat, puis renvoie la réponse texte de l’agent dans Telegram. Le navigateur n’est pas requis pendant l’exécution.

## Variables Vercel

Ajouter ces variables côté **serveur** dans Vercel, pour les environnements utilisés :

| Variable                   | Requise | Valeur                                                                                            |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`       | Oui     | Token fourni par BotFather. Ne pas utiliser le préfixe `bot` dans la valeur.                      |
| `TELEGRAM_WEBHOOK_SECRET`  | Oui     | Chaîne aléatoire d’au moins 32 caractères, utilisée pour vérifier l’en-tête secret Telegram.      |
| `TELEGRAM_ALLOWED_CHAT_ID` | Oui     | Identifiant numérique de votre chat Telegram personnel. Les autres chats sont ignorés.            |
| `OPENHANDS_CLOUD_API_KEY`  | Oui     | Clé API OpenHands Cloud créée dans Settings → API Keys. Elle doit rester côté serveur.            |
| `OPENHANDS_CLOUD_HOST`     | Non     | Hôte Cloud ; valeur par défaut : `https://app.all-hands.dev`.                                     |
| `OPENHANDS_REPOSITORY`     | Non     | Dépôt transmis aux nouvelles conversations ; valeur par défaut : `Frankenstein-dev197/OpenHands`. |

`TELEGRAM_ALLOWED_CHAT_ID` est obligatoire pour empêcher tout autre chat Telegram de déclencher des tâches. `OPENHANDS_CLOUD_API_KEY` est nécessaire même si l’interface web est déjà connectée avec un cookie : une fonction Vercel ne peut pas réutiliser le cookie de votre navigateur lorsque l’ordinateur est éteint.

## Activer le webhook

Après le déploiement Vercel, lancer une fois la commande suivante depuis le dépôt, avec le token et le secret disponibles dans l’environnement local :

```bash
TELEGRAM_BOT_TOKEN='…' \
TELEGRAM_WEBHOOK_SECRET='…' \
TELEGRAM_WEBHOOK_URL='https://votre-projet.vercel.app/api/telegram' \
npm run telegram:set-webhook
```

La commande appelle l’API officielle Telegram `setWebhook` et limite les mises à jour aux messages. Vérifier ensuite l’état avec `getWebhookInfo` si nécessaire.

## Commandes

`/start` confirme la connexion, `/help` affiche l’aide, `/new` crée une nouvelle conversation Cloud, `/status` affiche l’état de la conversation associée et `/stop` met en pause le sandbox courant. Tout autre message texte est envoyé à l’agent. Les conversations sont retrouvées sans base de données supplémentaire grâce à leur titre Cloud `Telegram chat <chat_id>`.
