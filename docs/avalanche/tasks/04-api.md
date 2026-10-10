# Tâche 04 — Brancher la chaîne dans l'API

Lis d'abord `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md`, `docs/api.md`, le rapport de la tâche 03, puis `src/firebreak/api.py` et `src/firebreak/schemas.py`.

## Règle d'or

Avec `FIREBREAK_CHAIN=off`, **toutes les réponses existantes sont identiques** à `main`, à l'exception de champs optionnels ajoutés qui valent `null`. Les tests existants ne changent pas.

## Câblage dans `api.py`

- Au chargement : `chain = get_chain_client(load_chain_config())`, `anchorer = Anchorer(chain)`, `anchorer.on_new_simulation(sim)`.
- Après chaque action qui modifie l'état, **sous le verrou existant** `_lock`, appeler `anchorer.after_action(sim, "<action>")` : `POST /api/compromise`, `/api/compromise/withdraw`, `/api/records/{id}/remediate`, `/api/demo/step`, document confirmé, import EPCIS. Après `POST /api/reset` : `on_new_simulation`.
- `after_action` ne fait que mettre en file : mesurer que `/api/state` reste < 200 ms et `POST /api/compromise` n'augmente pas de plus de 20 ms en mode `tester`.

## Nouveaux endpoints (modèles Pydantic dans `schemas.py`)

| Endpoint | Réponse |
|---|---|
| `GET /api/chain/status` | `ChainStatusOut` : `mode`, `connected`, `chain_id`, `contract`, `explorer_url`, `run_id`, `last_block`, `queue: {pending, sent, confirmed, failed}` |
| `GET /api/chain/anchors?kind=&company=` | `list[AnchorOut]` (champs de `AnchorRecord`, tri par `created_at`) |
| `POST /api/chain/anchor` | Ancre maintenant les têtes de tous les journaux, attend jusqu'à 5 s (`flush`), renvoie la liste des ancrages créés. 409 si mode `off`. |

## Ajout à `GET /api/audit/verify`

Dans chaque élément de `journals`, un champ optionnel `onchain` (null si mode `off` ou rien d'ancré) :

```json
"onchain": {
  "anchored_head": "…", "anchored_entries": 25,
  "block": 1234, "tx_hash": "0x…", "explorer_link": "https://…/tx/0x…",
  "matches": true
}
```

`matches` = le préfixe du journal local de longueur `anchored_entries` a pour dernier hash `anchored_head`. Au niveau racine, ajouter `onchain_ok: bool | null` (tous les journaux ancrés correspondent).

## Démo de réécriture — `POST /api/demo/rewrite`

- **Disponible seulement si `FIREBREAK_DEMO=1`**, sinon 404.
- Corps : `{"company": "fabricant", "drop_event": "alert_received"}`. Supprime la première entrée de ce type du journal de cette entreprise **et recalcule tous les hash suivants** pour que la chaîne locale reste cohérente.
- Pour ne pas toucher `audit.py`, implémente la réécriture dans un module de démo (`src/firebreak/chain/tamper.py`) qui reconstruit un `AuditLog` à partir des entrées modifiées et le remplace dans le ledger. Si ce n'est pas possible sans modifier `audit.py` ou `engine.py`, arrête-toi et décris ce qu'il faudrait changer (choix à faire avec Yann).
- Attendu ensuite : `/api/audit/verify` → `ok: true` (local) mais `onchain_ok: false`, avec `matches: false` sur le fabricant.

## Docs

- `docs/api.md` : section « Avalanche L1 » avec chaque endpoint, un exemple de réponse réelle (mode `tester`), le champ `onchain`, et les variables d'environnement. Monter la version du contrat (mineure).
- `docs/avalanche/README.md` : cocher la tâche.

## Tests — `tests/test_chain_api.py`

- Mode `off` : `/api/chain/status` → `mode: "off"` ; `/api/audit/verify` identique à avant + `onchain: null`.
- Mode `tester` : compromise → `flush` → anchors confirmés (alertes, acquittements, déclaration, audits) → `verify` avec `matches: true` partout.
- Réécriture : `FIREBREAK_DEMO=1`, après ancrage, `rewrite` → `ok: true`, `onchain_ok: false`.
- Sans `FIREBREAK_DEMO` : `rewrite` → 404.
- Le test de bout en bout existant de la démo passe toujours.

## Fini quand

- `uv run pytest -q` vert.
- Commit `chain: endpoints /api/chain, vérification on-chain de l'audit, démo de réécriture`.
