# Fiche de défense — FIREBREAK (Team 14, Track 3)

> Chiffres du banc d'essai v2 (`scripts/bench.py`, 500 mondes × 4 valeurs de p), **régénérés le 11/10** : les chiffres de la v1 (49,5 / 11,4…) sont caducs. **À vérifier avant le dépôt** : `uv run python scripts/bench.py`, puis comparer avec `docs/bench-results.md`.

## Menace traitée
Un partenaire d'une chaîne d'approvisionnement est compromis et injecte de fausses données (confirmations de livraison, stocks, coordonnées bancaires) dans les processus de ses clients et fournisseurs. Les partenaires n'ont aujourd'hui que deux options : tout couper avec lui, ou continuer et laisser passer la contamination.

## Ce que fait FIREBREAK
- Chaque entreprise enregistre la provenance de ses opérations (qui dépend de quoi) dans un graphe de dépendances.
- Quand une source est déclarée compromise depuis un instant donné, le moteur parcourt le graphe, met en quarantaine **seulement** les opérations qui en dépendent, et laisse passer les autres. Chaque quarantaine affiche le chemin exact dans le graphe.
- Les partenaires concernés reçoivent des alertes **signées (Ed25519)** qui ne contiennent que des jetons opaques, jamais de données commerciales. Une alerte falsifiée est rejetée.
- Chaque décision est inscrite dans un journal d'audit chaîné par hachage ; une libération passe par une remédiation (revalidation, validation humaine ou source de confiance).
- **Les règles décident, l'IA aide** : elle lit des documents, explique l'impact et propose un plan de reprise. Elle n'isole ni ne libère jamais seule.

## Fonctions NIST CSF 2.0 couvertes
| Fonction | Ce que le projet apporte |
|---|---|
| Identify | Graphe de provenance et de dépendances entre opérations et entreprises |
| Detect | Réception d'une déclaration de compromission ou d'une alerte signée d'un partenaire (la détection de la compromission elle-même n'est pas notre apport) |
| Respond | Quarantaine sélective, alertes signées aux partenaires, plan de reprise |
| Recover | Levée signée, remédiation, reprise des opérations indépendantes |
| Govern | Journal d'audit chaîné, chemin de décision explicable |

## Référentiels (identifiants à vérifier sur attack.mitre.org avant le dépôt)
- MITRE ATT&CK : Supply Chain Compromise (T1195), Trusted Relationship (T1199), Data Manipulation (T1565).
- Réglementation citée comme contexte, sans prétendre à la conformité : NIS2 (sécurité de la chaîne d'approvisionnement, gestion des incidents). Le journal d'audit *aide à démontrer* les décisions.

## Métriques (simulateur, 500 mondes aléatoires, 4 niveaux de dépendances non enregistrées)
Quatre politiques comparées sur le même monde : A alerte seule, B blocage du fournisseur et de ses partenaires directs, C FIREBREAK, D FIREBREAK + prudence (C, plus la quarantaine des réceptions sans provenance enregistrée chez les partenaires directs). L'entreprise compromise est tirée parmi les 5, client final compris ; 10 % des réceptions viennent d'hors fédération (légitimes, sans jeton).

| | A | B | C (FIREBREAK) | D (+ prudence) |
|---|---|---|---|---|
| Sains bloqués à tort (p=0) | 0 | 43,2 | 9,6 | 11,7 |
| Activité saine préservée (p=0) | 100 % | 83,8 % | 96,4 % | 95,6 % |
| Précision (p=0) | n/d | 44 % | 78 % | 75 % |
| Actions irréversibles contaminées qui passent (p=0, par monde) | 11,1 | 0,07 | 0 | 0 |
| Mondes avec au moins une fuite (p=0) | 100 % | 24,6 % | 0 % | 0 % |
| Rappel à p = 0 / 0,1 / 0,2 / 0,3 | 0 % | 98,5 % (quel que soit p) | 100 / 98,0 / 95,7 / 93,4 % | 100 / 99,4 / 98,6 / 97,9 % |
| Rappel à p = 0,3 : 5e centile / pire cas | — | 91,2 / 72,9 % | 79,2 / 66,0 % | 90,0 / 78,6 % |

Temps de détection : non mesuré (le déclencheur est une déclaration ou une alerte reçue, nous ne détectons pas).
Temps de réponse, mesuré sur notre démo (scénario `mixed`, pas un chiffre du banc) : mise en quarantaine des 17 opérations en environ 20 ms par l'API HTTP (2 ms en médiane hors réseau, chaîne éteinte, 20 essais) ; ancrage de chaque preuve sur notre L1 Avalanche en environ 2 s, en arrière-plan, sans retarder la quarantaine (12 ancrages en environ 24 s, 0 échec sur deux démos).

## Limites connues (à dire avant que le jury les trouve)
- Tout est simulé ; les chiffres viennent de notre modèle, pas d'une entreprise réelle.
- FIREBREAK ne voit que les dépendances enregistrées : quand 10 à 30 % manquent, son rappel moyen passe sous celui du blocage large (B), pour 4,5 à 5,4 fois moins de dégâts collatéraux. À 30 % de dépendances manquantes, 28 % des mondes laissent passer au moins une action irréversible contaminée. C'est un compromis, pas une victoire écrasante.
- À p=0, FIREBREAK bloque encore des opérations saines, et toutes viennent de la règle d'origine : toute donnée attribuée à la source compromise après la date déclarée est bloquée, même si elle copie une donnée antérieure ou vérifiée.
- La politique D exploite le signal « provenance manquante » (réception sans jeton ni lien). Le simulateur suppose qu'un envoi non tracé laisse toujours une réception non attribuée : ses chiffres sont une borne haute.
- Le déclencheur est une déclaration ou une alerte reçue ; nous ne détectons pas la compromission.
- Aucun client validé à ce jour.

## Qui est responsable si le système se trompe
La décision de blocage vient de règles déterministes et traçables (chemin dans le graphe) : on peut la contester et la rejouer. La libération d'une quarantaine reste une validation humaine ; l'IA ne décide jamais.
