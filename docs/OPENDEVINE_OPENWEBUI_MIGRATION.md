# Contrat de migration OpenDevine : interface Open WebUI et moteur OpenHands

## Objectif

OpenDevine utilise le fork [`Frankenstein-dev197/open-webui`](https://github.com/Frankenstein-dev197/open-webui) comme référence de l’interface et des interactions Open WebUI, tout en conservant [`Frankenstein-dev197/OpenHands`](https://github.com/Frankenstein-dev197/OpenHands) comme moteur réel d’exécution. La migration est progressive : l’interface peut évoluer rapidement, mais aucun service OpenHands validé ne doit être remplacé par une simulation.

## Architecture cible

```text
Interface Open WebUI réimplémentée en React/TypeScript OpenDevine
  ↓
Adaptateurs OpenDevine
  ↓
Services et hooks OpenHands existants
  ↓
Agent Server / TypeScript client / WebSocket d’événements
  ↓
Workspace réel, outils, MCP, worktrees, sous-agents, runtime et Live Preview
```

Le fork Open WebUI reste une **référence de code et d’UX à auditer**, pas un backend à supprimer sans remplacement. La cible est de reprendre les hiérarchies, interactions et états utiles dans le frontend React OpenHands, puis de retirer progressivement les dépendances au backend Open WebUI seulement lorsqu’un contrat OpenHands équivalent est branché et testé.

## Frontières non négociables

L’UI peut modifier la disposition, la navigation, les styles, les libellés et les composants de présentation. Elle ne doit pas remplacer ni contourner l’adaptateur Agent Server, le chemin WebSocket/événements, les services MCP, les client tools natifs, le lancement d’enfants, l’isolation worktree, le mono-writer, les services runtime, la gestion des URL Live Preview ou la politique CI/CD.

Une capacité n’est affichée comme action active que si son contrat backend existe et est testé. Les fixtures et handlers mockés restent réservés aux tests et ne doivent jamais être sélectionnés par l’entrée de développement ou de production.

## Flux stable

```text
Agent Server OpenHands
  ↓
Adaptateurs API et hooks TypeScript existants
  ↓
Types d’événements OpenHands normalisés
  ↓
Stores Zustand et état de conversation
  ↓
Composants de présentation OpenDevine
  ↓
Interactions inspirées du shell Open WebUI
```

Les composants de présentation consomment les données et callbacks des hooks/stores existants. Ils ne doivent pas appeler directement Agent Server. Les effets de bord API restent dans les services et hooks déjà responsables de ces contrats.

## Cartographie des surfaces

| Surface Open WebUI | Contrat OpenDevine/OpenHands | Règle de migration |
| --- | --- | --- |
| Sidebar, conversations et recherche | `Sidebar`, routes React, store sidebar et services de conversations | Réorganiser et re-thémer progressivement ; conserver les liens et actions réels. |
| New Chat | `AgentServerConversationService`, hooks de création et sélection backend/workspace | Conserver création, profils, workspace, worktree et erreurs réelles. |
| Chat et composer | `ConversationMain`, `ChatInterface`, `EventHandler`, stores et WebSocket provider | Migrer uniquement la présentation ; préserver l’ordre des événements, le streaming compatible et les confirmations. |
| Sélecteur modèle/profil | Services de profils, settings et hooks LLM | Ne jamais déduire un modèle ou une capacité depuis le seul état visuel. |
| Fichiers et pièces jointes | API upload/fichiers et hooks conversation OpenHands | Garder les uploads réels, les permissions et les chemins bornés au workspace. |
| Outils et MCP | Routes `/mcp`, services MCP et client tools Agent Server | Ne pas ajouter de cartes d’intégration visuelles sans contrat fonctionnel. |
| Workbench | Files, Terminal, Browser, Commits, planner, tasks et Preview existants | Composer les surfaces existantes avant d’en créer une nouvelle. |
| Live Preview | URL workspace/worker forwardée, iframe réel et hooks de refresh | Ne pas remplacer par un iframe mocké ni une URL inventée. |
| Agents et sous-agents | `launch_child_conversation`, worktrees isolés, limiteur et mono-writer | Conserver les garde-fous et l’intégration unique. |
| Authentification et sessions | Auth OpenHands et backend registry | Adapter la présentation seulement après validation du transport et des permissions. |

## Remplacement progressif du moteur Open WebUI

Le backend Python/FastAPI du fork Open WebUI fournit aujourd’hui ses propres sessions, auth, stockage, modèles, routes `/api/v1/*` et Socket.IO `/ws/socket.io`. Il ne doit donc pas être supprimé en bloc. La séquence sûre est la suivante :

1. **Référence visuelle et comportementale.** Reprendre les patterns UX du fork dans des composants React OpenDevine propres, sans copier aveuglément le code Svelte ou les assets de marque.
2. **Adaptateur de transport.** Introduire, surface par surface, un adaptateur qui traduit les états OpenHands vers les données attendues par la présentation. La source de vérité reste le service OpenHands existant.
3. **Parcours réels.** Valider chaque surface avec Agent Server réel : création de conversation, événements WebSocket, fichiers, MCP, terminal/workspace, Git/worktree, sous-agent et Preview.
4. **Désactivation contrôlée.** Une route ou dépendance Open WebUI ne peut être retirée qu’après migration de tous ses consommateurs, test de démarrage et test navigateur. Toute suppression doit être faite sur branche et rester réversible.
5. **Nettoyage final.** Après couverture complète et validation de production, retirer seulement les services Open WebUI devenus orphelins, en conservant les avis de licence et la traçabilité des changements.

## Première tranche publiée

La première tranche déjà intégrée sur la branche `feat/multi-agent-orchestration-guardrails` adopte une coque OpenDevine inspirée de la hiérarchie Open WebUI : titre et wordmark OpenDevine, sidebar plus proche du modèle de référence, rangées compactes et liens vers les surfaces réelles Agent profiles et MCP. Elle ne modifie ni la création de conversation, ni le transport d’événements, ni MCP, ni les routes Preview.

## Licence et attribution

Le fork audité contient une licence Open WebUI imposant la conservation des avis de copyright et comportant une clause spécifique sur la marque Open WebUI, notamment pour les déploiements de plus de 50 utilisateurs sur une période glissante de 30 jours. OpenDevine privilégie donc une implémentation React/TypeScript propre des patterns UX vérifiés, conserve les notices applicables et ne revendique aucune affiliation ou approbation officielle d’Open WebUI. Toute réutilisation directe de code ou d’assets doit être examinée séparément avant distribution.
