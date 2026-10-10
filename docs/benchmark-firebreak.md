# FIREBREAK — Benchmark des concurrents

> Ce que fait le marché, ce qui manque, et ce qui nous différencie.
> Sources : sites officiels des acteurs, consultés le 10 octobre 2026. Aucun produit testé en main propre.

## En bref

Le marché sait dire **quel fournisseur est dangereux**, ou **quelle machine isoler** chez soi.
Personne ne dit **quelles opérations métier précises** (commandes, livraisons, paiements) ont été contaminées par les données d'un partenaire compromis, ni ne les met en quarantaine sans bloquer le reste.

## Les concurrents

### 1. Notation cyber des fournisseurs (TPRM)

| Acteur | Ce qu'ils offrent |
|---|---|
| [SecurityScorecard](https://securityscorecard.com) | Notes de sécurité des fournisseurs vues de l'extérieur, surveillance continue, questionnaires, agents IA (TITAN AI), service géré de réponse aux incidents supply chain (MAX). |
| [Bitsight](https://www.bitsight.com) | Notes de sécurité, surveillance continue des tiers, exposition de la supply chain (Beacon), veille dark web. |
| [UpGuard](https://www.upguard.com) | Risque fournisseurs, surface d'attaque, questionnaires automatisés par IA. |
| [Black Kite](https://blackkite.com) | Risque cyber des tiers, chiffrage financier du risque (Open FAIR), probabilité de ransomware. |
| [RiskRecon (Mastercard)](https://www.riskrecon.com) | Notes cyber, évaluations, suivi de la remédiation avec les fournisseurs. |
| [Panorays](https://www.panorays.com), [Mitratech Prevalent](https://mitratech.com/products/prevalent/) | Évaluation des fournisseurs, questionnaires, conformité. |

**Limite :** ils raisonnent au niveau **du fournisseur entier**. Ils voient l'entreprise de l'extérieur, pas les commandes qu'elle a touchées chez vous. Leur réponse type : « surveiller » ou « couper ».

### 2. Risque supply chain physique

| Acteur | Ce qu'ils offrent |
|---|---|
| [Interos](https://www.interos.ai) | Cartographie des fournisseurs sur plusieurs rangs, alertes (cyber, sanctions, tarifs, réputation). |
| [Everstream](https://www.everstream.ai) | Jumeau numérique du réseau, alertes IA, visibilité sur les sous-traitants. |
| [Resilinc](https://www.resilinc.com) | Veille sur les perturbations fournisseurs (catastrophes, pénuries, sites). |

**Limite :** ils détectent qu'un fournisseur ou un site est **touché**, pas que **ses données** ont faussé vos opérations.

### 3. Confinement de brèche (réseau)

| Acteur | Ce qu'ils offrent |
|---|---|
| [Illumio](https://www.illumio.com) | Microsegmentation : isole les machines et les flux réseau pour empêcher une attaque de se propager. |
| EDR / XDR (CrowdStrike, SentinelOne…) | Isolement des postes et serveurs compromis. |

**Limite :** le confinement se fait **dans une seule entreprise**, au niveau **réseau et machines**. Une fausse confirmation de livraison passe par un canal légitime : le réseau ne la voit pas.

### 4. Traçabilité des données et des artefacts

| Acteur | Ce qu'ils offrent |
|---|---|
| [OpenLineage](https://openlineage.io) | Standard open source de lignage : d'où vient chaque jeu de données, analyse d'impact. |
| [SLSA](https://slsa.dev), Sigstore, Snyk… | Provenance et intégrité du **code** et des paquets logiciels. |
| TradeLens (Maersk × IBM) | Registre blockchain partagé pour le transport maritime. Arrêté début 2023, faute d'adoption par l'écosystème. |

**Limite :** le lignage reste **interne** et **sans action** (il explique, il ne bloque pas). SLSA protège le code, pas les flux métier. TradeLens montre qu'un registre commun imposé à toute la filière est difficile à faire adopter.

### 5. Partage de menaces

| Acteur | Ce qu'ils offrent |
|---|---|
| [MISP](https://www.misp-project.org), ISAC sectoriels | Partage d'indicateurs techniques entre organisations (IP, malwares, campagnes). |

**Limite :** on partage des **indicateurs techniques**, pas « telle opération chez vous dépend d'une donnée suspecte ».

## Tableau de synthèse

| | Notation fournisseurs | Supply chain physique | Confinement réseau | Lignage / provenance | Partage de menaces | **Firebreak** |
|---|---|---|---|---|---|---|
| Niveau d'analyse | Fournisseur | Fournisseur / site | Machine / flux | Jeu de données / code | Indicateur | **Opération métier** |
| Entre entreprises | Oui | Oui | Non | Non | Oui | **Oui** |
| Bloque quelque chose | Non | Non | Oui | Non | Non | **Oui, ciblé** |
| Laisse passer le sain | — | — | Partiellement | — | — | **Oui** |
| Décision explicable | Note | Score | Règles réseau | Graphe | — | **Chemin dans le graphe** |

## Recommandation

**Notre phrase :**

> Les autres disent quel fournisseur est dangereux. Firebreak dit quelles commandes sont touchées, les met en quarantaine, et laisse tourner tout le reste.

**Ce qui nous différencie, en trois points :**

1. **La granularité : l'opération, pas le fournisseur.** 3 commandes touchées sur 100, on bloque 3, pas 100. C'est notre seule promesse, il faut la démontrer en démo.
2. **Une décision prouvable.** Le blocage vient d'un chemin dans le graphe de dépendances, que l'on peut montrer à un auditeur. L'IA explique et prépare la reprise ; elle ne décide pas.
3. **Une alerte entre partenaires sans fuite de données.** Chaque entreprise garde ses données ; seules des alertes signées circulent. Pas de registre commun à imposer (la leçon TradeLens).

**À ne pas faire :** se battre sur la notation des fournisseurs (marché saturé) ou présenter un chatbot de score de risque.

**Positionnement conseillé :** **complément**, pas concurrent. SecurityScorecard ou Bitsight lèvent l'alerte « ce fournisseur est compromis » ; Firebreak prend le relais et fait le tri opération par opération.
