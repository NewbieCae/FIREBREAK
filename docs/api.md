# FIREBREAK — Contrat de l'API

Version du contrat : **1.2.0** (figée en 1.0.0 à l'étape 1 du [plan](plan.md) ; l'étape 2 a ajouté les levées fédérées, le retrait de déclaration et le journal d'audit ; l'étape 3 a ajouté les scénarios, la généalogie des lots et l'import EPCIS, sans rien retirer). Les étapes suivantes peuvent **ajouter** des champs ou des endpoints, jamais en retirer ou en renommer sans mettre ce document à jour.

- Base : `http://localhost:8000`. Tous les endpoints sont sous `/api`.
- Schéma OpenAPI interactif : http://localhost:8000/docs (JSON brut : `/openapi.json`). Les modèles de réponse sont définis dans `src/firebreak/schemas.py`.
- CORS ouvert pour le développement : `http://localhost:5173`, `http://localhost:3000` (et leurs équivalents `127.0.0.1`).
- L'état est en mémoire, partagé par tous les clients : un `POST /api/reset` remet tout à zéro pour tout le monde.

Les exemples ci-dessous sont de vraies réponses du serveur, tronquées (`…`).

## Vocabulaire

| Terme | Sens |
|---|---|
| **record** | Une opération métier dans le registre d'une entreprise : commande, avis d'expédition (`asn`), certificat, facture, paiement, lot de production, expédition… |
| **seed** | Record directement suspect : émis par une source déclarée compromise après l'heure `since`, ou reçu d'un partenaire qui l'a signalé dans une alerte signée valide. |
| **contamination** | Un record est contaminé dès qu'une de ses entrées (`inputs`) l'est. Le moteur suit ces dépendances de proche en proche. |
| **alerte** | Message signé (Ed25519) d'une entreprise à un partenaire. Il ne contient que des jetons opaques : ni libellé, ni montant, ni payload. Deux types : `taint` (ces données sont contaminées) et `release` (elles ne le sont plus). Le type fait partie de ce qui est signé. |
| **levée** | Sortie de quarantaine. Quand un record déjà signalé à un partenaire redevient sain (remédiation, retrait de déclaration), l'expéditeur envoie une alerte `release` signée ; le partenaire la vérifie, retire les jetons, recalcule et lève à son tour vers l'aval. Une `release` à la signature invalide est rejetée : l'aval reste bloqué. |
| **journal d'audit** | Une liste d'événements par entreprise, en ajout seul, chaînée par hash. Voir [`GET /api/audit`](#get-apiaudit). |

### Statuts d'un record (`status`)

| Valeur | Sens |
|---|---|
| `ok` | Ne dépend d'aucune donnée suspecte : l'opération continue. |
| `quarantined` | Dépend d'une donnée suspecte : l'opération est bloquée. `taint_path` donne la preuve. |
| `released` | Débloqué par une remédiation (`POST …/remediate`). Ne sera plus jamais contaminé et **arrête la propagation** : ses descendants redeviennent `ok` s'ils ne dépendaient que de lui. |

### Champs clés d'un record

| Champ | Sens |
|---|---|
| `gate` | `true` = action irréversible (paiement, expédition, lancement de production). Un gate en quarantaine est compté dans `gates_blocked`. |
| `verified` | `true` = confirmé par une source de confiance (ex. contrôle physique à la réception). Jamais contaminé, arrête la propagation. |
| `origin` | Entreprise qui a émis la donnée. Différente de `company` pour un record reçu d'un partenaire. |
| `token` | Jeton opaque (sha256 hex, 64 caractères) d'un record reçu d'un partenaire ; `null` pour un record interne. |
| `inputs` | Records **du même registre** dont celui-ci dépend. Les liens entre entreprises sont dans `edges` avec `cross: true`. |
| `taint_path` | Chemin le plus court du seed jusqu'à ce record, dans le registre de l'entreprise (`null` si non contaminé). Un record reçu contaminé par alerte commence son propre chemin. |
| `ts` | Horodatage ISO 8601 sans fuseau, en heure de Paris. |

### Compteurs (`counters`)

`counters.global` (toutes entreprises) et `counters.per_company.<id>` ont la même forme :

| Champ | Sens |
|---|---|
| `total` | Nombre de records. |
| `quarantined` | Records bloqués. |
| `ok` | Records qui continuent normalement (`total - quarantined - released`). |
| `released` | Records débloqués par remédiation. |
| `gates_blocked` | Actions irréversibles bloquées. |
| `amount_blocked` | Montant des **paiements** bloqués (€) : somme des `payload.amount` des records `kind == "payment"` en quarantaine. |
| `amount_flowing` | Montant des **paiements qui continuent** (€) : records `kind == "payment"` en `ok` + `released`. |

« Opérations qui continuent » à l'écran = `ok + released`. Seuls les records `kind == "payment"` participent aux totaux `amount_*` — une facture et sa copie reçue portent le même montant, les compter compterait les mêmes euros plusieurs fois ; le paiement est l'opération où l'argent bouge réellement.

## Erreurs

Toutes les erreurs ont la même forme : `{"detail": "<message en français>"}` (une chaîne, jamais une liste).

| Code | Quand | Exemple |
|---|---|---|
| 400 | Action refusée | `{"detail": "action invalide: hack"}`, `{"detail": "record non mis en quarantaine"}` |
| 404 | Entreprise, record ou route inconnus | `{"detail": "record inconnu: nope"}`, `{"detail": "Not Found"}` |
| 422 | Corps de requête invalide | `{"detail": "requête invalide — since: Field required"}` |

## Endpoints

| Méthode | Chemin | Réponse |
|---|---|---|
| GET | `/api/state` | État complet |
| POST | `/api/compromise` | État complet après propagation |
| POST | `/api/compromise/withdraw` | État complet après levées en cascade |
| GET | `/api/records/{id}/explain` | Explication et plan de reprise |
| POST | `/api/records/{id}/remediate` | État complet après recalcul |
| POST | `/api/reset` | État initial du scénario choisi (efface aussi les documents en attente) |
| GET | `/api/scenarios` | Liste des scénarios |
| POST | `/api/ingest/epcis?company=<id>` | Records importés d'un document GS1 EPCIS 2.0 + état complet |
| GET | `/api/audit?company=<id>` | Journal d'audit d'une entreprise |
| GET | `/api/audit/verify` | Vérification des chaînes de hash |
| POST | `/api/ingest/document?company=<id>` | Proposition de record lue dans un document |
| POST | `/api/ingest/document/{proposal_id}/confirm` | État complet après ajout du record |

### `GET /api/state`

État complet : entreprises, records, arêtes, compteurs, alertes, déclarations.

```bash
curl localhost:8000/api/state
```

```json
{
  "companies": [
    {"id": "fournisseur", "name": "Aciers Durand", "role": "Fournisseur d'acier", "gs1_prefix": "3012345"},
    …
  ],
  "records": [
    {"id": "f-asn-01", "company": "fournisseur", "origin": "fournisseur", "kind": "asn",
     "ts": "2026-10-10T08:30:00", "label": "ASN commande BC-1001", "inputs": [],
     "gate": false, "verified": false, "payload": {}, "token": null,
     "status": "ok", "taint_path": null},
    …
  ],
  "edges": [
    {"source": "m-asn-01", "target": "m-gr-01", "cross": false},
    {"source": "f-asn-01", "target": "m-asn-01", "cross": true},
    …
  ],
  "counters": {
    "global": {"total": 193, "quarantined": 0, "ok": 193, "released": 0, "gates_blocked": 0},
    "per_company": {"fournisseur": {"total": 28, …}, …}
  },
  "alerts": [],
  "declarations": [],
  "scenario": {
    "id": "mixed", "label": "Attaque mixte",
    "description": "Le fournisseur compromis envoie un faux avis d'expédition, …",
    "compromise": {"company": "fournisseur", "since": "2026-10-10T14:00:00"}
  }
}
```

- `edges` : `cross: false` = dépendance dans un même registre (`input → record`) ; `cross: true` = envoi d'un record d'une entreprise à une autre (record sortant → copie reçue).
- `alerts[]` : `{"type", "from", "to", "tokens_count", "verified", "issued_at"}`, dans l'ordre d'émission. `type` = `"taint"` (contamination) ou `"release"` (levée). `verified` = signature acceptée par le destinataire (`false` = alerte falsifiée, rejetée).
- `declarations[]` : `{"ledger", "source", "since"}` — le registre `ledger` considère `source` comme compromise depuis `since`.
- `scenario` : scénario chargé par le dernier `POST /api/reset` (voir [Scénarios](#scénarios)). `compromise` donne la déclaration à envoyer à `POST /api/compromise` pour la démo.
- `companies[].gs1_prefix` : préfixe entreprise GS1, utilisé par l'import EPCIS pour reconnaître le propriétaire d'un lieu (SGLN / GLN).
- Lots : un record qui représente un lot porte `payload.lot` ; un lancement de production (`kind: "production_lot"`) porte aussi `payload.input_lots`, les lots consommés (comme un TransformationEvent EPCIS). Ses `inputs` sont les records de ces lots : un lot fabriqué avec un lot contaminé est contaminé.

### `POST /api/compromise`

Déclare une entreprise compromise depuis une heure donnée. L'entreprise et ses partenaires directs enregistrent la déclaration ; le reste de la chaîne est prévenu par alertes signées, de proche en proche, jusqu'à stabilisation.

On peut déclarer plusieurs entreprises. Redéclarer la même entreprise avec une autre heure garde **la plus ancienne** (une heure plus récente est journalisée mais sans effet).

Corps : `{"company": "<id>", "since": "<date ISO 8601>"}`. Une date sans fuseau est lue en heure de Paris ; une date avec fuseau (ex. `2026-10-10T12:00:00Z`, ce que renvoie `new Date().toISOString()`) est convertie.

```bash
curl -X POST localhost:8000/api/compromise \
  -H 'Content-Type: application/json' \
  -d '{"company": "fournisseur", "since": "2026-10-10T14:00:00"}'
```

```json
{
  "counters": {
    "global": {"total": 193, "quarantined": 17, "ok": 176, "released": 0, "gates_blocked": 4},
    "per_company": {
      "fournisseur":  {"total": 28, "quarantined": 4, "ok": 24, "released": 0, "gates_blocked": 0},
      "fabricant":    {"total": 63, "quarantined": 8, "ok": 55, "released": 0, "gates_blocked": 3},
      "distributeur": {"total": 28, "quarantined": 3, "ok": 25, "released": 0, "gates_blocked": 1},
      "client":       {"total": 26, "quarantined": 2, "ok": 24, "released": 0, "gates_blocked": 0}
    }
  },
  "alerts": [
    {"type": "taint", "from": "fabricant", "to": "distributeur", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:00:00"},
    {"type": "taint", "from": "fournisseur", "to": "fabricant", "tokens_count": 4, "verified": true, "issued_at": "2026-10-10T15:00:00"},
    {"type": "taint", "from": "distributeur", "to": "client", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:01:00"}
  ],
  "declarations": [
    {"ledger": "fournisseur", "source": "fournisseur", "since": "2026-10-10T14:00:00"},
    {"ledger": "fabricant", "source": "fournisseur", "since": "2026-10-10T14:00:00"}
  ],
  "records": [
    …,
    {"id": "m-pay-X", "company": "fabricant", "origin": "fabricant", "kind": "payment",
     "ts": "2026-10-10T15:10:00", "label": "Paiement facture F-9999 (RIB modifié)",
     "inputs": ["m-inv-X"], "gate": true, "verified": false,
     "payload": {"amount": 5210, "rib": "FR76 1234 5678 9000 0000 0000 666"},
     "token": null, "status": "quarantined", "taint_path": ["m-inv-X", "m-pay-X"]},
    …
  ],
  …
}
```

Erreurs : 404 si l'entreprise est inconnue, 422 si `company` ou `since` manque ou est mal formé.

### `GET /api/records/{id}/explain`

Explication en français et plan de reprise pour un record, quel que soit son statut. L'explication est produite par l'IA (Bedrock ou gabarit déterministe, voir [IA](#ia--bedrock-et-repli-mock)) ; elle ne décide jamais du blocage.

```bash
curl localhost:8000/api/records/m-pay-X/explain
```

```json
{
  "record": {"id": "m-pay-X", "status": "quarantined", "taint_path": ["m-inv-X", "m-pay-X"], …},
  "path": [
    {"id": "m-inv-X", "company": "fabricant", "origin": "fournisseur", "kind": "invoice",
     "label": "Facture reçue F-9999", "token": "7d4b6386…5efba", "status": "quarantined", …},
    {"id": "m-pay-X", …}
  ],
  "explanation": "« Paiement facture F-9999 (RIB modifié) » est mis en quarantaine : il dépend, directement ou indirectement, de « Facture reçue F-9999 » (fournisseur, 14:19), émis dans la fenêtre de compromission déclarée. Chemin de contamination : « Facture reçue F-9999 » → « Paiement facture F-9999 (RIB modifié) ». Impact : blocage d'un paiement de 5210 €. Coordonnées bancaires suspectes (RIB modifié).",
  "remediation_plan": [
    {"action": "revalidate", "label": "Revalider la donnée",
     "rationale": "Comparer le document reçu avec la source d'origine (commande, certificat) pour confirmer son authenticité."},
    {"action": "human_approval", "label": "Validation humaine", "rationale": "…"},
    {"action": "trusted_source", "label": "Reprendre depuis une source de confiance", "rationale": "…"}
  ],
  "source": "mock"
}
```

- `source` : `"bedrock"` si la réponse vient de Bedrock, `"mock"` sinon (mode par défaut, ou repli après une erreur Bedrock).
- `path` : les records de `taint_path`, dans l'ordre, au même format que `records` (vide si le record n'est pas contaminé).
- `remediation_plan[].action` : une des trois actions acceptées par `/remediate`.

Erreur : 404 si le record est inconnu.

### `POST /api/records/{id}/remediate`

Débloque un record en quarantaine : il passe en `released`, puis tout est recalculé. Ses descendants qui ne dépendaient que de lui redeviennent `ok`, y compris chez les partenaires : des alertes `release` signées partent de proche en proche jusqu'au client. La remédiation est journalisée avec `actor: "humain"`.

Corps : `{"action": "revalidate" | "human_approval" | "trusted_source"}`.

```bash
curl -X POST localhost:8000/api/records/m-gr-X/remediate \
  -H 'Content-Type: application/json' -d '{"action": "human_approval"}'
```

Réponse : l'état complet, comme `/api/state`. Après compromission puis remédiation de `m-gr-X` :

```json
{
  "counters": {"global": {"total": 193, "quarantined": 9, "ok": 183, "released": 1, "gates_blocked": 1}, …},
  "alerts": [
    …les 3 alertes taint…,
    {"type": "release", "from": "fabricant", "to": "distributeur", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:02:00"},
    {"type": "release", "from": "distributeur", "to": "client", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:03:00"}
  ],
  …
}
```

`m-lot-X`, `m-ship-X`, `d-ship-X`, `d-gr-X`, `d-out-X`, `c-ship-X` et `c-gr-X` redeviennent `ok`. Le paiement au RIB frauduleux (`m-pay-X`) reste bloqué : il ne dépend pas de `m-gr-X`.

Erreurs : 404 si le record est inconnu ; 400 si l'action est invalide ou si le record n'est pas en quarantaine.

### `POST /api/compromise/withdraw`

Retire la déclaration d'une entreprise (fausse alerte) partout où elle est enregistrée, puis recalcule. Les records qui ne sont plus suspects sortent de quarantaine et des alertes `release` partent vers l'aval. Les autres déclarations restent actives. Un record déjà remédié reste `released`.

Corps : `{"company": "<id>"}`.

```bash
curl -X POST localhost:8000/api/compromise/withdraw \
  -H 'Content-Type: application/json' -d '{"company": "fournisseur"}'
```

Réponse : l'état complet. Après compromission puis retrait : `quarantined: 0`, `declarations: []`, et 3 alertes `release` vérifiées s'ajoutent aux 3 alertes `taint`.

Erreurs : 404 si l'entreprise est inconnue ; 400 `{"detail": "aucune déclaration active pour fournisseur"}` ; 422 si `company` manque.

### `POST /api/reset`

Reconstruit un scénario (aucune déclaration, aucune alerte, journaux d'audit vides, tous les records `ok`). Corps optionnel :

```bash
curl -X POST localhost:8000/api/reset -H 'Content-Type: application/json' -d '{"scenario": "cert"}'
```

Sans corps : `mixed` (193 records). Réponse : l'état complet, avec `scenario`. Un identifiant inconnu donne 422 `{"detail": "requête invalide — scenario: Input should be 'mixed', 'rib', 'cert' or 'asn'"}`.

### `GET /api/scenarios`

```json
[
  {"id": "mixed", "label": "Attaque mixte", "description": "…",
   "compromise": {"company": "fournisseur", "since": "2026-10-10T14:00:00"}},
  {"id": "rib", "label": "Fraude au RIB", …},
  {"id": "cert", "label": "Faux certificat qualité", …},
  {"id": "asn", "label": "Faux avis d'expédition", …}
]
```

### `GET /api/audit`

Journal d'audit d'une entreprise (paramètre `company` obligatoire), en ajout seul. Chaque entrée :

| Champ | Sens |
|---|---|
| `index` | Position dans le journal, à partir de 0. |
| `ts` | Heure **du scénario** (horloge simulée qui démarre à 15:00 et avance d'une minute par tour d'alertes), pas l'heure réelle. |
| `company` | Entreprise propriétaire du journal. |
| `event` | Voir le tableau ci-dessous. |
| `actor` | `"humain"` (déclaration, retrait, remédiation, confirmation de document) ou `"règle"` (tout ce que le moteur décide seul). |
| `details` | Contenu propre à l'événement. |
| `prev_hash` | `hash` de l'entrée précédente (64 zéros pour la première). |
| `hash` | `sha256(prev_hash + JSON canonique de l'entrée sans "hash")`, JSON trié, sans espaces, UTF-8. |

| `event` | `details` |
|---|---|
| `declaration` | `source`, `since` demandé, `effective_since` (la plus ancienne retenue) |
| `declaration_withdrawn` | `source`, `since` retiré |
| `alert_sent` | `type`, `from`, `to`, `tokens`, `issued_at`, `signature` |
| `alert_received` | idem + `verified` (bool) et `outcome` (`"appliquée"` ou `"rejetée : signature invalide"`) |
| `quarantine` | `record`, `rule`, `taint_path`, `gate`. `rule` : `source_compromise` (émis par une source déclarée, après `since`), `alerte_verifiee` (jeton signalé par un partenaire), `dependance` (dépend d'un record contaminé) |
| `remediation` | `record`, `action`, `taint_path` au moment de la remédiation |
| `release` | `record`, `reason` : sortie de quarantaine décidée par le moteur (après remédiation en amont, levée reçue ou retrait) |
| `document_confirmed` | `record`, `proposal`, `origin`, `kind`, `inputs`, `extraction_source` (`mock` ou `bedrock`), `confidence` : document lu puis confirmé (`POST /api/ingest/document/{id}/confirm`) |
| `epcis_import` | `records` (ids ajoutés), `events` (événements du document), `ignored` (nombre ignoré) : import EPCIS (`POST /api/ingest/epcis`) |

Le journal d'une entreprise ne contient que ses propres records et des jetons opaques : jamais les identifiants ni les données d'un partenaire.

```bash
curl 'localhost:8000/api/audit?company=distributeur'
```

```json
{
  "company": "distributeur",
  "head": "d70487f0…6e466",
  "entries": [
    {"index": 0, "ts": "2026-10-10T15:01:00", "company": "distributeur", "event": "alert_received", "actor": "règle",
     "details": {"type": "taint", "from": "fabricant", "to": "distributeur", "tokens": ["3192bdcb…8c06"],
                 "issued_at": "2026-10-10T15:00:00", "signature": "e6f021d6…6c0d", "verified": true, "outcome": "appliquée"},
     "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000", "hash": "d845ec03…e3b3"},
    {"index": 1, "ts": "2026-10-10T15:01:00", "company": "distributeur", "event": "quarantine", "actor": "règle",
     "details": {"record": "d-ship-X", "rule": "alerte_verifiee", "taint_path": ["d-ship-X"], "gate": false},
     "prev_hash": "d845ec03…e3b3", "hash": "79d32588…4299"},
    …
  ]
}
```

Erreurs : 404 si l'entreprise est inconnue ; 422 si `company` manque.

### `GET /api/audit/verify`

Recalcule toutes les chaînes de hash (ou une seule avec `?company=<id>`) et dit si elles sont intactes.

```json
{
  "ok": false,
  "first_broken": {"company": "distributeur", "index": 2},
  "journals": [
    {"company": "fournisseur", "ok": true, "entries": 6, "first_broken_index": null, "head": "eb3ef24b…b280"},
    {"company": "distributeur", "ok": false, "entries": 10, "first_broken_index": 2, "head": "d70487f0…6e466"},
    …
  ]
}
```

- `ok` : toutes les chaînes vérifiées sont intactes. `first_broken` : `null` dans ce cas.
- `first_broken_index` : première entrée dont `index`, `prev_hash` ou `hash` ne correspond plus. Une entrée modifiée, supprimée ou déplacée est détectée.
- Limite : la chaîne prouve qu'aucune entrée n'a été modifiée **sans recalculer tous les hash suivants**. Pour se protéger aussi contre ce cas, il faut publier `head` ailleurs (chez un partenaire ou sur une blockchain) ; ce n'est pas encore fait.

Erreur : 404 si l'entreprise est inconnue.

### `GET /api/timeline`

Rejeu pas à pas de **la dernière action** (`POST /api/compromise`, `…/compromise/withdraw`, `…/records/{id}/remediate`, ou une ingestion confirmée). Les étapes sont lues depuis les journaux d'audit chaînés : la timeline ne change aucun résultat du moteur, elle l'instrumente. Vide (`{"steps": []}`) juste après un reset.

```json
{"steps": [
  {"n": 1, "ts": "2026-10-10T15:00:00", "type": "declaration",
   "company": "fournisseur", "record": null, "parent": null, "gate": false,
   "label": null, "rule": null, "alert": null,
   "counters": {"quarantined": 0, "gates_blocked": 0,
                "amount_blocked": 0, "amount_flowing": 121380},
   "text": "fournisseur déclarée compromise depuis 2026-10-10 14:00 — registre fournisseur."},
  {"n": 12, "ts": "2026-10-10T15:00:00", "type": "gate_blocked",
   "company": "fabricant", "record": "m-pay-X", "parent": "m-inv-X",
   "gate": true, "label": "Paiement facture F-9999 (RIB modifié)",
   "rule": "dependance", "alert": null,
   "counters": {"quarantined": 8, "gates_blocked": 3,
                "amount_blocked": 10420, "amount_flowing": 110960},
   "text": "Action irréversible bloquée : « Paiement facture F-9999 (RIB modifié) » (5210 €) (fabricant)."}
]}
```

| `type` | Sens |
|---|---|
| `declaration` | Une déclaration de compromission enregistrée sur ce registre (`company` = registre, la source est dans `text`). |
| `seed` | Record contaminé directement par une règle : `rule` = `source_compromise` (origine déclarée, `ts` dans la fenêtre) ou `alerte_verifiee` (jeton d'une alerte vérifiée). |
| `quarantine` | Record contaminé par dépendance ; `parent` = record contaminé dont il dérive. |
| `gate_blocked` | Quarantaine d'un `gate` (action irréversible). |
| `alert_sent` / `alert_received` | Alerte signée émise / reçue-vérifiée. `alert.links` donne les paires `[record_émis, record_reçu]` des jetons — les arêtes `cross: true` à animer. `alert.verified` = `false` si la signature est rejetée. |
| `release` | Record sorti de quarantaine au recalcul (ne dépend plus d'une donnée suspecte). |
| `remediation` | Action humaine de remédiation (le record passe `released`). |
| `withdrawal` | Déclaration retirée (fausse alerte). |

- `counters` donne l'impact **cumulé à cette étape** : rejouer les étapes dans l'ordre reproduit l'état final de `/api/state` (y compris les cascades de libération après remédiation ou retrait).
- `text` est une phrase française prête pour l'affichage.

### `GET /api/events?speed=<s>`

Diffuse la même séquence en **Server-Sent Events** (`text/event-stream`) : un événement `data:` par étape (même charge utile JSON qu'une entrée de `/api/timeline`), précédé d'un commentaire `: rejeu firebreak`, flux fermé en fin de séquence. `speed` = pause en secondes entre événements (défaut `0.5`, `0` pour tout d'un coup, max `10`).

```js
const es = new EventSource('/api/events?speed=0.8');
es.onmessage = (e) => {
  const step = JSON.parse(e.data);
  console.log(step.n, step.type, step.text);
  // step.counters = {quarantined, gates_blocked, amount_blocked, amount_flowing}
  // amount_* = montant des paiements (kind == "payment") bloqués / qui continuent
  // step.alert.links = [[record_emis, record_recu], …] → arêtes cross à animer
};
// le flux se ferme tout seul en fin de séquence
```

L'état final reconstruit en appliquant les étapes dans l'ordre est identique à `GET /api/state` (vérifié par `tests/test_timeline.py`).

### `GET /api/compare`

**Avec vs sans Firebreak**, mesuré sur la simulation courante et ses déclarations actives (400 `{"detail": "aucune déclaration active"}` s'il n'y en a pas). Deux politiques comparées sur la **même vérité terrain** :

- **Vérité terrain** : records réellement contaminés — BFS depuis les records **émis** par la source dans son propre registre (`origin == company`) après `since`, le long des dépendances enregistrées (`inputs` + envois inter-entreprises) ; un record `verified` n'est jamais contaminé et arrête la propagation. Indépendante des statuts (la remédiation ne la change pas).
- **`without` (politique B, « sans Firebreak »)** : pour chaque déclaration, on coupe la source et ses **clients directs** (ceux qui ont reçu ses données) — tout record de leurs registres avec `ts >= since` est bloqué. `scope` donne ce périmètre par source.
- **`with` (politique C, « avec Firebreak »)** : les records actuellement `quarantined`.

Même fonction de métriques des deux côtés : `blocked`, `healthy_blocked` (bloqués hors vérité = collatéraux), `leaked`/`leaked_ids` (contaminés non bloqués = fuites), `gates_blocked`, `payments_blocked_eur`/`payments_flowing_eur` (paiements seulement), `activity_preserved_pct` (part des opérations saines non bloquées), `precision`, `recall` (null quand indéfini), `companies_hit`, `blocked_ids`.

```json
{"declarations":[{"company":"fournisseur","since":"2026-10-10T14:00:00"}],
 "truth":{"contaminated":17,"definition":"Records réellement contaminés : …"},
 "without":{"title":"Sans Firebreak","policy":"B",
   "subtitle":"On coupe le fournisseur et ses clients directs depuis 14 h",
   "scope":{"fournisseur":["fournisseur","fabricant"]},
   "blocked":54,"healthy_blocked":42,"leaked":5,
   "leaked_ids":[{"id":"d-ship-X","label":"Expédition reçue LOT-999","company":"distributeur"},…],
   "gates_blocked":18,"payments_blocked_eur":16910,"payments_flowing_eur":80402,
   "activity_preserved_pct":76.1,"precision":0.222,"recall":0.706,
   "companies_hit":["fabricant","fournisseur"],"blocked_ids":["f-asn-08",…]},
 "with":{"title":"Avec Firebreak","policy":"C",
   "subtitle":"On gèle seulement les opérations contaminées",
   "blocked":17,"healthy_blocked":0,"leaked":0,"leaked_ids":[],
   "gates_blocked":4,"payments_blocked_eur":5210,"payments_flowing_eur":92102,
   "activity_preserved_pct":100.0,"precision":1.0,"recall":1.0,
   "companies_hit":["client","distributeur","fabricant","fournisseur"],"blocked_ids":[…]},
 "healthy_blocked_ratio":null,
 "bench":{"p_values":["0.0","0.1","0.2","0.3"],"seeds_per_group":500,
   "command":"uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3",
   "groups":{"p0.0:B":{"seeds":500,"healthy_blocked_mean":43.182,"leaks_mean":0.662,"recall_mean":0.985,"activity_preserved_mean":0.838},
             "p0.0:C":{"seeds":500,"healthy_blocked_mean":9.616,"leaks_mean":0.0,"recall_mean":1.0,"activity_preserved_mean":0.964},…}},
 "real_world":[{"name":"Jaguar Land Rover","date":"septembre 2025","text":"…","source":"https://www.reuters.com/…"},{…}]}
```

- `healthy_blocked_ratio` = `without.healthy_blocked / with.healthy_blocked` (`null` si 0 — la comparaison est alors « infinie »).
- `bench` : agrégat de `bench/results.csv` (moyenne par graine, politiques B et C, à `p=0` et au `p` max présent) ; `null` si le fichier manque.
- `real_world` : exemples réels de coupure totale, avec liens sources.

### `POST /api/ingest/document?company=<id>`

Lit un document fournisseur reçu par l'entreprise `company` (bon de commande, avis d'expédition, facture, changement de RIB) et renvoie une **proposition** de record. Rien n'est ajouté au registre avant `…/confirm`.

Corps : le fichier brut, au choix :

| Content-Type | Contenu |
|---|---|
| `application/pdf` | PDF avec texte (un scan sans texte est refusé) |
| `message/rfc822` | Mail `.eml` (en-têtes + corps texte) |
| `text/plain` | Texte collé |
| `application/json` | `{"text": "<texte du mail>"}` |

Paramètre optionnel `received_at` (ISO 8601) : heure de réception du document. Par défaut : maintenant, heure de Paris. C'est cette heure qui est comparée à la fenêtre de compromission. Taille max : 2 Mo.

Côté interface : `fetch(url, {method: "POST", body: file, headers: {"Content-Type": file.type}})`.

```bash
curl 'localhost:8000/api/ingest/document?company=fabricant&received_at=2026-10-10T16:00:00' \
  -H 'Content-Type: application/pdf' --data-binary @assets/samples/facture-rib-modifie.pdf
```

```json
{
  "id": "doc-01", "status": "pending", "source": "mock", "confidence": 0.9, "missing": [],
  "record": {
    "id": "m-doc-01", "company": "fabricant", "origin": "fournisseur", "kind": "invoice",
    "ts": "2026-10-10T16:00:00", "label": "Facture reçue F-9999 — nouveau RIB",
    "inputs": [], "gate": false,
    "payload": {"amount": 5210, "rib": "FR76 1234 5678 9000 0000 0000 666",
                "previous_rib": "FR76 3000 4028 3798 7654 3210 085",
                "bank_details_change": true, "references": ["F-9999", "BC-9999"],
                "dates": ["2026-10-10", "2026-10-12"], "rib_unknown_for_origin": true}
  }
}
```

- `record.kind` : `purchase_order`, `asn`, `invoice`, `bank_details_change`, ou `null` si non reconnu.
- `record.origin` : émetteur reconnu à son nom dans le document, ou `null`.
- `record.payload` : seuls les champs trouvés sont présents (`references` et `dates` toujours, éventuellement vides). `bank_details_change: true` si le document annonce un nouveau RIB **ou** si le RIB n'a jamais été vu pour cet émetteur dans le registre (`rib_unknown_for_origin: true`).
- `confidence` (0 à 1) : en mode mock, part des champs attendus trouvés pour ce type, plafonnée à 0,9 ; en mode Bedrock, la confiance donnée par le modèle.
- `missing` : champs attendus pour ce type mais absents (ex. `["amount"]`).

Erreurs : 404 si l'entreprise est inconnue ; 400 si le document est vide, trop gros, ou un PDF illisible ou sans texte ; 422 si le JSON n'a pas de champ `text`.

### `POST /api/ingest/document/{proposal_id}/confirm`

Ajoute le record proposé au registre, puis recalcule tout : le record passe par les mêmes règles que les autres (émis par une source compromise après `since` → quarantaine).

Corps optionnel : `{"origin": "<id>", "inputs": ["<id de record du même registre>", …]}` pour corriger l'émetteur ou rattacher le document à des records existants.

```bash
curl -X POST localhost:8000/api/ingest/document/doc-01/confirm
```

La confirmation est inscrite dans le journal d'audit du registre (`event: "document_confirmed"`, `actor: "humain"`, avec la source et la confiance de l'extraction).

Réponse : l'état complet. Après compromission du fournisseur depuis 14 h, la facture ci-dessus arrive en `quarantined` avec `taint_path: ["m-doc-01"]` (18 bloqués sur 146).

Erreurs : 404 si la proposition est inconnue ; 400 si elle est déjà confirmée, si l'émetteur ou le type n'est pas reconnu, ou si un `inputs` n'existe pas dans le registre.

Documents d'exemple dans `assets/samples/` : `facture-rib-modifie.pdf` (facture F-9999 avec nouveau RIB), `avis-expedition.eml` (BC-1009), `bon-de-commande.txt` (BC-7001, du distributeur au fabricant).

### `POST /api/ingest/epcis?company=<id>`

Importe un document **GS1 EPCIS 2.0** (JSON / JSON-LD) dans le registre de `company`. Les données sont structurées : pas d'étape de confirmation, les records sont ajoutés tout de suite puis passent par les mêmes règles que les autres (recalcul et alertes). Exemple : [`assets/samples/epcis-sample.json`](../assets/samples/epcis-sample.json) (11 événements, registre du fabricant).

```bash
curl -X POST 'localhost:8000/api/ingest/epcis?company=fabricant' \
  -H 'Content-Type: application/json' --data @assets/samples/epcis-sample.json
```

```json
{
  "events": 11,
  "imported": [
    {"id": "m-epcis-01", "company": "fabricant", "origin": "fournisseur", "kind": "asn",
     "ts": "2026-10-10T09:00:00", "label": "Avis d'expédition Aciers Durand — COIL-12",
     "inputs": [], "gate": false, "verified": false,
     "payload": {"epcis": {"event_id": "urn:uuid:…", "type": "ObjectEvent", "biz_step": "shipping", …},
                 "epc_inputs": ["urn:epc:class:lgtin:3012345.012345.COIL-12"],
                 "epc_outputs": ["urn:epc:class:lgtin:3012345.012345.COIL-12"], "lot": "COIL-12"},
     "token": null, "status": "ok", "taint_path": null},
    …
    {"id": "m-epcis-08", "kind": "production_lot", "label": "Transformation COIL-77 + COIL-12 → LOT-801",
     "inputs": ["m-epcis-05", "m-epcis-02"], "gate": true,
     "payload": {…, "lot": "LOT-801", "input_lots": ["COIL-77", "COIL-12"]}, …},
    …
  ],
  "ignored": [],
  "state": {…}
}
```

Sous-ensemble géré (tout le reste est ignoré et listé dans `ignored`, avec `index`, `type` et `reason`) :

| Élément EPCIS | Traitement |
|---|---|
| Document | `type: "EPCISDocument"` et `epcisBody.eventList` obligatoires (sinon 400). 1 000 événements max. |
| `ObjectEvent` | Objets = `epcList` + `quantityList[].epcClass`, consommés et produits (rien de produit si `action: "DELETE"`). |
| `AggregationEvent` | Consomme `childEPCs` / `childQuantityList` (et `parentID`), produit `parentID` et les enfants. |
| `TransformationEvent` | Consomme `inputEPCList` / `inputQuantityList`, produit `outputEPCList` / `outputQuantityList` → `kind: "production_lot"`, `payload.input_lots`. |
| `AssociationEvent`, `TransactionEvent`, `errorDeclaration` | Ignorés. |
| `eventTime` | Converti en heure de Paris ; absent ou invalide → ignoré. Les événements sont traités dans l'ordre de `eventTime`. |
| `bizLocation` (sinon `readPoint`) | `origin` = entreprise dont le `gs1_prefix` commence l'identifiant (`urn:epc:id:sgln:…` ou Digital Link `/414/`). Pas de lieu : l'entreprise qui importe. Lieu inconnu : ignoré. |
| `bizStep` (URN, URL ou terme seul) | `shipping` → `shipment` (`asn` si fait par un partenaire), `receiving` / `accepting` → `goods_receipt`, `inspecting` → `quality_check`, `storing` → `stock_entry`, `packing` → `packing`, autre → `epcis_event`. |
| `disposition`, `sourceList`, `destinationList`, `eventID` | Recopiés dans `payload.epcis`. |

Règles :

- `inputs` = le dernier record qui a produit chacun des objets consommés, y compris les records d'un import précédent (`payload.epc_outputs`) ;
- `gate: true` pour une expédition ou une transformation faite par l'entreprise elle-même ;
- `verified: true` pour un contrôle (`inspecting`) `conformant` fait par l'entreprise elle-même : il arrête la propagation ;
- lots : `payload.lot` = lot de la première classe LGTIN produite (`urn:epc:class:lgtin:…` ou Digital Link `/10/`).

Après import de l'exemple puis compromission du fournisseur depuis 14 h : 7 des 11 records importés sont bloqués (`m-epcis-03` à `06`, la transformation `m-epcis-08` → LOT-801, la palettisation et l'expédition). Le contrôle conforme de COIL-78 (`m-epcis-07`) protège LOT-802 (`m-epcis-09`). L'import est inscrit au journal d'audit (`event: "epcis_import"`).

Erreurs : 404 si l'entreprise est inconnue ; 400 si ce n'est pas un document EPCIS.

## IA : Bedrock et repli mock

L'IA **ne décide jamais d'un blocage**. Elle explique (`/explain`), propose un plan de reprise et extrait les données des documents. Toute donnée extraite n'entre dans le registre qu'après confirmation humaine, puis passe par les règles du graphe.

| Variable | Défaut | Rôle |
|---|---|---|
| `FIREBREAK_AI` | `mock` | `bedrock` pour utiliser AWS Bedrock, `mock` pour les gabarits et les regex hors ligne. |
| `FIREBREAK_BEDROCK_MODEL` | `anthropic.claude-3-haiku-20240307-v1:0` | Identifiant du modèle ou du profil d'inférence Bedrock (Converse API). |
| `AWS_REGION` | — | Région Bedrock, ex. `eu-west-3`. |
| Identifiants AWS | — | Chaîne standard de boto3 : `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`, rôle… Jamais dans le dépôt, jamais journalisés. |

```bash
FIREBREAK_AI=bedrock AWS_REGION=eu-west-3 AWS_PROFILE=hackathon \
  uv run uvicorn firebreak.api:app --port 8000
```

Repli automatique sur le mock, avec `source: "mock"` dans la réponse et un avertissement dans les logs du serveur (cause seulement, sans identifiants), si :

- les identifiants ou la région manquent, ou boto3 lève une erreur ;
- Bedrock ne répond pas en 8 s ;
- la réponse n'est pas un objet JSON valide ;
- l'explication propose une action hors de `revalidate`, `human_approval`, `trusted_source` ;
- l'extraction donne un type ou un émetteur hors liste, ou un RIB, une référence ou une date qui n'apparaît pas dans le document.

Le prompt d'explication ne contient que le record, les records de son `taint_path` et les règles appliquées (seed, propagation, gate…), pas le reste du registre. Le prompt d'extraction contient le texte du document (12 000 caractères max) et la liste des entreprises.

## Scénarios

Quatre entreprises : `fournisseur` (Aciers Durand) → `fabricant` (Mécano Précision Loire) → `distributeur` (Logidis Rhône) → `client` (Bâtiments Azur). Tous les scénarios partagent la même matinée : 7 livraisons propres avant 14 h (de la bobine reçue au paiement du client) et des opérations internes. Le fournisseur est compromis depuis 14 h ; seule l'attaque change. Chiffres après `{"company": "fournisseur", "since": "2026-10-10T14:00:00"}` (vérifiés par `tests/test_scenarios.py`) :

| `id` | Attaque | Records | Bloqués | Actions irréversibles bloquées | Ce qui arrête la propagation |
|---|---|---|---|---|---|
| `mixed` (défaut) | Faux ASN, faux certificat et facture au RIB modifié | 193 | 17 | `m-lot-X`, `m-pay-X`, `m-ship-X`, `d-out-X` | Réception BC-1008 contrôlée physiquement (`m-gr-08`) |
| `rib` | Mail de changement de RIB → fiche fournisseur modifiée → paiement | 185 | 8 | `m-pay-X` | Contre-appel au numéro connu pour la facture F-3008 (`m-call-08`) : son paiement continue |
| `cert` | Faux certificat qualité sur une bobine réelle (COIL-210) | 193 | 13 | `m-lot-901`, `m-asm-950`, `m-ship-950`, `d-out-950` | Réception pesée de COIL-210 (`m-gr-X`) : la bobine existe, seul le certificat est faux. LOT-902 (autres bobines) et son expédition continuent |
| `asn` | Faux avis d'expédition (COIL-299 n'existe pas) | 190 | 13 | `m-lot-X`, `m-ship-X`, `d-out-X` | Réception COIL-108 contrôlée physiquement (`m-gr-08`) : LOT-908 continue |

- `rib` reste chez le fabricant : aucun objet physique ne part vers l'aval.
- `cert` montre la généalogie des lots : LOT-901 est fabriqué avec COIL-210, puis le sous-ensemble ASM-950 avec LOT-901 et LOT-902. ASM-950 est bloqué jusqu'au client ; LOT-902 seul continue.
- `asn` bloque la production lancée sur un stock fantôme, la réservation chez le distributeur et le planning du chantier client.

### Détail du scénario `mixed`

Le fournisseur est compromis depuis 14 h et envoie un faux avis d'expédition, un faux certificat et une facture avec RIB modifié. Une livraison légitime reçue après 14 h est contrôlée physiquement (`m-gr-08`, `verified: true`) : elle arrête la propagation.

Après `{"company": "fournisseur", "since": "2026-10-10T14:00:00"}` : 17 records bloqués sur 193, 176 continuent, 4 actions irréversibles bloquées (`m-lot-X`, `m-pay-X`, `m-ship-X`, `d-out-X`), contamination jusqu'au client.
