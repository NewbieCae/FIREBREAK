# FIREBREAK — Brief de l'interface finale

> Pour qui construit l'interface. Le moteur et l'API sont livrés (`docs/api.md`). Ce brief dit **ce que l'on veut voir, ressentir et manier**. Il ne dit pas quel framework utiliser : choisissez ce qui vous rend rapide. Rendu dimanche 12 h, gel à 10 h.
>
> Lire avant : `docs/firebreak.md` (l'idée), `docs/api.md` (le contrat), `web/index.html` (le dashboard de debug, à ne pas imiter, mais il montre chaque appel qui fonctionne).

## 1. L'intention en une phrase

Une **salle de contrôle d'incident** pour une chaîne d'approvisionnement : belle comme un produit de 2026, lisible comme un cockpit, et si simple qu'un juré prend la souris et comprend seul. On concentre une vraie complexité (4 entreprises, 193 opérations, un graphe, des signatures) dans une interface qui respire.

Trois adjectifs à vérifier sur chaque écran : **tech, calme, prouvable.**

## 2. Ce que le jury doit ressentir, dans l'ordre

1. **Ça vit.** L'activité coule entre les entreprises. Rien n'est statique.
2. **Ça frappe.** Un clic, et la contamination se propage sous les yeux. Rouge précis, pas rouge partout.
3. **Ça tient.** Le reste continue de couler. Les gros chiffres verts ne bougent presque pas.
4. **Ça prouve.** Un clic sur une opération bloquée montre le chemin exact et l'explication.
5. **Ça guérit.** Une remédiation, et la chaîne repasse au vert en cascade, jusqu'aux partenaires.

Si un écran ne sert pas une de ces cinq émotions, on le coupe.

## 3. Direction artistique

### Ambiance

Centre de supervision la nuit. Fond sombre profond, pas noir pur : un bleu nuit très désaturé avec, en arrière-plan, un **dégradé fluide et lent** (bleu, cyan, un soupçon de violet) qui bouge à peine, comme une aurore. C'est la seule couleur « libre » de l'interface : tout le reste est discipliné.

Par-dessus, des **panneaux en verre** : fond translucide, flou d'arrière-plan fort, bordure fine à 1 px blanche à 10 ou 15 % d'opacité, un reflet très léger en haut du panneau. Le verre n'est pas de la déco : il hiérarchise. Un panneau de verre = une surface que l'on peut manier. Le fond = le monde qui vit.

Règle : **le verre ne porte jamais de texte long**. Le texte long va sur une surface plus opaque à l'intérieur du panneau, sinon ce n'est pas lisible. La lisibilité gagne toujours contre l'effet.

### Couleurs

| Rôle | Usage | Note |
|---|---|---|
| Fond | bleu nuit désaturé, dégradé animé derrière | jamais de noir pur |
| Verre | blanc à 6–10 % + flou 20–40 px + bordure blanc 12 % | une seule recette, partout |
| Texte principal | blanc cassé 92 % | |
| Texte secondaire | blanc 55 % | |
| **Sain / continue** | vert menthe, lumineux mais pas fluo | la couleur qui rassure |
| **Contaminé / bloqué** | rouge corail chaud | il doit se voir de loin, mais ne jamais occuper plus de 15 % de l'écran |
| **En reprise / libéré** | ambre | transitoire |
| Accent | cyan électrique | liens, focus, signatures vérifiées, boutons primaires |

Quatre couleurs sémantiques, pas une de plus. Jamais de couleur pour « faire joli » : chaque couleur signifie quelque chose, et toujours la même chose. Contraste texte/fond ≥ 4,5:1 partout, y compris sur le verre : testez avec un vérificateur de contraste.

### Typographie

- **Titres et chiffres** : une grotesque géométrique nette (Space Grotesk, Geist, Inter Display ou équivalent). Les gros chiffres en **tabular-nums** pour qu'ils ne sautent pas quand ils s'incrémentent.
- **Texte courant** : Inter ou Geist, 15–16 px, interligne 1,5.
- **Identifiants, jetons, hash, horodatages** : une monospace fine (JetBrains Mono, Geist Mono). Un jeton tronqué `7d4b…5efba` en mono, c'est un signal « crypto, vérifié ».
- Peu de graisses : regular, medium, semibold. Pas de light sur fond sombre.
- Tout ce qui est visible est **en français**, sans anglicisme inutile. Les identifiants techniques restent tels quels.

Reporter les choix finaux dans `design.md` (c'est la source de vérité du design, elle est vide aujourd'hui).

### Logo et nom

- FIREBREAK, « pare-feu » au sens forestier : la bande que l'on coupe pour que l'incendie s'arrête. Le logo doit raconter ça : un trait net qui **interrompt** une propagation. Pistes : une ligne de points liés dont une est coupée par une barre verticale ; ou un feu stylisé stoppé par une ligne. Monochrome d'abord (blanc), déclinaison cyan et rouge.
- Le logo a droit à **une** animation : à l'ouverture, la propagation s'anime puis la barre tombe et l'arrête. Deux secondes, une fois, jamais en boucle.
- Nom en capitales espacées à côté du logo dans l'en-tête. Sous-titre discret : « Pare-feu des supply chains ».

### Icônes

Un **jeu d'icônes custom, cohérent**, 24 px, trait 1,5 px, bouts arrondis, mono-trait. Pas de pack mélangé. Les icônes nécessaires :

| Icône | Sens |
|---|---|
| commande, avis d'expédition, certificat, facture, paiement, lot, expédition, réception | les 8 `kind` d'un record |
| fournisseur, fabricant, distributeur, client | les 4 entreprises (usine, entrepôt, camion, boutique) |
| gate | action irréversible : un cadenas ou une porte |
| vérifié | un sceau ou une coche dans un bouclier |
| alerte signée | une enveloppe avec un sceau ; variante barrée pour « signature rejetée » |
| contamination | une goutte ou une onde |
| quarantaine | un cercle en pointillés |
| levée / reprise | une flèche de retour |
| fausse alerte | une cloche barrée |
| journal d'audit | une chaîne (les événements sont chaînés par hash) |
| avec / sans | deux rectangles côte à côte |

Même trait, même rayon, même grille : une icône seule doit sembler sortir de la même main que les autres.

### Mouvement

Le mouvement explique, il ne décore pas. Trois registres :

1. **Ambiance** : le dégradé de fond et les particules de flux. Lents, continus, jamais au premier plan.
2. **Causalité** : la propagation, les alertes, les cascades de levée. Rythmés par le flux SSE (`/api/events?speed=…`), 0,3 à 0,8 s par étape. On doit pouvoir **suivre du regard** d'où vient le rouge.
3. **Micro-interactions** : hover, focus, apparition des panneaux. 150–250 ms, easing en sortie (ease-out). Jamais de rebond.

Courbe par défaut : `cubic-bezier(0.2, 0.8, 0.2, 1)`. Respecter `prefers-reduced-motion` : les particules s'arrêtent, la propagation devient un fondu.

**Chargements et connexions** : chaque appel réseau a un état visible. Avant la réponse : un **skeleton** en verre avec un léger balayage lumineux, jamais un spinner seul. Pendant une propagation : une **ligne de progression** fine sous l'en-tête, en cyan, qui suit les étapes SSE. Quand une alerte signée est vérifiée : un bref **pulse** cyan sur l'enveloppe. En cas d'erreur : un toast en verre, texte en français, bouton « Réessayer ».

## 4. Les écrans

Une seule page, sans navigation. Les écrans sont des **états** de la même scène. Rien ne se charge ailleurs.

### 4.1 En-tête

Logo, nom, puis à droite : le sélecteur de scénario (`GET /api/scenarios`, 4 choix : mixed, rib, cert, asn), le bouton « Réinitialiser », et un indicateur d'IA (« Bedrock » ou « simulée », depuis `source` de `/explain`). L'en-tête est un panneau de verre fin, fixe.

### 4.2 Le tableau de bord vivant (état de repos)

- **Trois chiffres**, énormes, en haut à gauche sur un panneau de verre : opérations bloquées, paiement frauduleux bloqué (€), paiements qui continuent (€). Source : `counters.global` de `/api/state` (`quarantined`, `amount_blocked`, `amount_flowing`). Ils **s'incrémentent** avec un compteur animé pendant une propagation ; les tabular-nums évitent les sauts.
- **La carte de la chaîne**, au centre, 70 % de l'écran : quatre colonnes, fournisseur → fabricant → distributeur → client. Chaque entreprise est un panneau de verre avec son icône et ses compteurs (`counters.per_company`). Entre elles, des **particules** qui coulent le long des arêtes `cross: true` de `edges`. À l'intérieur de chaque entreprise, les records sont des points regroupés par `kind` ; on n’affiche pas 193 étiquettes, on affiche 193 points qui respirent.
- **Le bouton d'action**, unique, en bas au centre, en verre avec bordure rouge corail : « Déclarer le fournisseur compromis depuis 14 h ». Le libellé vient de `scenarios[].compromise`. C'est le seul bouton rouge de l'interface au repos.

### 4.3 La propagation (état d'incident)

Au clic : `POST /api/compromise`, puis on ouvre `GET /api/events?speed=0.6` et on **joue** la séquence :

| Étape SSE (`type`) | Ce que l'on voit |
|---|---|
| `declaration` | onde rouge qui part de l'entreprise déclarée ; son panneau prend une bordure rouge |
| `seed` | le point du record passe au rouge avec un pulse ; `rule` affiché en infobulle (« source compromise » ou « alerte vérifiée ») |
| `quarantine` | un trait rouge court du `parent` vers le record, puis le record passe au rouge |
| `gate_blocked` | idem, plus l'icône cadenas qui se ferme ; le compteur « bloquées » s'incrémente ; le `text` apparaît dans le fil d'événements |
| `alert_sent` / `alert_received` | une enveloppe scellée file le long de l'arête inter-entreprises (`alert.links`), pulse cyan à la réception si `verified`, croix rouge sinon |
| `release`, `remediation`, `withdrawal` | même mécanique, en vert ou ambre, dans l'autre sens |

Un **fil d'événements** à droite, en verre, affiche le `text` de chaque étape en français, horodaté, avec l'icône du type. On peut remonter le fil. Un bouton « Rejouer » relance le flux.

Les points sains **continuent de couler** pendant tout l'incident. C'est le message : on n'a pas arrêté l'usine.

### 4.4 Avec ou sans Firebreak (l'arme de la démo)

Bouton « Avec vs sans » après une propagation. Deux panneaux côte à côte, même scène, depuis `GET /api/compare` :

- Gauche, **sans Firebreak** : « On coupe le fournisseur et ses clients directs ». Rouge large : `blocked` (54) dont `healthy_blocked` (42, collatéraux) hachurés, et surtout **`leaked`** (5) : des points contaminés restés verts, marqués d'un signal d'alarme. L'activité préservée : 76 %.
- Droite, **avec Firebreak** : 17 bloqués, 0 collatéral, 0 fuite, 100 % d'activité préservée.
- En dessous, une seule ligne de comparaison : `precision` et `recall` sous forme de deux jauges, et les euros.

Le message tient en une image : **moins de casse et moins de fuite**. Transition d'ouverture : les deux panneaux glissent depuis les bords, 250 ms.

### 4.5 La preuve (panneau de détail)

Clic sur un point ou une ligne du fil : un panneau latéral en verre glisse depuis la droite avec `GET /api/records/{id}/explain` :

1. Le libellé, l'entreprise, l'horodatage, le `kind` avec son icône, le statut en badge coloré. Le montant si `payload.amount`. Le jeton en mono si `token`.
2. **Le chemin de contamination** (`path`) : une mini-timeline verticale, un nœud par record, le seed en haut marqué « origine », une flèche entre chaque. C'est la preuve que l'on montre à un auditeur.
3. **L'explication** (`explanation`) sur une surface opaque, en français, avec un petit badge « IA : Bedrock » ou « IA : simulée ». Un sous-titre discret rappelle : « La décision vient du graphe. L'IA explique. »
4. **Le plan de reprise** (`remediation_plan`) : trois cartes-boutons, libellé + `rationale` en secondaire. Le clic appelle `POST /api/records/{id}/remediate` avec l'`action`, ferme le panneau et relance le flux SSE pour montrer la **cascade de levée** (vert ambre qui remonte jusqu'au client, alertes `release` qui filent).

