# FIREBREAK — Contrat de l'API

Version du contrat : **1.0.0** (figée à l'étape 1 du [plan](plan.md)). Les étapes suivantes peuvent **ajouter** des champs ou des endpoints, jamais en retirer ou en renommer sans mettre ce document à jour.

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
| **alerte** | Message signé (Ed25519) d'une entreprise à un partenaire. Il ne contient que des jetons opaques : ni libellé, ni montant, ni payload. |

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

« Opérations qui continuent » à l'écran = `ok + released`.

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
| GET | `/api/records/{id}/explain` | Explication et plan de reprise |
| POST | `/api/records/{id}/remediate` | État complet après recalcul |
| POST | `/api/reset` | État initial |

### `GET /api/state`

État complet : entreprises, records, arêtes, compteurs, alertes, déclarations.

```bash
curl localhost:8000/api/state
```

```json
{
  "companies": [
    {"id": "fournisseur", "name": "Aciers Durand", "role": "Fournisseur d'acier"},
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
    "global": {"total": 145, "quarantined": 0, "ok": 145, "released": 0, "gates_blocked": 0},
    "per_company": {"fournisseur": {"total": 28, …}, …}
  },
  "alerts": [],
  "declarations": []
}
```

- `edges` : `cross: false` = dépendance dans un même registre (`input → record`) ; `cross: true` = envoi d'un record d'une entreprise à une autre (record sortant → copie reçue).
- `alerts[]` : `{"from", "to", "tokens_count", "verified", "issued_at"}`. `verified` = signature acceptée par le destinataire (`false` = alerte falsifiée, rejetée).
- `declarations[]` : `{"ledger", "source", "since"}` — le registre `ledger` considère `source` comme compromise depuis `since`.

### `POST /api/compromise`

Déclare une entreprise compromise depuis une heure donnée. L'entreprise et ses partenaires directs enregistrent la déclaration ; le reste de la chaîne est prévenu par alertes signées, de proche en proche, jusqu'à stabilisation.

Corps : `{"company": "<id>", "since": "<date ISO 8601>"}`. Une date sans fuseau est lue en heure de Paris ; une date avec fuseau (ex. `2026-10-10T12:00:00Z`, ce que renvoie `new Date().toISOString()`) est convertie.

```bash
curl -X POST localhost:8000/api/compromise \
  -H 'Content-Type: application/json' \
  -d '{"company": "fournisseur", "since": "2026-10-10T14:00:00"}'
```

```json
{
  "counters": {
    "global": {"total": 145, "quarantined": 17, "ok": 128, "released": 0, "gates_blocked": 4},
    "per_company": {
      "fournisseur":  {"total": 28, "quarantined": 4, "ok": 24, "released": 0, "gates_blocked": 0},
      "fabricant":    {"total": 63, "quarantined": 8, "ok": 55, "released": 0, "gates_blocked": 3},
      "distributeur": {"total": 28, "quarantined": 3, "ok": 25, "released": 0, "gates_blocked": 1},
      "client":       {"total": 26, "quarantined": 2, "ok": 24, "released": 0, "gates_blocked": 0}
    }
  },
  "alerts": [
    {"from": "fabricant", "to": "distributeur", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:00:00"},
    {"from": "fournisseur", "to": "fabricant", "tokens_count": 4, "verified": true, "issued_at": "2026-10-10T15:00:00"},
    {"from": "distributeur", "to": "client", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:01:00"}
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

Explication en français et plan de reprise pour un record, quel que soit son statut. L'explication est produite par l'IA (actuellement un gabarit déterministe, `MockExplainer`) ; elle ne décide jamais du blocage.

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
  ]
}
```

- `path` : les records de `taint_path`, dans l'ordre, au même format que `records` (vide si le record n'est pas contaminé).
- `remediation_plan[].action` : une des trois actions acceptées par `/remediate`.

Erreur : 404 si le record est inconnu.

### `POST /api/records/{id}/remediate`

Débloque un record en quarantaine : il passe en `released`, puis tout est recalculé. Ses descendants qui ne dépendaient que de lui redeviennent `ok`.

Corps : `{"action": "revalidate" | "human_approval" | "trusted_source"}`.

```bash
curl -X POST localhost:8000/api/records/m-gr-X/remediate \
  -H 'Content-Type: application/json' -d '{"action": "human_approval"}'
```

Réponse : l'état complet, comme `/api/state`. Après compromission puis remédiation de `m-gr-X` :

```json
{"counters": {"global": {"total": 145, "quarantined": 14, "ok": 130, "released": 1, "gates_blocked": 2}, …}, …}
```

Limite actuelle (corrigée à l'étape 2) : le déblocage ne se propage pas encore aux partenaires. Ici `m-lot-X` et `m-ship-X` redeviennent `ok`, mais `d-ship-X` (distributeur) et `c-ship-X` (client) restent en quarantaine.

Erreurs : 404 si le record est inconnu ; 400 si l'action est invalide ou si le record n'est pas en quarantaine.

### `POST /api/reset`

Reconstruit le scénario de départ (aucune déclaration, aucune alerte, 145 records `ok`). Réponse : l'état complet.

## Scénario par défaut

Quatre entreprises : `fournisseur` (Aciers Durand) → `fabricant` (Mécano Précision Loire) → `distributeur` (Logidis Rhône) → `client` (Bâtiments Azur). Le fournisseur est compromis depuis 14 h et envoie un faux avis d'expédition, un faux certificat et une facture avec RIB modifié. Une livraison légitime reçue après 14 h est contrôlée physiquement (`m-gr-08`, `verified: true`) : elle arrête la propagation.

Après `{"company": "fournisseur", "since": "2026-10-10T14:00:00"}` : 17 records bloqués sur 145, 128 continuent, 4 actions irréversibles bloquées (`m-lot-X`, `m-pay-X`, `m-ship-X`, `d-out-X`), contamination jusqu'au client.
