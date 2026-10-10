# Script de démo FIREBREAK — 3 minutes

Lancement : `bash scripts/demo.sh` (uv sync → serveur en mode démo sur
:8000 → navigateur). Le dashboard s'ouvre sur
http://localhost:8000 ; pilotage au bouton **« Démo : étape suivante →»**
ou à la **flèche droite** du clavier.

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

## Déroulé — un clic = une étape

| Clic | Action API | À l'écran | Phrase à dire |
|---|---|---|---|
| 1 | `POST /api/demo/step` → reset `mixed` | Graphe vert : 4 colonnes (Aciers Durand → Mécano Précision Loire → Logidis Rhône → Bâtiments Azur), 193 opérations, compteurs à zéro. | « Voici une supply chain normale, un jour ordinaire : commandes, certificats, expéditions, paiements. » |
| 2 | étape 1 → `compromise` | 25 étapes de timeline : les records passent au rouge un par un, les alertes voyagent en pointillés entre entreprises, les compteurs tournent en direct. **Bouton « Rejouer »** pour revoir la propagation. | « Le fournisseur est compromis depuis 14 h. Firebreak bloque 17 opérations sur 193 — 8,8 % — et laisse tourner les 176 autres. Le paiement de 5 210 € vers le RIB modifié est bloqué. » |
| 3 | étape 2 → `GET /api/compare` | **Écran divisé** : à gauche « Sans Firebreak » (le périmètre coupé gris/rouge, fuites orange vers le distributeur et le client), à droite « Avec Firebreak » (17 rouges précis, zéro collatéral). Bandeau : chiffres du bench sur 500 chaînes + exemples réels JLR/CDK. | « Sans Firebreak, on coupe le fournisseur et ses clients directs : 54 opérations bloquées dont 42 saines — toute une après-midi de production à l’arrêt — et 5 opérations contaminées fuient quand même vers le client. Avec Firebreak : 17 bloquées, toutes contaminées, zéro sain bloqué, zéro fuite. Sur 500 chaînes simulées, ça fait 11 opérations saines bloquées contre 49 — quatre fois moins de dégâts collatéraux, pour un meilleur rappel. » |
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
