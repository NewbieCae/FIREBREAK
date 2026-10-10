# FIREBREAK — Plan de build en 6 étapes

> Fin du hacking : dimanche 11 octobre 2026, 17 h. L'interface finale est faite par une collègue ; ce dépôt livre **le produit** (moteur, API, IA) et un dashboard de debug.

## Point de départ (10 octobre, 18 h 40)

Un premier socle existe déjà dans le dépôt, il n'a pas encore été relu :

- `src/firebreak/` : `model.py`, `engine.py` (graphe et propagation), `federation.py` (alertes signées Ed25519), `scenario.py` (4 entreprises), `simulation.py`, `ai.py` (IA simulée), `api.py` (FastAPI).
- `web/index.html` : dashboard de debug (Cytoscape.js).
- `tests/` : 26 tests, tous verts (`uv run pytest -q`).
- Scénario : 193 records ; après « fournisseur compromis depuis 14 h », 17 en quarantaine, 176 continuent, 4 gates bloqués, propagation jusqu'au client.
- Lancement : `uv run uvicorn firebreak.api:app --reload --port 8000`, puis http://localhost:8000.

**Trou connu :** quand on remédie une opération, la libération ne se propage pas aux partenaires. Les alertes déjà émises restent actives et chacun doit remédier de son côté.

## Vue d'ensemble

| # | Étape | Livrable | Dépend de | En parallèle ? |
|---|---|---|---|---|
| 1 | Consolider le socle et figer le contrat API | Code relu, `docs/api.md`, CORS, README | — | Non, à faire d'abord |
| 2 | Fédération complète et journal d'audit | Levée de quarantaine signée, journal des décisions | 1 | Non (touche le moteur) |
| 3 | Scénarios réalistes et import EPCIS | 3 attaques au choix, import JSON EPCIS | 2 | Non (touche le moteur) |
| 4 | Timeline et événements live | Rejeu pas à pas, flux SSE pour animer l'UI | 3 | Non |
| 5 | IA : Bedrock et lecture de documents | `BedrockExplainer`, extraction PDF/mail → record | 1 | **Oui**, en parallèle de 2 à 4 (fichiers `ai.py` et `ingest/` uniquement) |
| 6 | Prêt pour la démo | Script de démo, robustesse, déploiement, gel | 1 à 5 | Non, en dernier |

**Règles communes à tous les handoffs :**

- Lire d'abord `docs/firebreak.md` (l'idée), `docs/benchmark-firebreak.md` (le positionnement) et ce plan.
- Stack : Python 3.12, uv, FastAPI, networkx, `cryptography`, pytest. Pas de nouvelle dépendance sans raison ; versions stables, publiées depuis au moins 7 jours.
- Textes visibles par l'utilisateur en français ; code et identifiants en anglais.
- Principe non négociable : **le blocage est décidé par des règles sur le graphe, jamais par l'IA.** L'IA explique et propose.
- Les entreprises ne lisent jamais les données des autres. Seuls des tokens opaques et des alertes signées circulent.
- `uv run pytest -q` doit rester vert. Chaque étape ajoute ses propres tests.
- Ne pas modifier `CLAUDE.md`, `AGENTS.md` ni `sessionyann.md`. Commit + push à la fin de l'étape.

---

## Handoff 1 — Consolider le socle et figer le contrat API

