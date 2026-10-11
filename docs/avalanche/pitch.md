# Pitch — pourquoi Avalanche

## Les 3 preuves (30 secondes)

1. **Qui a prévenu qui, et quand.** Chaque alerte inter-entreprises est
   ancrée sur notre L1 : horodatage que personne ne peut réécrire après coup.
2. **Le journal n'a pas été touché.** La tête du journal d'audit de chaque
   entreprise est ancrée. Si quelqu'un réécrit son journal et recalcule les
   hash, la vérification locale ne voit rien, Avalanche si (bouton de démo).
3. **Seuls les membres écrivent.** Le contrat n'accepte que les adresses des
   entreprises de la fédération : on ne peut pas déclarer un faux incident
   pour paralyser un concurrent.

## Ce qui n'est PAS on-chain

Aucune donnée commerciale : ni montants, ni RIB, ni lots, ni noms de
fournisseurs. Uniquement des empreintes (hash), des identifiants opaques et
des horodatages. Les données restent chez chaque entreprise.

## Pourquoi une L1 dédiée

- Une chaîne de consortium : membres connus, pas de frais imprévisibles, pas
  de données exposées sur un réseau public.
- Contrôle d'accès décidé par les membres : le contrat n'accepte que les
  entreprises de la fédération.
- **À dire honnêtement** : en démo, notre L1 n'a **qu'un seul validateur**
  (nœud hébergé par le Builder Hub d'Avalanche) et l'administrateur du contrat
  est l'équipe. En production, les validateurs sont les membres du
  consortium : c'est ce qui rend la preuve indépendante de chacun.
- Ne pas promettre une finalité « en moins d'une seconde » : sur notre L1,
  une preuve est confirmée en 2 à 4 s, attente du reçu comprise (mesures
  ci-dessous).

## La leçon TradeLens

TradeLens (Maersk / IBM) a annoncé son arrêt fin 2022 et fermé début 2023 : les concurrents refusaient de
confier leur flux à une plateforme contrôlée par un seul acteur. FIREBREAK
évite ce piège : on n'y met que des preuves, pas les données, et la chaîne a
vocation à être validée par les membres du consortium (en démo : un seul
validateur, voir plus haut).

## Chiffres mesurés sur la vraie L1

L1 Avalanche de l'équipe (chainId 569712, contrat
`0x28cE7fcb60FA1592318594807eEE2Ec4Ee2F8D3B`, explorer
https://2hxmvtcr.firn.gg), mesurés par pc1 le 11/10 entre 01 h 50 et 03 h 40 :

- **Les étapes de la démo répondent en 16 ms** (médiane, max 31 ms) : l'ancrage
  part dans une file en arrière-plan, hors du chemin de la requête.
- **Scénario « mixed » + compromission : 12 preuves** (3 alertes signées,
  3 accusés de réception, déclaration, 4 journaux), confirmées en ~24 s,
  soit ~2 s par transaction. Deux passages d'affilée : 24/24 confirmées.
- **Démo complète (6 étapes de `/api/demo/step`) : 19 preuves**, file vidée
  ~70 s après la dernière étape (~3,7 s par transaction, envoi séquentiel).
  Deux passages : 17/19 puis 19/19. Les 2 échecs du premier passage étaient
  des erreurs réseau ponctuelles (nœud géré qui limite le débit), non
  reproduites ; correctif de relance en cours.
- **« Vérifier sur Avalanche »** (lecture des 4 journaux ancrés) : ~3,4 s,
  tout conforme. **Réécriture du journal du fabricant** : vérification locale
  « intègre », vérification Avalanche « non conforme ».
- Pour le pitch : dire « une preuve est sur la chaîne en quelques secondes,
  et la démo n'attend jamais la chaîne ». Lancer la démo **une minute avant**
  de montrer le panneau Avalanche, pour que la file soit vidée.

Mesures sur l'EVM en mémoire (mode `tester`, pc2) pour comparaison : 19
preuves en ~1,5 s, ~80 ms par transaction. Ne jamais les présenter comme
celles de la L1.

## Si on nous demande

- *« Et si la chaîne tombe ? »* Le produit fonctionne sans, l'ancrage est
  optionnel et non bloquant ; il rattrape ensuite.
- *« Pourquoi pas une base de données ? »* Qui contrôle la base peut la
  réécrire : la preuve vaut seulement si elle est hors de portée de chacun.
