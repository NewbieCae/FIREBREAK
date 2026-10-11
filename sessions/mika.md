# Session — Mika

> Mis à jour par l'agent de Mika à chaque itération. Le plus récent en haut du journal. Mika travaille avec deux agents : `mika/pc1` (intégrateur, décide en dernier sur la partie Avalanche) et `mika/pc2` ; ils se coordonnent dans `docs/agents-canal.md`.

## Où j'en suis

- **Avalanche L1** : L1 de l'équipe (chainId 569712), contrat `FirebreakRegistry` déployé (`contracts/deployments/l1.json`), ancrage des journaux d'audit, des alertes signées, des signalements qualité, des accusés de réception et des déclarations. Off par défaut (`FIREBREAK_CHAIN`). Validé sur la vraie L1 : démo complète et scénario `recall`, 0 échec, vérification on-chain conforme, réécriture de journal détectée. Mesures réelles dans `docs/avalanche/pitch.md`.
- **Qualité, dans les deux sens** : lot suspect sans blacklister le fournisseur, analyse de rappel depuis un produit fini, signalement qualité signé vers l'amont avec décision au cas par cas. Scénarios `lot` et `recall`, API, panneau de debug. 295 tests verts.

## En cours

- pc2 : envoi des ancrages en parallèle par entreprise (la file met ~2 min à se vider sur la vraie L1).

## Prochaine étape

- Mesurer l'envoi parallèle sur la L1, puis gel à 10 h.
- Aider le pitch : angle « qualité et rappel produit », chiffres réels Avalanche.

## Besoin des autres

- Yann : afficher le parcours qualité (scénarios `lot` et `recall`) dans l'interface finale, ou décider qu'on le montre depuis le panneau de debug. Sur ces scénarios, le bouton « Déclarer fournisseur compromis » est trompeur.
- Céline : ajouter l'angle qualité au pitch ; les temps d'ancrage réels existent maintenant.

## Journal

- **11/10 04 h 06** — Scénario `recall` rejoué sur la vraie L1 : 20 opérations isolées, 25 preuves ancrées sans échec, fournisseur jamais compromis. Contrat redéployé (type « signalement qualité »).
- **11/10 03 h 58** — Chantier qualité : lot suspect, analyse de rappel, signalement signé vers l'amont (cœur pc1 ; scénarios, API, ancrage et panneau pc2).
- **11/10 03 h 30** — Démo complète rejouée sur la vraie L1 ; pitch Avalanche corrigé (un seul validateur dit honnêtement, pas de finalité < 1 s).
- **11/10 02 h 00** — Contrat déployé sur la L1, premiers ancrages réels.
- **11/10 01 h 00 – 02 h 00** — Partie Avalanche : contrat, déploiement, client, API, panneau, démo de réécriture (pc1 + pc2), fusionnée dans `main` par Yann à 02 h 30.
