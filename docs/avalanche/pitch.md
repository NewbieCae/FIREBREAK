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

- Une chaîne de consortium : validateurs et membres connus, pas de frais
  imprévisibles, pas de données exposées sur un réseau public.
- Finalité en moins d'une seconde : l'ancrage suit le rythme d'une alerte.
- Contrôle d'accès et gouvernance décidés par les membres.

## La leçon TradeLens

TradeLens (Maersk / IBM) a annoncé son arrêt fin 2022 et fermé début 2023 : les concurrents refusaient de
confier leur flux à une plateforme contrôlée par un seul acteur. FIREBREAK
évite ce piège : aucun acteur ne détient la chaîne seul, et on n'y met que des
preuves, pas les données.

## Chiffres mesurés

Mesurés sur l'EVM en mémoire (mode `tester`, pc2, 11/10) — **à refaire sur la
vraie L1** (la latence y dépend du temps de bloc) :

- `POST /api/compromise` : ~20 ms (l'ancrage est asynchrone, hors du chemin
  de la requête) ; `/api/state` : ~15 ms.
- Une compromission produit 6 ancrages (alertes, accusés, incident, journaux),
  tous confirmés en ~0,5 s au total, soit ~80 ms par transaction (envoi
  séquentiel).
- Démo complète (6 étapes) : 19 ancrages, 0 échec.
- « Vérifier sur Avalanche » (ancrage forcé des 4 journaux + vérification) :
  ~0,3 s.

## Si on nous demande

- *« Et si la chaîne tombe ? »* Le produit fonctionne sans, l'ancrage est
  optionnel et non bloquant ; il rattrape ensuite.
- *« Pourquoi pas une base de données ? »* Qui contrôle la base peut la
  réécrire : la preuve vaut seulement si elle est hors de portée de chacun.
