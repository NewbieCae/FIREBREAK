# Script de démo FIREBREAK — 3 minutes

Lancement : `bash scripts/demo.sh` (uv sync → serveur en mode démo sur
:8000 → navigateur). **L'interface finale** s'ouvre sur
http://localhost:8000/app/ ; chaque geste se fait à la souris, ou à la
**flèche droite** du clavier (un appui = un geste, voir « Interface finale »
ci-dessous). Le dashboard de debug reste sur http://localhost:8000 (secours).

Tous les chiffres ci-dessous sont produits par une commande
reproductible — pas recopiés à la main :

```bash
uv run python -m firebreak.demo_figures
```

Sortie mesurée (scénario `mixed`, fournisseur compromise depuis 14 h) :

```
records_total            = 193
operations_bloquees      = 17
operations_qui_continuent = 176
part_bloquee             = 8.8%
gates_bloques            = 4  ['m-lot-X', 'm-pay-X', 'm-ship-X', 'd-out-X']
paiements_bloques_eur    = 5210
paiements_qui_passent    = 92102
entreprises_touchees     = 4  ['client', 'distributeur', 'fabricant', 'fournisseur']
alertes_signees          = 3  [('fabricant', 'distributeur'), ('fournisseur', 'fabricant'), ('distributeur', 'client')]
etapes_timeline          = 25
audit_integre            = True  (25 entrées)
paiement_frauduleux      = 5210 € (RIB FR76 1234 5678 9000 0000 0000 666)

== Avec vs sans Firebreak (politique C vs B) ==
B    Sans Firebreak   bloqués  54  saines bloquées  42  fuites 5  gates 18  activité préservée 76.1 %
C    Avec Firebreak   bloqués  17  saines bloquées   0  fuites 0  gates 4  activité préservée 100.0 %
ratio                    = infini (0 sain bloqué avec Firebreak)
```

## Interface finale (`/app/`) — les cinq gestes

Une seule page. La flèche droite enchaîne les gestes ; tout reste cliquable à la souris.

| → | Geste | À l'écran | Phrase à dire |
|---|---|---|---|
| — | **Repos** | La chaîne vit : 4 panneaux de verre, 193 points qui respirent, des particules vertes qui coulent entre les entreprises. | « Quatre entreprises, 193 opérations, tout tourne. » |
| 1 | **Déclarer** (bouton corail en bas) | Onde corail sur Aciers Durand, les points passent au rouge un par un, les traits suivent les dépendances, les enveloppes scellées filent vers l'aval, cadenas sur les actions irréversibles ; les trois chiffres montent ; le fil défile à droite. | « 17 bloquées sur 193. Pas 193. Les points verts continuent de couler : on n'a pas arrêté l'usine. » |
| 2 | **Avec vs sans** | Deux panneaux glissent des bords. Gauche : fournisseur et fabricant hachurés « coupé », 42 saines bloquées, 5 fuites qui clignotent chez le distributeur et le client. Droite : 17 rouges précis, 0, 0. Jauges précision / rappel, banc d'essai, JLR et CDK. | « Sans nous : 54 bloquées, 42 pour rien, et 5 fuites. Avec : 17, 0, 0. » |
| 3 | **Prouver** | Tiroir sur le paiement de 5 210 € : RIB, chemin depuis l'alerte signée (jeton opaque, signature vérifiée), explication, plan de reprise. | « Le graphe décide, l'IA explique. » |
| 4 | **Guérir** | Remédiation de la réception BC-9999 (validation humaine) : point ambre, levée en cascade jusqu'au client, alertes de levée signées. Le paiement frauduleux reste bloqué. | « Et les partenaires sont prévenus, sans voir nos données. » |
| 5 | **Vérifier** | Toast « journaux d'audit intacts » ; chaque panneau montre la tête de sa chaîne de hash. | « Tout est journalisé et vérifiable. » |

Si on recommence la démo : la flèche droite repart d'une scène propre toute seule (réinitialisation automatique si une remédiation ou un retrait a laissé des records « libérés »). À la souris : **Réinitialiser** avant chaque répétition.

Avec Avalanche (`FIREBREAK_CHAIN=tester` ou `l1`) : une pastille « Avalanche · N ancré(s) » apparaît dans l'en-tête (clic → liste des ancrages) ; le journal d'audit de chaque entreprise montre « Ancré sur Avalanche, bloc N : le journal correspond » ; en mode démo, **Simuler une réécriture du journal** montre une chaîne locale encore cohérente mais qui ne correspond plus à l'ancrage. Chaîne éteinte : rien de tout cela n'apparaît.

Bonus si on a le temps : **Voir comme** (en haut) → Distributeur : les autres registres deviennent du verre dépoli, seules les alertes signées passent. **Importer** → « Facture au RIB modifié » : l'IA lit le PDF, un humain confirme, la facture arrive en rouge. **Fausse alerte** : tout repasse au vert en cascade.

## Dashboard de debug — un clic = une étape