Le panneau est fermable par Échap, clic hors panneau, ou bouton. Pendant le chargement : skeleton. L'IA peut prendre 2 à 4 s en mode Bedrock : afficher le chemin tout de suite (il vient de `record.taint_path` déjà connu) et l'explication quand elle arrive.

### 4.6 Fausse alerte

Petit bouton secondaire « Fausse alerte » visible pendant un incident : `POST /api/compromise/withdraw`. Tout repasse au vert en cascade. À montrer au jury si quelqu'un demande « et si vous vous trompez ? ».

### 4.7 Ingestion (bonus, si le temps)

Zone de dépôt en verre : on glisse `assets/samples/facture-rib-modifie.pdf` ou l'`.eml`. `POST /api/ingest/document?company=…` renvoie une proposition de record lue par l'IA ; on l'affiche dans un panneau, bouton « Confirmer » → `POST …/confirm`. Le record apparaît sur la carte. Idem pour `epcis-sample.json` via `/api/ingest/epcis`. Ça montre « le composant léger qui enregistre la provenance » dont parle le pitch.

### 4.8 Vue partenaire (bonus)

Un commutateur « Voir comme : fabricant / distributeur / client ». La carte ne montre que les records de cette entreprise ; les données des autres sont **floutées** (du verre dépoli, littéralement), on ne voit que les alertes reçues, leur signature vérifiée, et les jetons. Preuve visuelle que rien ne fuit entre entreprises.

