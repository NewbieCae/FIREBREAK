# Tâche 00 — Mise en place (Mika, à la main)

Cette fiche n'est **pas** pour un agent : elle touche aux secrets et à l'installation d'outils sur la machine de Mika.

## 1. Outils sur la machine (Windows)

Constat du 11/10 : `uv`, `forge` et Python ≥ 3.12 sont absents ; seul Python 3.6 est installé.

- [ ] Installer `uv` (il installe aussi Python 3.12 pour le projet) :
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  Puis rouvrir le terminal, et dans `finswag/` : `uv sync` puis `uv run pytest -q` → tout doit être vert **avant** de lancer les agents.
- Foundry n'est **pas** nécessaire : on compile et on teste le contrat depuis Python (`py-solc-x`, `eth-tester`), pour rester dans la stack de l'équipe.

## 2. Infos de la L1 (non secrètes) — à compléter ici

| Info | Valeur |
|---|---|
| Nom de la L1 | … |
| chainId | … |
| URL RPC | … |
| Explorer | … |
| Symbole du jeton natif | … |
| Créée avec | console Builder Hub / Avalanche CLI |
| `TxAllowList` activé ? admin = ? | … |
| `ContractDeployerAllowList` activé ? admin = ? | … |
| Adresse publique du compte 0 (admin, celui qui a les jetons) | 0x… |

## 3. Fichier `.env.local` à la racine de `finswag/` (ignoré par Git)

Créer `.env.local` à la main avec ce contenu. Le mnémonique est celui du wallet **dédié au hackathon** ; il ne doit contrôler aucun fonds réel.

```
# Fédération : fixer ces deux valeurs (n'importe quelle longue chaîne aléatoire)
# pour que les clés Ed25519 restent stables entre deux lancements du serveur.
# Indispensable : les clés publiques sont enregistrées on-chain au déploiement.
FIREBREAK_KEY_SEED=...
FIREBREAK_PAIR_SECRET=...

# Avalanche L1 — off (défaut) | tester (EVM en mémoire) | l1 (vraie L1)
FIREBREAK_CHAIN=l1
FIREBREAK_CHAIN_RPC_URL=...
FIREBREAK_CHAIN_ID=...
FIREBREAK_CHAIN_EXPLORER_URL=...
# Compte 0 = admin (a les jetons), 1..4 = fournisseur, fabricant, distributeur, client
FIREBREAK_CHAIN_MNEMONIC=...
FIREBREAK_CHAIN_DEPLOYMENT=contracts/deployments/l1.json
```

Pour générer les deux secrets de fédération : `python -c "import secrets; print(secrets.token_hex(32))"` (deux fois).

Vérifier : `git check-ignore -v .env.local` doit répondre (fichier ignoré).

## 4. MCP Avalanche (optionnel, utile aux agents)

Donne aux agents la doc Avalanche à jour (precompiles, version d'EVM, outils) :
```bash
claude mcp add --transport http avalanche-docs https://build.avax.network/api/mcp
```

## 5. Prévenir l'équipe

`AGENTS.md` dit « pas de branches ». Prévenir Yann que la partie Avalanche vit sur `mika/avalanche-l1`, désactivée par défaut, et qu'elle ne sera fusionnée que verte. Message à envoyer par `scripts/messages.py send yann "…"` (ça pousse sur `main`, c'est voulu).

## Fini quand

- `uv run pytest -q` vert sur la branche.
- Le tableau du §2 est rempli.
- `.env.local` existe et est ignoré.