```text
Projet : FIREBREAK, dépôt finswag (hackathon, gel du dépôt dimanche 12 h).
Lis docs/firebreak.md, docs/benchmark-firebreak.md et docs/plan.md avant de commencer.

Contexte : un premier socle existe (src/firebreak/, web/index.html, tests/, 26 tests verts),
écrit d'une traite et jamais relu. Une collègue va construire l'interface finale sur l'API :
le contrat doit être propre et stable dès maintenant.

À faire :
1. Relire tout src/firebreak/ et tests/ en cherchant les défauts. Points à vérifier en priorité :
   - la propagation suit exactement les règles : seeds = records dont origin == source et ts >= since,
     plus ceux dont le token figure dans une alerte vérifiée ; un record est contaminé si l'une de
     ses entrées l'est, sauf s'il est verified ou released (dans ce cas il bloque la propagation) ;
   - taint_path est correct et le recalcul est déterministe et idempotent ;
   - aucun ledger ne lit directement les records d'un autre ledger ;
   - les alertes ne contiennent que des tokens (ni payload, ni label, ni montant).
   Corriger ce qui est faux et ajouter un test par bug trouvé.
2. Figer le contrat API :
   - modèles Pydantic de réponse pour /api/state, /explain, /remediate (response_model), afin que
     l'OpenAPI (/docs) soit exploitable par la collègue ;
   - CORS ouvert pour le développement (localhost:5173 et localhost:3000) ;
   - préfixe /api conservé, erreurs JSON homogènes {"detail": ...}.
3. Écrire docs/api.md : chaque endpoint avec un exemple de requête et de réponse réelles
   (tronquées), la signification des statuts (ok, quarantined, released), des champs gate et
   verified, et des compteurs.
4. README : section « Lancer le projet » (uv sync, uvicorn, tests, URL du dashboard et de /docs).
5. Supprimer le warning de dépréciation httpx des tests si c'est trivial, sinon le laisser.

Ne pas changer le comportement du scénario : le test tests/test_scenario.py::test_exact_quarantined_set
doit rester vert avec le même ensemble attendu, sauf bug avéré (à justifier dans le rapport).

Fini quand : pytest vert ; serveur lancé sur le port 8000 ; curl de /api/state et de
POST /api/compromise OK ; docs/api.md écrit. Commit + push.
Rapport : bugs trouvés et corrigés, sortie de pytest, compteurs après compromission.
```

## Handoff 2 — Fédération complète et journal d'audit

```text
Projet : FIREBREAK, dépôt finswag. Lis docs/firebreak.md, docs/plan.md et docs/api.md.
Le socle (étape 1) est relu et le contrat API est figé : ne casse pas les endpoints existants,
ajoute des champs ou des endpoints si besoin et mets docs/api.md à jour.

Objectif : rendre la réponse complète entre entreprises et prouvable devant un auditeur
(angle KPMG / conformité).

1. Levée de quarantaine fédérée. Aujourd'hui, si le fabricant remédie m-gr-X, les records reçus
   en aval (d-ship-X, c-ship-X) restent en quarantaine car les alertes déjà émises restent actives.
   À implémenter :
   - un nouveau type d'alerte signée « release » (même format canonique et signature Ed25519 que
     les alertes de contamination, avec un champ type: "taint" | "release"), émise quand un record
     sortant n'est plus contaminé après recalcul ;
   - le destinataire vérifie la signature, retire ces tokens de ses seeds, recalcule et propage
     à son tour vers l'aval, jusqu'à stabilisation ;
   - une release dont la signature est invalide est rejetée et journalisée.
2. Journal d'audit en ajout seul (append-only) par entreprise : déclaration de compromission,
   alerte émise ou reçue (vérifiée ou non), mise en quarantaine (avec la règle et le taint_path),
   remédiation (action, horodatage, acteur : "humain" ou "règle"), levée. Chaque entrée est chaînée
   par hash à la précédente (sha256 de l'entrée précédente + entrée courante), pour qu'on puisse
   prouver que le journal n'a pas été modifié.
   Endpoints : GET /api/audit?company=..., GET /api/audit/verify (recalcule la chaîne et renvoie
   ok ou l'index de la première entrée cassée).
3. Plusieurs déclarations : pouvoir déclarer plusieurs sources compromises, ou la même avec une
   autre heure (on garde la plus ancienne). Endpoint pour retirer une déclaration (fausse alerte),
   ce qui déclenche des releases en cascade.

Tests obligatoires : release valide → aval libéré jusqu'au client ; release falsifiée → rejetée,
aval toujours en quarantaine ; chaîne d'audit valide puis altérée → verify détecte l'index ;
retrait d'une déclaration → retour à l'état initial (zéro quarantaine).
Fini quand : pytest vert, docs/api.md à jour, dashboard de debug toujours fonctionnel. Commit + push.
```

