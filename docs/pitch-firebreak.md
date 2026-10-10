# Firebreak — pitch, démo et questions (Track 3)

À mettre dans `docs/pitch-firebreak.md`. Règle d'or : **les seuls chiffres autorisés viennent de `docs/bench-results.md`** (et, pour la démo en direct, de l'écran). On dit toujours « dans notre simulateur ».

## Phrase unique du problème
Quand un partenaire d'une chaîne d'approvisionnement est compromis, une entreprise ne sait pas quelles opérations sont contaminées : elle laisse tout passer ou elle gèle tout. Firebreak isole seulement ce qui est touché, chez elle et chez ses partenaires.

Personnes aidées (hypothèse à tester) : responsables supply chain et IT de PME industrielles, clients et fournisseurs de grands donneurs d'ordre.

## Découpage du temps (premier tour : 5 min + 2 min de questions)
| Temps | Contenu |
|---|---|
| 0:00–0:30 | Accroche : « Un fournisseur est piraté. 3 commandes sur 100 sont touchées. Aujourd'hui on gèle les 100, ou on laisse passer les 3. » |
| 0:30–1:00 | Pourquoi maintenant, pour qui |
| 1:00–1:30 | La solution en trois idées |
| 1:30–3:00 | Démo en direct |
| 3:00–4:00 | La preuve : 500 mondes simulés |
| 4:00–4:30 | Limites, dites avant qu'on nous les trouve |
| 4:30–5:00 | Et après |

Finale (3 min + 3 min de questions) : garder accroche, démo en 60 s, une seule diapo de preuve (p=0 et p=0,3), une phrase de limites, une phrase d'avenir.

