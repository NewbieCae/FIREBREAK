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
records_total            = 145
operations_bloquees      = 17
operations_qui_continuent = 128
part_bloquee             = 11.7%
gates_bloques            = 4  ['m-lot-X', 'm-pay-X', 'm-ship-X', 'd-out-X']
paiements_bloques_eur    = 5210
paiements_qui_passent    = 80402
entreprises_touchees     = 4  ['client', 'distributeur', 'fabricant', 'fournisseur']
alertes_signees          = 3  [('fabricant', 'distributeur'), ('fournisseur', 'fabricant'), ('distributeur', 'client')]
etapes_timeline          = 25
audit_integre            = True  (25 entrées)
paiement_frauduleux      = 5210 € (RIB FR76 1234 5678 9000 0000 0000 666)
```

## Déroulé — un clic = une étape

| Clic | Action API | À l'écran | Phrase à dire |
|---|---|---|---|
| 1 | `POST /api/demo/step` → reset `mixed` | Graphe vert : 4 colonnes (Aciers Durand → Mécano Précision Loire → Logidis Rhône → Bâtiments Azur), 145 opérations, compteurs à zéro. | « Voici une supply chain normale un vendredi matin : commandes, certificats, expéditions, paiements. » |
| 2 | étape 1 → `compromise` | 25 étapes de timeline : les records passent au rouge un par un, les alertes voyagent en pointillés entre entreprises, les compteurs tournent en direct. **Bouton « Rejouer »** pour revoir la propagation. | « Le fournisseur est compromis depuis 14 h. Firebreak bloque 17 opérations sur 145 — 11,7 % — et laisse tourner les 128 autres. Le paiement de 5 210 € vers le RIB modifié est bloqué. » |
| 3 | étape 2 → explain `m-pay-X` | Panneau : explication française + chemin de contamination `m-inv-X → m-pay-X` + plan de remédiation. | « Chaque blocage est prouvable : ce paiement dépend de la facture reçue après 14 h. Ce n'est pas un score IA, c'est le graphe. » |
| 4 | étape 3 → remediate `m-gr-X` (validation humaine) | `m-gr-X` passe bleu (`released`) ; la levée se propage : les nœuds aval redeviennent verts, alertes « release » signées vers le distributeur et le client. | « La remédiation libère tout ce qui ne dépendait que d'elle — et les partenaires sont prévenus par alertes signées, sans jamais voir leurs données commerciales. » |
| 5 | étape 4 → audit verify | « Journaux : intègres » — 25 entrées chaînées par hash par entreprise. | « Tout est journalisé et vérifiable : un auditeur peut rejouer chaque décision. » |

Cliquer encore reste en fin de démo (« Démo terminée… »).

## Points de chute si on te questionne

- **Stop rule** : `m-gr-08` (réception contrôlée physiquement) reste verte
  malgré une semence contaminée — la règle `verified` arrête la propagation.
- **Autres scénarios** (sélecteur en haut) : `rib` (8 bloqués, 1 gate,
  5 210 €), `cert` (13 bloqués, généalogie de lots LOT-901/902 + ASM-950),
  `asn` (13 bloqués, stock fantôme jusqu'au planning chantier).
- **API** : http://localhost:8000/docs — tout ce que fait le dashboard est
  documenté dans [api.md](api.md).
