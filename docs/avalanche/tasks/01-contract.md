# Tâche 01 — Contrat `FirebreakRegistry` + compilation + tests

Lis d'abord `docs/avalanche/README.md` et `docs/avalanche/tasks/RULES.md`.

## Objectif

Un seul contrat Solidity, petit et lisible, qui sert de témoin horodaté pour Firebreak. Compilé depuis Python, testé sur une EVM en mémoire. Aucun accès réseau.

## Dépendances à ajouter (groupe dev)

`uv add --dev py-solc-x "eth-tester[py-evm]"` et `uv add web3` — versions stables publiées depuis au moins 7 jours. `web3` sert aussi aux tâches 02 et 03.

## Le contrat — `contracts/FirebreakRegistry.sol`

- `pragma solidity 0.8.24;`, compilé avec **`evmVersion: "paris"`** (pas de `PUSH0`, compatible avec toute L1 Subnet-EVM). Si le MCP `avalanche-docs` est disponible, vérifie la version d'EVM supportée par Subnet-EVM et note-la dans ton rapport.
- Pas de dépendance OpenZeppelin : tout tient en ~150 lignes.

### État

```solidity
address public admin;
struct Member { bytes32 companyId; bytes32 ed25519PubKey; bool active; }
mapping(address => Member) public members;            // compte EVM → entreprise
mapping(bytes32 => address) public accountOf;         // companyId → compte EVM
mapping(bytes32 => bytes32) public pubKeyOf;          // companyId → clé publique Ed25519 (32 octets)

struct AlertRecord { bytes32 fromCompany; bytes32 toCompany; uint8 alertType; uint64 anchoredAt; uint64 ackAt; }
mapping(bytes32 => AlertRecord) public alerts;        // alertHash → enregistrement

struct AuditAnchor { bytes32 head; uint32 entries; uint64 anchoredAt; }
mapping(bytes32 => mapping(bytes32 => AuditAnchor)) public latestAudit; // runId → companyId → dernier ancrage
```

### Fonctions

| Fonction | Qui | Effet |
|---|---|---|
| `constructor()` | — | `admin = msg.sender` |
| `registerMember(address account, bytes32 companyId, bytes32 pubKey)` | admin | crée ou met à jour un membre actif ; refuse un `companyId` déjà lié à un autre compte |
| `deactivateMember(address account)` | admin | `active = false` |
| `declareIncident(bytes32 runId, bytes32 sourceCompany, uint64 since, bytes32 declarationHash)` | membre actif | event `IncidentDeclared(runId, declarer, sourceCompany, since, declarationHash, block.timestamp)` |
| `withdrawIncident(bytes32 runId, bytes32 sourceCompany, bytes32 declarationHash)` | membre actif | event `IncidentWithdrawn(...)` |
| `anchorAlert(bytes32 runId, bytes32 alertHash, bytes32 toCompany, uint8 alertType)` | membre actif = émetteur | refuse un `alertHash` déjà ancré ; `alertType` 0 = taint, 1 = release ; stocke ; event `AlertAnchored(runId, alertHash, from, to, alertType, block.timestamp)` |
| `acknowledgeAlert(bytes32 alertHash)` | membre actif = destinataire | refuse si inconnu ou déjà acquitté ; event `AlertAcknowledged(alertHash, to, block.timestamp)` |
| `anchorAudit(bytes32 runId, bytes32 head, uint32 entries)` | membre actif | refuse si `entries` < dernier ancrage du même run (un journal ne raccourcit pas) ; stocke ; event `AuditAnchored(runId, company, head, entries, block.timestamp)` |
| `transferAdmin(address)` | admin | — |

- `runId` : identifiant d'une partie de démo (un `reset` = un nouveau run), pour que plusieurs démos ne se mélangent pas.
- Erreurs Solidity personnalisées (`error NotAdmin(); error NotMember(); …`) plutôt que des chaînes.
- Tous les events ont leurs champs clés `indexed` (runId, companyId, alertHash).

## Compilation — `scripts/chain_compile.py`

- Installe la version de solc demandée via `py-solc-x` si absente, compile avec optimiseur (200 runs) et `evmVersion: "paris"`.
- Écrit `contracts/build/FirebreakRegistry.json` : `{"contractName", "abi", "bytecode", "solcVersion", "evmVersion", "sourceSha256"}`. Ce fichier est **versionné** (le serveur n'aura pas besoin de solc).
- Idempotent : relancer sans changement de source ne modifie pas le fichier.

## Tests — `tests/test_chain_contract.py`

Sur `EthereumTesterProvider` (web3 + eth-tester), en chargeant `contracts/build/FirebreakRegistry.json`. Au minimum :

- admin enregistre 4 membres ; un non-admin ne peut pas enregistrer ;
- un non-membre ne peut ni déclarer, ni ancrer (c'est l'argument « personne d'extérieur ne déclare un faux incident ») ;
- `anchorAlert` par l'émetteur → `alerts(hash)` rempli, event émis ; ré-ancrer le même hash → revert ;
- `acknowledgeAlert` seulement par le destinataire ; double acquittement → revert ;
- `anchorAudit` : stocke, refuse un nombre d'entrées en baisse, accepte un nouveau `runId` qui repart de zéro ;
- membre désactivé → plus aucune écriture ;
- un test qui vérifie que `contracts/build/…json` correspond bien à la source actuelle (`sourceSha256`), pour qu'on n'oublie pas de recompiler.

## Fini quand

- `uv run python scripts/chain_compile.py` produit le JSON.
- `uv run pytest -q` vert (tous les tests du dépôt).
- Commit `chain: contrat FirebreakRegistry, compilation et tests` sur `mika/avalanche-l1`.
- Rapport : signatures exactes des fonctions et events (la tâche 03 en dépend), version de solc, taille du bytecode.