## Les 8 diapos
1. **Titre** : Firebreak, le pare-feu des supply chains. Une phrase : « Isoler ce qui est contaminé, pas toute l'activité. »
2. **Le problème** : schéma de quatre entreprises, un fournisseur piraté envoie de fausses confirmations ; deux mauvaises options (tout couper / continuer).
3. **Pourquoi maintenant** : NIS2 impose des mesures de sécurité sur la chaîne d'approvisionnement et la gestion d'incident. Statistiques à citer comme issues de sources secondaires : 41,4 % des attaques de rançongiciel viendraient de tiers (SecurityScorecard, relayé par un rapport de marché) ; 54 % des brèches de tiers atteindraient aussi les fournisseurs de leurs fournisseurs (Verizon 2024, relayé par un guide d'achat).
4. **La solution** : graphe de provenance → déclaration (source + date) → propagation → quarantaine sélective → alertes signées aux partenaires → un humain libère. Encadré : « Les règles décident, l'IA explique. »
5. **Démo** : capture de l'interface, avec les compteurs en grand.
6. **La preuve** : tableau p=0 / p=0,3 (voir plus bas), une phrase de compromis.
7. **Limites** : tout est simulé ; dépendances manquantes ; règle d'origine prudente ; pas de client validé ; on ne détecte pas la compromission, on la contient.
8. **Et après** : pilotes, intégrations, 6 mois, ce qu'il nous faut (voir plus bas) + équipe.

## Déroulé de la démo (90 secondes, à répéter 3 fois)
1. État de départ : « 0 opération bloquée / 145 continuent ». Dire : « Quatre entreprises, une chaîne qui tourne. »
2. Clic sur **Déclarer fournisseur compromis (depuis 14:00)**. Les compteurs basculent : lire le nombre bloqué, les actions irréversibles bloquées, les euros bloqués, les euros qui continuent. (Chiffres de l'écran, pas de mémoire.)
3. Clic sur une opération rouge : montrer le **chemin exact** dans le graphe jusqu'à la source. « On peut montrer à un auditeur pourquoi. »
4. Panneau **Alertes signées** : les partenaires ont reçu des jetons, aucune donnée commerciale.
5. **Avec vs sans** : même attaque, sans Firebreak les opérations dépendantes continuent.
6. **Retirer la déclaration (fausse alerte)** : tout est libéré, signature vérifiée. Dire : « Un humain garde la main. »
7. Filet de sécurité : si l'écran plante, lancer la **vidéo de démo** enregistrée. Garder aussi **Rejouer** prêt.

## La preuve (à reproduire telle quelle)
Source : `docs/bench-results.md`, 500 mondes, 5 entreprises, 300 opérations par monde. A alerte seule, B blocage du fournisseur et de ses clients directs, C Firebreak.

| | A | B | C Firebreak |
|---|---|---|---|
| Sains bloqués à tort, p=0 | 0 | 43,2 | **9,6** |
| Mondes avec une fuite, p=0 | 100 % | 24,6 % | **0 %** |
| Rappel, p=0 / p=0,3 | 0 % | 98,5 % | 100 % / 93,4 % |
| Mondes avec une action irréversible contaminée qui passe, p=0,3 | 100 % | 5,0 % | 28,4 % |

À dire : « Dans notre simulateur, à dépendances toutes tracées, Firebreak ne laisse rien passer et bloque 4,5 fois moins d'opérations saines que le blocage large. Quand 30 % des dépendances sont invisibles, des actions irréversibles contaminées passent dans 28 % des mondes. C'est un compromis qui dépend de la qualité de la traçabilité. »

À ne pas dire : « l'avantage grandit avec la longueur de la chaîne » comme une découverte. Le balayage de taille montre un écart qui passe de 4,5 fois à 9 fois, mais le générateur densifie les relations quand la chaîne grandit (1,16 puis 2,29 clients directs par entreprise) : une partie de l'écart vient du modèle. À réserver aux questions, avec cette précaution.

D (« Firebreak + prudence ») : option, borne haute. Elle rattrape des fuites, mais le prix monte avec le bruit (environ 1,8 opération saine bloquée par fuite rattrapée sans bruit, 3,1 à 10 %, 7,0 à 30 %).

## Et après (diapo 8) — hypothèses, à présenter comme telles
- **Mois 1–2 : deux pilotes** avec des PME industrielles ou leurs donneurs d'ordre, en mode « unilatéral » : suivre ce qui arrive d'un fournisseur sans exiger qu'il installe quoi que ce soit.
- **Mois 2–4 : connecteurs** vers les flux existants (EPCIS, EDI, ERP), lecture de documents (e-mails, avis d'expédition).
- **Mois 3–5 : mesure sur des données réelles** : rejouer 90 jours d'opérations pour montrer ce qui aurait été isolé lors d'un incident passé.
- **Mois 4–6 : mode réseau** (alertes signées entre partenaires) et cartographie NIS2.
- **Ce qu'il nous faut** : deux ou trois partenaires pilotes, accès à des flux réels anonymisés, un avis conformité.
- Premiers clients visés (hypothèse) : sous-traitants industriels de taille moyenne soumis aux exigences de sécurité de leurs donneurs d'ordre ; éditeurs de logiciels de supply chain qui voudraient l'intégrer.

## Questions probables et réponses
1. **« Pourquoi pas un outil de notation de fournisseurs ? »** Ils disent quel fournisseur est risqué ; nous disons quelles opérations sont contaminées et nous les isolons. Ils sont complémentaires : la déclaration de compromission peut venir d'un de ces outils.
2. **« Resilinc ou Interos font déjà ça. »** Ils relient un événement à des pièces et commandes ouvertes et alertent. À notre connaissance, ils visent surtout des perturbations, et alertent plutôt qu'ils n'isolent. Notre cas : de fausses données injectées, une quarantaine automatique et sélective, des alertes signées entre partenaires. Nous n'avons pas testé leurs produits.
3. **« Et si votre graphe est incomplet ? »** C'est notre limite principale et nous la chiffrons : à 30 % de dépendances invisibles, le rappel passe à 93,4 % et 28,4 % des mondes laissent passer une action irréversible. Leviers : extraction de dépendances depuis les documents, règle de provenance manquante (option D).
4. **« Qui est responsable si vous bloquez à tort ? »** La décision vient de règles déterministes, avec le chemin dans le graphe : elle se conteste et se rejoue. La libération reste une validation humaine ; l'IA ne décide jamais.
5. **« Où est l'IA ? »** Elle lit des documents désordonnés, explique l'impact et propose un plan de reprise. Elle n'isole ni ne libère. (Ne pas annoncer de mesure de l'effet de l'IA tant que l'extracteur n'est pas évalué sur des documents de test.)
6. **« Comment savez-vous qu'un partenaire est compromis ? »** Nous ne le détectons pas : la déclaration vient d'un incident connu, d'un outil de notation ou d'un partenaire. Notre apport est ce qui se passe ensuite.
7. **« Une fausse alerte peut-elle geler mon activité ? »** Une alerte ne porte que des jetons des données de l'émetteur : elle ne peut mettre en quarantaine que ce qui en dépend, et un humain peut la lever. Les signatures sont vérifiées ; les clés ne sont ni écrites dans le code ni devinables.
8. **« Pourquoi pas une blockchain ? »** Un registre commun imposé à toute la filière est difficile à faire adopter (TradeLens a été arrêté en 2023 faute de collaboration de toute l'industrie). Chaque entreprise garde ses données ; seules des alertes signées circulent.
9. **« Qui paierait ? »** Hypothèse à tester : PME industrielles sous pression de leurs donneurs d'ordre (NIS2), et éditeurs qui l'intégreraient. Nous n'avons pas de client validé.
10. **« Vos chiffres sont-ils réels ? »** Non : ils viennent de notre simulateur, reproductible (`scripts/bench.py`, 500 mondes). Ils décrivent notre modèle, pas une entreprise réelle.

## À ne jamais dire
- « Personne ne l'a fait » · « en entreprise réelle » · « conforme à NIS2 » (dire « aide à démontrer ») · « détection parfaite » · un chiffre qui n'est pas dans `docs/bench-results.md` ou à l'écran.
