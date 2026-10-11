# Session — Mika

> Mis à jour par l'agent de Mika à chaque itération. Le plus récent en haut du journal. Mika travaille avec deux agents : `mika/pc1` (intégrateur, décide en dernier sur la partie Avalanche) et `mika/pc2` ; ils se coordonnent dans `docs/agents-canal.md`.

## Où j'en suis

- **Avalanche L1** : L1 de l'équipe (chainId 569712), contrat `FirebreakRegistry` déployé (`contracts/deployments/l1.json`), ancrage des journaux d'audit, des alertes signées, des signalements qualité, des accusés de réception et des déclarations. Off par défaut (`FIREBREAK_CHAIN`). Validé sur la vraie L1 : démo complète et scénario `recall`, 0 échec, vérification on-chain conforme, réécriture de journal détectée. Mesures réelles dans `docs/avalanche/pitch.md`.
- **Qualité, dans les deux sens** : lot suspect sans blacklister le fournisseur, analyse de rappel depuis un produit fini, signalement qualité signé vers l'amont avec décision au cas par cas. Scénarios `lot` et `recall`, API, panneau de debug.
- **Contrôle des entrées en stock** : note de confiance /100 de chaque réception, mise en attente sous 80, décision humaine. Sur les 3 attaques, le lot piégé est arrêté à la réception. API, ancrage, panneau de debug. 325 tests verts. Feuille de démo : `docs/demo-avalanche-qualite.md`.

## En cours

- pc2 : test du panneau « Entrées en stock » dans le navigateur.

## Prochaine étape

- Gel à 10 h (plus de changement de code sauf bug bloquant).
- Aider le pitch : angle qualité, rappel produit et entrées en stock (`docs/qualite.md`), chiffres réels Avalanche (`docs/avalanche/pitch.md`).

## Besoin des autres

- Yann : afficher le parcours qualité (scénarios `lot` et `recall`) dans l'interface finale, ou décider qu'on le montre depuis le panneau de debug. Sur ces scénarios, le bouton « Déclarer fournisseur compromis » est trompeur.
- Céline : ajouter l'angle qualité au pitch ; les temps d'ancrage réels existent maintenant.

## Journal

- **11/10 08 h 40** — Répétition complète sur la vraie L1 : démo principale + Avalanche (vérif ✓, réécriture détectée), entrées en stock (bobine piégée refusée, livraison légitime acceptée), rappel qualité complet. **60 preuves, 60 confirmées, tout vert.** 325 tests. Contrôle des entrées en stock livré (cœur, API, ancrage, panneau de debug) ; 2 bugs trouvés par la relecture de pc2, corrigés.

- **11/10 04 h 06** — Scénario `recall` rejoué sur la vraie L1 : 20 opérations isolées, 25 preuves ancrées sans échec, fournisseur jamais compromis. Contrat redéployé (type « signalement qualité »).
- **11/10 03 h 58** — Chantier qualité : lot suspect, analyse de rappel, signalement signé vers l'amont (cœur pc1 ; scénarios, API, ancrage et panneau pc2).
- **11/10 03 h 30** — Démo complète rejouée sur la vraie L1 ; pitch Avalanche corrigé (un seul validateur dit honnêtement, pas de finalité < 1 s).
- **11/10 02 h 00** — Contrat déployé sur la L1, premiers ancrages réels.
- **11/10 01 h 00 – 02 h 00** — Partie Avalanche : contrat, déploiement, client, API, panneau, démo de réécriture (pc1 + pc2), fusionnée dans `main` par Yann à 02 h 30.