## Handoff 3 — Scénarios réalistes et import EPCIS

```text
Projet : FIREBREAK, dépôt finswag. Lis docs/firebreak.md, docs/plan.md, docs/api.md.

Objectif : montrer que FIREBREAK marche sur des supply chains physiques et s'appuie sur un
standard que l'industrie connaît (GS1 EPCIS 2.0), au lieu d'un format maison.

1. Trois scénarios d'attaque, sélectionnables via POST /api/reset {"scenario": "..."} :
   - "rib" : facture avec RIB modifié → paiement bloqué (le cas finance) ;
   - "cert" : faux certificat qualité → lot de production non conforme mis en quarantaine,
     ainsi que les expéditions de ce lot jusqu'au client ;
   - "asn" : faux avis d'expédition → réception fantôme et production lancée sur un stock inexistant.
   Le scénario actuel (les trois attaques mélangées) devient "mixed" et reste celui par défaut.
   Chaque scénario : déterministe, entre 100 et 150 records, moins de 15 % en quarantaine, au moins
   un gate bloqué, au moins un record verified qui arrête la propagation. Ensemble attendu de
   quarantaine codé en dur dans les tests, raisonné et non copié depuis la sortie.
2. Généalogie des lots : modéliser la transformation (lots consommés → lot produit) comme
   dans un TransformationEvent EPCIS, pour qu'un lot contaminé contamine les lots fabriqués avec lui.
3. Import EPCIS : module src/firebreak/ingest/epcis.py qui lit un document EPCIS 2.0 JSON-LD
   (ObjectEvent, AggregationEvent, TransformationEvent ; champs eventTime, bizStep,
   inputEPCList/outputEPCList, sourceList/destinationList) et le convertit en records d'un ledger.
   Fournir un exemple dans assets/samples/epcis-sample.json et un endpoint
   POST /api/ingest/epcis?company=.... Ne gérer que le sous-ensemble utile, documenté dans docs/api.md.

Tests : un test par scénario (ensemble exact), un test de généalogie de lots, un test d'import
EPCIS sur l'exemple. Fini quand : pytest vert, les trois scénarios visibles dans le dashboard
(ajouter un sélecteur), docs/api.md à jour. Commit + push.
```

## Handoff 4 — Timeline et événements live

```text
Projet : FIREBREAK, dépôt finswag. Lis docs/plan.md et docs/api.md.

Objectif : la démo doit montrer la contamination se propager pas à pas, d'une entreprise à
l'autre, et non un graphe qui devient rouge d'un coup. La collègue qui fait l'UI a besoin d'un
flux d'événements.

1. Rejeu pas à pas : la propagation et la fédération produisent une liste ordonnée d'étapes
   (déclaration, seed, contamination d'un record avec son parent, alerte émise, alerte vérifiée,
   quarantaine d'un gate, release…). Chaque étape a un numéro, un type, une entreprise, des ids
   de records, un horodatage simulé. Ne pas dupliquer la logique : instrumenter le moteur
   existant (callback ou journal d'événements), sans changer ses résultats.
2. Endpoints :
   - GET /api/timeline → la liste complète des étapes de la dernière action ;
   - GET /api/events (Server-Sent Events) → diffuse les étapes en direct, avec un paramètre
     ?speed= pour ralentir le rejeu en démo.
3. Dashboard de debug : bouton « Rejouer » qui anime les étapes (nœuds qui passent au rouge un
   par un, alerte qui « voyage » sur l'arête inter-entreprises).
4. Documenter le format des événements dans docs/api.md, avec un exemple de consommation SSE
   en JavaScript (EventSource) pour la collègue.

Tests : l'état final reconstruit à partir de la timeline est identique à /api/state ; l'ordre
est causal (un record n'est contaminé qu'après son parent, une alerte n'est reçue qu'après avoir
été émise) ; test SSE minimal avec TestClient.
Fini quand : pytest vert, rejeu visible dans le dashboard. Commit + push.
```

## Handoff 5 — IA : Bedrock et lecture de documents (en parallèle de 2 à 4)