| Clic | Action API | À l'écran | Phrase à dire |
|---|---|---|---|
| 1 | `POST /api/demo/step` → reset `mixed` | Graphe vert : 4 colonnes (Aciers Durand → Mécano Précision Loire → Logidis Rhône → Bâtiments Azur), 193 opérations, compteurs à zéro. | « Voici une supply chain normale, un jour ordinaire : commandes, certificats, expéditions, paiements. » |
| 2 | étape 1 → `compromise` | 25 étapes de timeline : les records passent au rouge un par un, les alertes voyagent en pointillés entre entreprises, les compteurs tournent en direct. **Bouton « Rejouer »** pour revoir la propagation. | « Le fournisseur est compromis depuis 14 h. Firebreak bloque 17 opérations sur 193 — 8,8 % — et laisse tourner les 176 autres. Le paiement de 5 210 € vers le RIB modifié est bloqué. » |
| 3 | étape 2 → `GET /api/compare` | **Écran divisé** : à gauche « Sans Firebreak » (le périmètre coupé gris/rouge, fuites orange vers le distributeur et le client), à droite « Avec Firebreak » (17 rouges précis, zéro collatéral). Bandeau : chiffres du bench sur 500 chaînes + exemples réels JLR/CDK. | « Sans Firebreak, on coupe le fournisseur et ses clients directs : 54 opérations bloquées dont 42 saines — toute une après-midi de production à l’arrêt — et 5 opérations contaminées fuient quand même vers le client. Avec Firebreak : 17 bloquées, toutes contaminées, zéro sain bloqué, zéro fuite. Sur 500 chaînes simulées, ça fait 9,6 opérations saines bloquées contre 43,2 — 4,5 fois moins de dégâts collatéraux, pour un meilleur rappel (source : `docs/bench-results.md`). » |
| 4 | étape 3 → explain `m-pay-X` | Panneau : explication française + chemin de contamination `m-inv-X → m-pay-X` + plan de remédiation. | « Chaque blocage est prouvable : ce paiement dépend de la facture reçue après 14 h. Ce n'est pas un score IA, c'est le graphe. » |
| 5 | étape 4 → remediate `m-gr-X` (validation humaine) | `m-gr-X` passe bleu (`released`) ; la levée se propage : les nœuds aval redeviennent verts, alertes « release » signées vers le distributeur et le client. | « La remédiation libère tout ce qui ne dépendait que d'elle — et les partenaires sont prévenus par alertes signées, sans jamais voir leurs données commerciales. » |
| 6 | étape 5 → audit verify | « Journaux : intègres » — 25 entrées au total, chaînées par hash dans le journal de chaque entreprise. | « Tout est journalisé et vérifiable : un auditeur peut rejouer chaque décision. » |

Cliquer encore reste en fin de démo (« Démo terminée… »).

## Points de chute si on te questionne

- **Stop rule** : `m-gr-08` (réception contrôlée physiquement) reste verte
  malgré une semence contaminée — la règle `verified` arrête la propagation.
- **Autres scénarios** (sélecteur en haut) : `rib` (8 bloqués, 1 gate,
  5 210 €), `cert` (13 bloqués, généalogie de lots LOT-901/902 + ASM-950),
  `asn` (13 bloqués, stock fantôme jusqu'au planning chantier).
- **API** : http://localhost:8000/docs — tout ce que fait le dashboard est
  documenté dans [api.md](api.md).

## Avalanche L1 (optionnel)

Aucune étape existante ne change. La chaîne ne s'active que si on le demande.

**Lancement** (sans réseau, EVM en mémoire) :
`FIREBREAK_DEMO=1 FIREBREAK_CHAIN=tester bash scripts/demo.sh`.
Sur la vraie L1 : `FIREBREAK_CHAIN=l1` après `scripts/chain_smoke.py` au vert
(configuration dans `.env.local`, jamais versionné). Fixer aussi
`FIREBREAK_KEY_SEED` et `FIREBREAK_PAIR_SECRET`.

| Clic | Ce qu'on voit | Ce qu'on dit |
|---|---|---|
| Ouvrir le panneau « Avalanche » (colonne de droite) | point vert, chainId, contrat, file d'ancrages | « Chaque alerte et chaque journal sont ancrés sur notre L1 Avalanche : un témoin horodaté, hors de portée de celui qui tient le journal. » (Si on demande : en démo, un seul validateur ; en production, les membres du consortium.) |
| Étape « compromission » de la démo | des ancrages `alert`, `ack`, `incident`, `audit` passent à *confirmé* avec un numéro de bloc | « Seuls les membres de la chaîne peuvent écrire : une entreprise extérieure ne peut pas déclarer un faux incident pour paralyser un concurrent. » |
| « Vérifier sur Avalanche » | pour chaque entreprise : local ✓, Avalanche ✓ | « Aucune donnée commerciale sur la chaîne : uniquement des empreintes. » |
| « Simuler une réécriture du journal » | local ✓, **Avalanche ✗** sur le fabricant | « Ici quelqu'un réécrit le journal du fabricant pour effacer qu'il a été prévenu, et recalcule tous les hash. La vérification locale ne voit rien. Avalanche, si. » |

Le bouton de réécriture exige `FIREBREAK_DEMO=1`. Après une réécriture,
« Réinitialiser » repart d'un journal propre (nouveau `run_id`). Si la L1 est
lente ou coupée, les ancrages restent `en cours` ou `échec` : la démo
continue, la chaîne n'est jamais bloquante. Les étapes de démo ne sont pas
modifiées : l'enchaînement ci-dessus se fait à la main.
