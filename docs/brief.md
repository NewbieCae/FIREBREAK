# Finswag — brief Secure Horizons

Page Notion : https://app.notion.com/p/3f58c3ea1f5e81e88164e25c35e8475e

**Finswag — Secure Horizons, Team 14, Track 1 « Guardians of Value ».** Espace de cadrage et de coordination de l’équipe. Le Track 1 est confirmé dans le brief ; le produit à construire et la répartition des rôles restent à valider.

# Projet et sources
- **Dépôt GitHub privé :** [Sc4rville/finswag](https://github.com/Sc4rville/finswag)
- **Dossier local :** `/home/yann/projects/finswag`
- **Source principale :** mail « \[CODEX\] brief hackathon Secure Horizons - Track 1 Guardians of Value (Avalanche + AWS) », reçu dans `[adresse retirée]` le 2026-10-10 à 12:26 (Europe/Paris).
- **Nom du projet :** le mail mentionnait « secureswag » ; le dépôt et cette page utilisent « finswag », conformément à la demande actuelle de Yann.
- Les informations événementielles et techniques ci-dessous sont reprises du mail. Le [Candidate Guide](https://app.notion.com/p/Candidate-Guide-Track-Guidance-EN-3f400920c77e81beb3b4fad01fc5eeda) n’est pas accessible avec la connexion Notion actuelle ; ses indications sont rapportées depuis le brief.

# Contexte du hackathon
- **Événement :** Secure Horizons, organisé par UTOPIA × KRYPTOSPHERE × ESSEC MetaLab.
- **Lieu :** ESSEC Cergy, 3 avenue Bernard Hirsch.
- **Format annoncé :** 150 builders, 36 heures, 3 tracks ; équipes jusqu’à 5 personnes. Repas et hébergement gratuits.
- **Accueil :** 2026-10-10 à 09:00 (Europe/Paris) ; présentation de 10 h à 11 h ; formation d’équipe de 10 h 50 à 11 h 30.
- **Hacking :** début annoncé le 2026-10-10 à 11:00 (Europe/Paris) ; fin annoncée le 2026-10-11 à 17:00 (Europe/Paris).
- **Changement de track :** possible jusqu’au point de contrôle du 2026-10-10 à 18:30 (Europe/Paris) ; places possiblement plafonnées.
- **Équipe :** Team 14, équipe AWS. Le brief rapporte la décision de Yann à 12 h 25 : partir sur le Track 1.
- **Prix annoncés :** environ 15 000 € au total, plus des crédits infrastructure. Répartition par track et critères de jury non précisés dans le mail.
- **Soutien cité :** France 2030 (ANR-23-CMAS-0020) / NextGenerationEU.

# Brief — Track 1 « Guardians of Value »
## Objectif
Construire une solution défensive qui sécurise les systèmes financiers, les transactions ou les actifs numériques : **surveiller, détecter et répondre aux menaces visant l’argent**, de la banque à la DeFi.
## Public et besoin
Finance, blockchain, antifraude et conformité. Le guide cité décrit des défenseurs noyés d’alertes et de faux positifs, des agents IA non supervisés, des abus d’outils et de privilèges, ainsi que des besoins de détection, réponse et assurance cyber.
## Cadre attendu
- Approche **Blue Team**, centrée sur la défense.
- Traiter au moins une fonction du **NIST CSF 2.0**, idéalement **Detect** ou **Respond**.
- Référentiels cités : MITRE ATT&CK, MITRE ATLAS, MITRE D3FEND et OWASP Top 10 for Agentic Applications.
- **Jury Track 1 :** Team1 / Avalanche, KPMG, KRYPTOSPHERE France.
- Angle suggéré dans le brief pour KPMG : conformité, auditabilité et réduction des faux positifs.
- Le guide ne fournit pas de défi précis, de barème ni de prix par track selon le mail.
## Autres tracks, pour contexte
- Track 2 « Defenders Augmented » : IA × cyber ; jury GitGuardian, ESSEC MetaLab, KPMG.
- Track 3 « Uncharted Frontiers » : sujets libres ; jury Bpifrance, ESSEC Alumni, UTOPIA.

# Ressources techniques
## Avalanche / Team1
Le brief prévoit Avalanche pour la partie on-chain, avec une utilité démontrable : preuve, traçabilité ou journal d’audit.
- **Réseau :** testnet Fuji, C-Chain compatible EVM.
- **Outils possibles :** Solidity, MetaMask ou Core, Hardhat ou Foundry.
- **Chain ID annoncé :** 43113 ; token de test AVAX.
- [Explorer Fuji](https://testnet.snowtrace.io)
- [Builder Hub — inscription](https://build.avax.network/signup?ref=HGURW)
- [Faucet](https://build.avax.network/console/primary-network/faucet)
- Le lien [Chainlist 43113](https://chainlist.org/chain/43113) fourni par les organisateurs décrit le réseau. L’endpoint candidat `https://api.avax-test.network/ext/bc/C/rpc` reste **à tester** ; le brief ne le présente pas comme confirmé par les organisateurs.
- Si le faucet ne suffit pas : contacter Yassir à `[adresse retirée]` avec l’adresse EVM publique du wallet.
- Utiliser un wallet dédié au hackathon. Consigner les adresses des contrats déployés dans GitHub.

## AWS / Bedrock
- Compte temporaire, gratuit et isolé par équipe.
- **Région unique annoncée :** `us-east-1`.
- Bedrock, Bedrock AgentCore et services AWS de base ; modèles cités dans le mail : Claude, Amazon Nova, GPT-5.x, Llama et Mistral.
- **Pas de GPU.** Rester sous environ une requête par seconde et par personne.
- Un membre de l’équipe doit remplir le formulaire d’usage Claude dans la console Bedrock.
- Le lien unique d’accès Team 14 se trouve dans le mail organisateur du 10 octobre à 11 h 03. Le récupérer depuis la boîte de Yann.
- **Kiro :** offre annoncée de 100 codes de 1 000 crédits, premier arrivé premier servi ; à réclamer avant le dimanche 11 octobre à minuit selon le mail : [promotion Kiro](https://pulse.amazon/promotion/L9OJAMMY).
- Le compte AWS sera supprimé à la fin : sauvegarder régulièrement le code sur GitHub et enregistrer une vidéo de démo avant la fin.

# Règles du hackathon reprises du mail
- Tester et attaquer uniquement ce que notre équipe déploie dans son propre compte.
- Ne pas cibler une autre équipe, le réseau ESSEC, AWS ou un site externe.
- Pas de déni de service, malware, phishing ou jailbreak de modèles.
- Utiliser des données synthétiques et de faux secrets, par exemple `FLAG{team14-canary}` ; aucune donnée personnelle réelle.
- Ne jamais partager une vraie clé ou une seed phrase.
- Pousser le code sur GitHub au moins toutes les heures.
- Les liens Discord doivent être récupérés depuis le canal ou l’écran officiel sur place : le brief signale deux invitations différentes dans les mails organisateurs.

# Pistes de produit — à valider avec l’équipe
Les quatre idées suivantes sont des propositions du brief, **aucune n’est validée par Yann**.
## A — Triage d’alertes antifraude
Flux de transactions synthétiques ; agent Bedrock qui classe et explique les alertes et vise à réduire les faux positifs. Hash des décisions et preuves ancré dans un contrat Fuji pour un audit vérifiable.
## B — Moniteur de contrats et transactions
Surveillance de transactions Fuji : drain, approvals suspects et appels anormaux. Évaluation du risque avec un LLM ; réponse par alerte ou pause d’un contrat de démo via un circuit breaker Pausable. Les scénarios portent uniquement sur nos propres contrats.
## C — Garde-fou pour agents IA qui paient
Proxy qui contrôle les droits, plafonds et destinataires d’un agent exécutant des paiements. Politique on-chain d’allowlist et de limites ; journal d’actions vérifiable et détection d’abus de privilèges ou d’outils.
## D — Journal d’audit pour la conformité
Ancrage périodique des hashes de logs sur Fuji, vérificateur d’intégrité et résumé IA. Démontrer la traçabilité et les preuves utilisables pour un audit ou l’assurance cyber.
## Recommandation contenue dans le mail
Discuter d’une combinaison **B + C** : détection et réponse sur contrats, avec un agent IA encadré. Préparer une démonstration claire en trois minutes ; la durée officielle reste à confirmer.

# Plan de travail proposé — à confirmer
1. **Cadrage :** choisir le scénario, valider le périmètre, les rôles, la stack et les critères de réussite ; récupérer les accès AWS et Fuji.
2. **Premier parcours :** données synthétiques, contrat de démonstration Fuji, première analyse Bedrock et interface minimale.
3. **Intégration :** relier événement suspect, explication, garde-fou ou réponse et preuve on-chain.
4. **Validation :** scénarios normal / suspect, comportement en cas d’échec et mesure de l’effet attendu.
5. **Rendu :** README, adresses des contrats, vidéo enregistrée et pitch. Caler les jalons sur les horaires officiels et le format de soumission.

# Équipe et accès
Adresses fournies par Yann pour un accès en modification :
- [adresse retirée]
- [adresse retirée]
- [adresse retirée]

**Statut Notion :** invitations non envoyées ; le connecteur actuel ne fournit pas d’outil de partage. La liste ci-dessus ne donne pas accès à la page. La page est actuellement privée.
**GitHub :** le contexte local indique des invitations déjà envoyées à NewbieCae, mncodol et magraku avec accès en écriture ; acceptation à vérifier.

# Actions et questions ouvertes
- [x] Retrouver et intégrer le brief transmis à Codex.
- [x] Créer la page Finswag et lier le dépôt existant.
- [ ] Inviter les trois adresses sur Notion avec accès en modification.
- [ ] Choisir le produit et préciser le périmètre du MVP.
- [ ] Confirmer le nombre de membres, la stack, les ressources déjà prêtes et la répartition des rôles.
- [ ] Demander aux organisateurs : barème Track 1, prix par track, durée de démo, format et échéance exacte du rendu.
- [ ] Vérifier les accès AWS, le formulaire Claude, le wallet dédié et le RPC Fuji.
- [ ] Consigner les contrats déployés ; pousser au moins toutes les heures.
- [ ] Enregistrer la démo avant suppression du compte AWS.

# Organisation du dépôt
- `src/` : code source.
- `assets/` : ressources.
- `scripts/` : utilitaires.
- `docs/` : brief et documentation.
