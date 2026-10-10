# Tâche 03 — Client Python et ancrage

Lis d'abord `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md`, le rapport de la tâche 01, puis `src/firebreak/audit.py`, `src/firebreak/federation.py` et `src/firebreak/simulation.py` (lecture seule).

## Objectif

Une couche `src/firebreak/chain/` qui transforme les actions de Firebreak en écritures on-chain, **sans jamais ralentir ni casser** le moteur ou l'API.

## `config.py`

- `load_chain_config() -> ChainConfig` (dataclass figée) : lit les variables de `docs/avalanche/README.md` depuis `os.environ`, après avoir chargé `.env.local` à la racine **s'il existe** avec un petit parseur maison (`CLE=valeur`, lignes `#` ignorées, n'écrase pas une variable déjà présente). Pas de nouvelle dépendance.
- `mode` ∈ `off | tester | l1`, défaut `off`. Valeur inconnue → `off` + avertissement.
- `__repr__` ne montre jamais le mnémonique.

## `ids.py` (fonctions pures)

- `company_id(cid: str) -> bytes` : `sha256(b"firebreak:company:" + cid)`, 32 octets.
- `run_id() -> bytes` : 32 octets aléatoires, un par simulation.
- `alert_hash(alert: Alert) -> bytes` : `sha256(json canonique de alert.payload() + "|" + alert.signature)`. Même canonisation que `federation._canonical` (réimplémente-la à l'identique plutôt que d'importer un nom privé, et ajoute un test qui compare les deux).
- `declaration_hash(company, since_iso, declarer) -> bytes`.
- `hex32(b: bytes) -> str` : `0x` + 64 hex.

## `client.py`

```python
class ChainClient(Protocol):
    mode: str
    def submit(self, op: ChainOp) -> AnchorRecord: ...      # non bloquant : met en file, retourne status="pending"
    def anchors(self) -> list[AnchorRecord]: ...
    def status(self) -> dict: ...
    def read_audit_anchor(self, run_id: bytes, company: str) -> dict | None: ...  # lecture on-chain, timeout court
    def flush(self, timeout: float) -> None: ...             # pour les tests et POST /api/chain/anchor
```

- `ChainOp` : `kind` (`audit` | `alert` | `ack` | `incident` | `incident_withdrawn`), `company` (qui signe la tx), arguments du contrat.
- `AnchorRecord` : `id`, `kind`, `company`, `hash` (hex), `status` (`pending` | `sent` | `confirmed` | `failed`), `tx_hash`, `block`, `error` (court, sans secret), `created_at`, `explorer_link`.
- **`NullChain`** (mode `off`) : `submit` renvoie un enregistrement `status="disabled"` et ne fait rien. N'importe pas `web3`.
- **`Web3Chain`** (modes `tester` et `l1`) : un **thread d'envoi unique** consomme une `queue.Queue`. Un compte par entreprise (dérivé du mnémonique comme dans la tâche 02, test : mnémonique public) ; gestion des nonces par compte ; `wait_for_transaction_receipt` avec timeout ; 2 tentatives puis `failed`. Toute exception est capturée et stockée dans `error`. `tester` utilise `EthereumTesterProvider` et déploie le contrat + enregistre les membres au démarrage (pratique pour développer sans L1).
- `get_chain_client(config) -> ChainClient` : fabrique selon le mode. En mode `l1`, si le RPC est injoignable ou si le chainId ne correspond pas, retourne un client dont `status()["connected"]` est `false` et dont tous les `submit` finissent en `failed` — jamais une exception au démarrage du serveur.

## `anchoring.py`

```python
class Anchorer:
    def __init__(self, client: ChainClient): ...
    def on_new_simulation(self, sim) -> None              # nouveau run_id, mémorise les positions
    def after_action(self, sim, action: str) -> None      # appelé par l'API après compromise / withdraw / remediate / reset / demo step
```

`after_action` :
1. Pour chaque **nouvelle** alerte de `sim.federation.alerts` depuis le dernier appel : `anchorAlert` signé par l'émetteur ; si l'alerte est `verified` côté destinataire, `acknowledgeAlert` signé par le destinataire.
2. Pour chaque **nouvelle** entrée d'audit `declaration` / `declaration_withdrawn` : `declareIncident` / `withdrawIncident`.
3. Pour chaque journal dont la longueur a changé : `anchorAudit(run_id, head, entries)` signé par l'entreprise.
4. Ne lit que des données publiques de la simulation ; ne modifie rien.

## Tests — `tests/test_chain_client.py`

- `config` : défaut `off` ; `.env.local` lu sans écraser l'environnement ; `repr` sans mnémonique.
- `ids` : stabilité, longueur, `alert_hash` identique pour la même alerte, différent si la signature change.
- `NullChain` : n'importe pas `web3` (vérifier `sys.modules` dans un sous-processus).
- `Web3Chain` en mode `tester` : après `build_simulation` + `declare_compromise` + `Anchorer.after_action` + `flush`, les alertes sont ancrées et acquittées, les têtes de journaux lues on-chain sont égales aux `head` locaux.
- Panne : un faux provider qui lève → enregistrements `failed`, aucune exception remontée, l'API (si testée) reste rapide.

## Fini quand

- `uv run pytest -q` vert.
- Commit `chain: client, file d'envoi et ancrage des alertes et journaux`.
- Rapport : comment brancher `Anchorer` dans `api.py` (points d'appel exacts) pour la tâche 04.
