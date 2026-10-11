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
4. **La solution** : graphe de provenance → déclaration (source + date) → propagation → quarantaine sélective → alertes signées aux partenaires → un humain libère → les preuves (alertes, accusés, déclarations, têtes de journaux) sont ancrées sur une L1 Avalanche. Encadré : « Les règles décident, l'IA explique, la blockchain prouve. »
5. **Démo** : capture de l'interface, avec les compteurs en grand.
6. **La preuve** : tableau p=0 / p=0,3 (voir plus bas), une phrase de compromis.
7. **Limites** : tout est simulé ; dépendances manquantes, chiffrées : à p=0,3, une action irréversible contaminée passe dans 28,4 % des mondes avec Firebreak contre 5,0 % avec le blocage large, et le levier D (Firebreak + prudence, borne haute) ramène ce taux à 20,6 % (source : `docs/bench-results.md`) ; règle d'origine prudente ; pas de client validé ; on ne détecte pas la compromission, on la contient ; l'ancrage Avalanche prouve qu'un journal n'a pas été réécrit après coup, pas que ce qui y a été écrit était vrai.
8. **Et après** : pilotes, intégrations, 6 mois, ce qu'il nous faut (voir plus bas) + équipe.

## Déroulé de la démo (90 secondes, à répéter 3 fois)
Mêmes gestes que l'interface finale (`/app/`, flèche droite) : le détail écran par écran est dans `docs/demo.md`. Chiffres : ceux de l'écran (scénario `mixed`, reproductibles par `uv run python -m firebreak.demo_figures`).

Lancement avec la blockchain : `FIREBREAK_CHAIN=l1 bash scripts/demo.sh` (vraie L1, configuration dans `.env.local`, `scripts/chain_smoke.py` au vert avant). Sans cette variable, `scripts/demo.sh` démarre **chaîne éteinte** et rien d'Avalanche n'apparaît. `FIREBREAK_CHAIN=tester` fonctionne sans réseau, mais c'est une EVM en mémoire : dans ce mode, ne pas dire « notre L1 ».

1. **Repos** : « 0 opération bloquée / 193 continuent ». Dire : « Quatre entreprises, une chaîne qui tourne. »
2. **Déclarer** (fournisseur compromis depuis 14 h) : la contamination se propage, les compteurs montent. Lire le nombre bloqué, les actions irréversibles bloquées, les euros bloqués, les euros qui continuent.
3. **Avec vs sans** : même attaque, sans Firebreak on bloque large et des opérations contaminées fuient quand même.
4. **Prouver** : clic sur le paiement bloqué, **chemin exact** jusqu'à la source, alerte signée à jetons opaques (aucune donnée commerciale). « Le graphe décide, l'IA explique. »
5. **Guérir** : un humain valide la remédiation, la levée part en cascade vers les partenaires par alertes signées.
6. **Vérifier** : journaux d'audit intègres. Si la chaîne est active : « Ancré sur Avalanche, bloc N », puis **Simuler une réécriture du journal** → local ✓, Avalanche ✗. « La vérification locale ne voit rien. Avalanche, si. »
7. Filet de sécurité : si l'écran plante, lancer la **vidéo de démo** enregistrée, ou le plan B en ligne (https://firebreak-zeta.vercel.app, IA simulée). Garder aussi **Rejouer** prêt. Bonus si on a le temps : **Fausse alerte** (retrait de la déclaration, tout repasse au vert : « un humain garde la main »).

## La preuve (à reproduire telle quelle)
Source : `docs/bench-results.md`, 500 mondes, 5 entreprises, 300 opérations par monde. A alerte seule, B blocage du fournisseur et de ses clients directs, C Firebreak.

| | A | B | C Firebreak |
|---|---|---|---|
| Sains bloqués à tort, p=0 | 0 | 43,2 | **9,6** |
| Mondes avec une fuite, p=0 | 100 % | 24,6 % | **0 %** |
| Rappel, p=0 / p=0,3 | 0 % | 98,5 % | 100 % / 93,4 % |

À dire : « Dans notre simulateur, à dépendances toutes tracées, Firebreak ne laisse rien passer et bloque 4,5 fois moins d'opérations saines que le blocage large. » Le compromis quand des dépendances sont invisibles est dit à la diapo suivante (Limites).

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
7. **« Une fausse alerte peut-elle geler mon activité ? »** Une alerte ne porte que des jetons des données de l'émetteur : elle ne peut mettre en quarantaine que ce qui en dépend, et un humain peut la lever. Les signatures sont vérifiées ; les clés ne sont ni écrites dans le code ni devinables. Sur Avalanche, le contrat n'accepte que les membres de la fédération : une entreprise extérieure ne peut pas déclarer un faux incident.
8. **« Pourquoi une blockchain ? »** Notre journal d'audit est chaîné par hash, mais celui qui le détient peut le réécrire en recalculant tous les hash. Nous ancrons donc sur une L1 Avalanche de consortium les empreintes des journaux, des alertes, des accusés de réception et des déclarations d'incident : on peut prouver après coup qui a été prévenu, et quand (litige, assurance, NIS2), sans dépendre de celui qui tient le journal. En démo, honnêtement : un seul validateur (hébergé par le Builder Hub d'Avalanche) et un seul compte admin du contrat, tenu par l'équipe ; en production, les validateurs sont les membres du consortium. Aucune donnée commerciale sur la chaîne, uniquement des empreintes. La chaîne ne décide et ne bloque rien : si elle tombe, Firebreak continue et l'ancrage rattrape ensuite. Détails : `docs/avalanche/pitch.md`.
   - **« Et TradeLens ? »** TradeLens (Maersk × IBM, arrêt annoncé fin 2022, fermeture début 2023) demandait à toute la filière de confier ses données à une plateforme contrôlée par un seul acteur. Nous faisons l'inverse : les données restent chez chaque entreprise, seules des preuves vont sur la chaîne, et en production ce sont les membres du consortium qui la valident (en démo, un seul validateur).
   - **« Pourquoi pas une base de données partagée ? »** Celui qui contrôle la base peut la réécrire : la preuve ne vaut que si elle est hors de portée de chacun.
9. **« Qui paierait ? »** Hypothèse à tester : PME industrielles sous pression de leurs donneurs d'ordre (NIS2), et éditeurs qui l'intégreraient. Nous n'avons pas de client validé.
10. **« Vos chiffres sont-ils réels ? »** Non : ils viennent de notre simulateur, reproductible (`scripts/bench.py`, 500 mondes). Ils décrivent notre modèle, pas une entreprise réelle.

## À ne jamais dire
- « Personne ne l'a fait » · « en entreprise réelle » · « conforme à NIS2 » (dire « aide à démontrer ») · « détection parfaite » · un chiffre qui n'est pas dans `docs/bench-results.md` ou à l'écran.
- « La blockchain bloque » ou « détecte l'attaque » (elle prouve, elle ne décide rien) · « nos données sont sur la blockchain » (seulement des empreintes) · « sur notre L1 » si la démo tourne en mode `tester` · « finalité en moins d'une seconde » (mesuré sur notre L1 : environ 2 s par preuve, reçu compris ; 12 ancrages en environ 24 s, deux démos d'affilée sans échec) · « aucun acteur ne détient la chaîne » ou « validateurs connus » tant que la L1 n'a qu'un validateur. Ces temps sont « mesurés sur notre démo », pas des chiffres du banc.