```text
Projet : FIREBREAK, dépôt finswag. Lis docs/firebreak.md, docs/plan.md, docs/api.md.
Ne modifie que src/firebreak/ai.py, src/firebreak/ingest/documents.py (nouveau), leurs tests et
le minimum de câblage dans api.py : d'autres étapes travaillent en parallèle sur le moteur.

Règle absolue : l'IA ne décide jamais d'un blocage. Elle explique, propose et extrait des données ;
toute donnée extraite passe par les règles du graphe comme n'importe quel record.

1. BedrockExplainer : implémente l'interface Explainer existante (explain, remediation_plan) avec
   AWS Bedrock via boto3 (Converse API). Modèle configurable par variable d'environnement
   FIREBREAK_BEDROCK_MODEL, région via AWS_REGION. Sélection : FIREBREAK_AI=bedrock|mock (mock par
   défaut). En cas d'erreur, de timeout (8 s) ou d'absence d'identifiants : repli automatique sur
   MockExplainer, et la réponse indique source: "mock" ou "bedrock".
   Le prompt reçoit uniquement le record, son taint_path et les règles appliquées ; il doit
   produire une explication en français et un plan de reprise parmi les actions existantes
   (revalidate, human_approval, trusted_source). Si la réponse n'est pas un JSON valide ou propose
   une action hors liste, rejeter et utiliser le mock.
2. Lecture de documents : POST /api/ingest/document?company=... accepte un PDF ou un texte de mail
   fournisseur (bon de commande, avis d'expédition, facture, changement de RIB) et renvoie un record
   proposé (kind, label, payload : montant, RIB, références, dates) avec un score de confiance.
   Le record n'est ajouté au ledger qu'après confirmation (POST .../confirm). Version mock basée
   sur des expressions régulières, version Bedrock si FIREBREAK_AI=bedrock.
   Mettre 3 documents d'exemple dans assets/samples/ (dont une facture avec RIB modifié).
3. Ne jamais journaliser les identifiants AWS. Aucun secret dans le dépôt.

Tests : tout en mode mock, Bedrock simulé par un faux client (pas d'appel réseau en test) ;
repli sur le mock en cas d'erreur ; rejet d'une action hors liste ; extraction des 3 exemples.
Fini quand : pytest vert, docs/api.md à jour (section IA + variables d'environnement). Commit + push.
```

## Handoff 6 — Prêt pour la démo

```text
Projet : FIREBREAK, dépôt finswag. Lis docs/firebreak.md, docs/benchmark-firebreak.md,
docs/plan.md, docs/api.md. Les étapes 1 à 5 sont livrées.

Objectif : une démo de 3 minutes qui ne peut pas planter, et les chiffres du pitch.

1. Mode démo : FIREBREAK_DEMO=1 → scénario par défaut, IA en mock garanti (aucune dépendance
   réseau), vitesse de rejeu réglée pour la scène, endpoint POST /api/demo/step qui avance la démo
   d'un cran (pour piloter au clic depuis l'UI ou un clavier).
2. Script de démo dans docs/demo.md : chaque clic, ce qu'on voit à l'écran, la phrase à dire,
   et les chiffres réels lus depuis l'API (opérations bloquées, opérations qui continuent, gates
   bloqués, entreprises touchées, montant du paiement frauduleux bloqué). Les chiffres doivent
   venir d'une commande reproductible, pas être recopiés à la main.
3. Robustesse : test de bout en bout qui déroule exactement le script de démo via l'API
   (reset → compromise → rejeu → explain → remediate → release fédérée → audit verify) ; temps de
   réponse de /api/state mesuré (< 200 ms sur le scénario) ; reset fiable entre deux passages.
4. Lancement en une commande : scripts/demo.sh (uv sync, lance le serveur, ouvre le navigateur).
   Optionnel si le temps le permet : Dockerfile minimal.
5. README final : pitch en 3 lignes, architecture, lancement, liens vers docs/.
6. Gel : tag git demo-freeze une fois tout vert.

Fini quand : test de bout en bout vert, docs/demo.md avec chiffres réels, scripts/demo.sh testé
depuis un clone propre. Commit + push + tag.
```