## 5. Intégration : ce que l'API garantit

- `GET /api/state` renvoie tout : `companies`, `records`, `edges`, `alerts`, `declarations`, `counters`. Un seul appel au chargement, puis après chaque action (`compromise`, `remediate`, `withdraw`, `reset`, `confirm`) la réponse **est** le nouvel état complet : pas besoin de refaire `/state`.
- La séquence animée vient de `/api/events` (SSE) ou de `/api/timeline` (même contenu, d'un coup). Rejouer les étapes dans l'ordre reproduit exactement l'état final : on peut animer **puis** afficher l'état sans incohérence.
- « Opérations qui continuent » = `ok + released`. Les euros ne comptent que les paiements (`kind == "payment"`), c'est voulu.
- `taint_path` est déjà dans chaque record : le chemin s'affiche sans appel supplémentaire. `/explain` ajoute l'explication et le plan.
- Les dates sont en heure de Paris sans fuseau. Pour `since`, `new Date().toISOString()` est accepté.
- CORS est ouvert : l'interface peut tourner sur un autre port que l'API.
- En cas de 4xx/5xx : `{"detail": "…"}` en français, à afficher dans le toast.

Si quelque chose manque dans l'API, **le dire dans `messages.md`** (`python3 scripts/messages.py send yann "…"`), on l'ajoute. On ne contourne pas le contrat côté interface.

## 6. Démo de 3 minutes : les cinq gestes

1. **Repos** (20 s) : la chaîne vit. « Quatre entreprises, 193 opérations, tout tourne. »
2. **Déclarer** (40 s) : clic, propagation animée, les trois chiffres montent. « 17 bloquées sur 193. Pas 193. »
3. **Avec vs sans** (40 s) : split screen. « Sans nous : 54 bloquées, 42 pour rien, et 5 fuites. Avec : 17, 0, 0. »
4. **Prouver** (40 s) : clic sur le paiement de 5 210 €. Chemin, explication, RIB modifié. « Le graphe décide, l'IA explique. »
5. **Guérir** (30 s) : remédier la réception de lot, cascade verte jusqu'au client, alertes de levée signées. « Et les partenaires sont prévenus, sans voir nos données. »

Tout doit marcher **sans réseau externe** (IA simulée par défaut). Bedrock est un plus si la connexion tient.

## 7. Garde-fous

- Aucune donnée inventée côté interface : tout chiffre vient de l'API.
- Une seule police de verre, une seule courbe d'animation, quatre couleurs sémantiques. La cohérence fait le « léché ».
- Testé en 1920×1080 (projecteur) et en 1440×900 (portable). Pas de scroll horizontal. Les gros chiffres restent lisibles à 5 m.
- Clavier : Tab parcourt les panneaux, Échap ferme, Entrée déclenche. Focus visible en cyan.
- Pas de dépendance lourde juste pour une icône ou une animation. Si une lib de graphe est utilisée, elle sert le graphe ; les particules et les panneaux sont en CSS/SVG/Canvas maison.
- Mettre à jour `design.md` avec les valeurs finales (couleurs, polices, rayons, recette du verre) pour que les slides du pitch reprennent le même langage.
