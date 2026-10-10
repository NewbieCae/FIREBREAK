# Fiche de défense — FIREBREAK (Team 14, Track 3)

> Chiffres du banc d'essai (`scripts/bench.py`, 500 mondes × 4 valeurs de p). **À régénérer et vérifier avant le dépôt** : `uv run python scripts/bench.py`, puis comparer avec `docs/bench-results.md`.

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
Trois politiques comparées sur le même monde : A alerte seule, B blocage du fournisseur et de ses partenaires directs, C FIREBREAK.

| | A | B | C (FIREBREAK) |
|---|---|---|---|
| Sains bloqués à tort (p=0) | 0 | 49,5 | 11,4 |
| Activité saine préservée (p=0) | 100 % | 81,3 % | 95,7 % |
| Précision (p=0) | n/d | 40 % | 75 % |
| Rappel à p = 0 / 0,1 / 0,2 / 0,3 | 0 % | ≈ 98 % | 100 / 97,1 / 94,3 / 91,6 % |

Temps de détection / de réponse : non mesuré (le déclencheur est une alerte reçue).

## Limites connues (à dire avant que le jury les trouve)
- Tout est simulé ; les chiffres viennent de notre modèle, pas d'une entreprise réelle.
- FIREBREAK ne voit que les dépendances enregistrées : quand 10 à 30 % manquent, il laisse passer plus de contamination que le blocage large (B), pour moins de dégâts collatéraux. C'est un compromis, pas une victoire écrasante.
- À p=0, FIREBREAK bloque encore des opérations saines : la règle d'origine bloque toute donnée reçue de la source compromise après la date déclarée, même si elle copie une donnée antérieure.
- Le déclencheur est une déclaration ou une alerte reçue ; nous ne détectons pas la compromission.
- Aucun client validé à ce jour.

## Qui est responsable si le système se trompe
La décision de blocage vient de règles déterministes et traçables (chemin dans le graphe) : on peut la contester et la rejouer. La libération d'une quarantaine reste une validation humaine ; l'IA ne décide jamais.
