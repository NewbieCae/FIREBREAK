# Design System — FIREBREAK

> Source de vérité du design. Synchro avec l'interface finale `web/app/` (servie sur `http://localhost:8000/app/`).
> Les slides du pitch reprennent ces valeurs à l'identique. Trois adjectifs à vérifier sur chaque écran : **sobre, contrasté, prouvable**.
> Refonte du 11/10 (04 h 45) : on quitte l'esthétique « néon / verre lumineux » pour un registre de keynote de startup — noir profond, un horizon de lumière granuleuse, aucune boîte inutile.

## Principes

- **Noir profond, une seule lumière** : fond `#050506`, un horizon de lumière bleue granuleuse qui monte du bas de l'écran. Il vire au corail quand un incident est en cours (transition de 1,6 s), puis revient au bleu.
- **Pas de boîtes** : les entreprises, les chiffres et le fil flottent, séparés par des filets fins (1 px, blanc 8 à 16 %). Une surface pleine n'existe que pour ce qu'on manipule : tiroir, menus, dock d'action, toasts.
- **Le sain est neutre** : une opération qui continue est un point blanc. Seul l'anormal porte une couleur (corail = bloqué, ambre = en reprise, bleu = preuve vérifiée).
- **Aucune lueur** : pas de halo, pas de `text-shadow`, pas de néon. Le contraste vient du noir et du blanc.
- **Icônes sans cadre** : trait fin, posées directement sur le fond.
- **Aucun chiffre inventé** : tout nombre affiché vient de l'API (`docs/api.md`) ; les chiffres du banc viennent de `docs/bench-results.md`.

## Couleurs

| Rôle | Valeur | Usage |
|---|---|---|
| Fond | `#050506` | partout, jamais de dégradé de fond hors horizon |
| Surface pleine | `#0d0e11` + filet blanc 8 % | tiroir, menus, toasts, panneaux « avec vs sans » |
| Surface interne | blanc 3,5 % + filet blanc 8 % | faits, explication, plan de reprise |
| Horizon | bleu `rgba(170,200,255,.62)` → `rgba(70,112,255,.48)` → `rgba(24,48,190,.24)` ; variante incident corail `rgba(255,85,69,.34)` | ellipse floue (30 px) sous le bas de l'écran, dérive 38 s |
| Grain | bruit fractal SVG, 11 %, `mix-blend-mode: overlay` | sur tout le fond |
| **Sain / continue** | `#f4f4f5` (points à 56 %) | points, particules, « paiements qui continuent » |
| **Contaminé / bloqué** | `#ff5545` (corail) | points bloqués, arêtes coupées, chiffres « bloqués », étiquette « Compromis » |
| **En reprise / libéré** | `#ffb02e` (ambre) | remédiation, levée en cascade (transitoire) |
| **Preuve** | `#6e95ff` (bleu) | signatures vérifiées, ancrage Avalanche, focus, anneau « vérifié » |
| Texte principal | `#f4f4f5` | |
| Texte secondaire | `#f4f4f5` à 66 % | 8,1:1 sur le fond |
| Texte tertiaire | `#f4f4f5` à 42 % | décoratif seulement (compteurs, rôles) |

Contrastes calculés (WCAG) sur `#050506` : texte principal 18,5:1 · secondaire 8,1:1 · corail 6,4:1 · ambre 11,2:1 · bleu 7,2:1.

## Typographie

Polices auto-hébergées dans `web/app/fonts/` (aucun réseau externe pendant la démo) : **Geist** et **Geist Mono**, en fontes variables.

| Rôle | Police | Graisse | Taille |
|---|---|---|---|
| Gros chiffres | Geist | **300** | `clamp(44px, 4.1vw, 80px)`, interlettrage −0,055 em |
| Titres | Geist | 500 | 15–22 px, interlettrage −0,02 à −0,03 em |
| Texte courant | Geist | 400–450 | 14,5 px, interligne 1,5 |
| Étiquettes (KPI, sections, méta du fil) | Geist Mono | 450 | 10,5–11 px, MAJUSCULES, interlettrage 0,07 em |
| Identifiants, jetons, hash, heures | Geist Mono | 450 | 0,88 em ; jeton tronqué `7d4b…5efba` |

- Chiffres en `font-variant-numeric: tabular-nums`.
- La graisse fine (300) est réservée aux grands chiffres et aux grandes valeurs : jamais sous 26 px.
- Marque : `firebreak` en minuscules, Geist 600, 18 px, interlettrage −0,035 em. Sous-titre : « Pare-feu des supply chains » en texte tertiaire.
- Tout est en français ; les identifiants techniques restent tels quels.

## Espacement et rayons

- Grille de 4 px. Marges de scène 32 px (26 px sous 940 px de haut), gouttière carte / fil 40 px.
- Rayons : tiroir et panneaux 20 px · contrôles en **pilule** (999 px) · petites surfaces 12–14 px.
- Entre les colonnes de la carte : `clamp(36px, 3.4vw, 72px)` — c'est là que coulent les particules.
- Points d'opération : `clamp(9px, 2.4vh − 10px, 17px)` ; un point carré = action irréversible (gate) ; anneau bleu creux = vérifié.

## Mouvement

Une seule courbe : `cubic-bezier(0.2, 0.8, 0.2, 1)`. Jamais de rebond. Les animations de causalité sont inchangées par la refonte.

| Registre | Durées | Exemples |
|---|---|---|
| Ambiance | 3,2–54 s, continu | horizon, respiration des points, particules (46 px/s) |
| Causalité | 0,3–0,7 s par étape (flux SSE à 0,6 s) | trait corail parent → enfant, enveloppe scellée (aussi d'un registre à l'autre pour un signalement qualité), onde de déclaration, cadenas, flash ambre |
| Micro-interactions | 160–240 ms | survol, focus, menus, tiroir (300 ms), écran « avec vs sans » (260 ms) |

`prefers-reduced-motion` : horizon, respiration et particules s'arrêtent ; les traits apparaissent en fondu.

## Logo

Une **grille de points** (les opérations, la forêt) **coupée par une barre verticale** (le pare-feu) : deux colonnes de trois points à gauche, la barre, une colonne estompée à droite (`web/app/icons.js` → `logo()`, `web/app/favicon.svg`).

- Monochrome blanc. Une seule animation, à l'ouverture, 2,2 s, jamais en boucle : les points de gauche passent au corail l'un après l'autre, la barre se dresse, puis tout revient au blanc ; la colonne de droite n'est jamais touchée.

## Icônes

Jeu custom (`web/app/icons.js`) : grille 24 px, trait 1,4 px, bouts et jointures arrondis, `currentColor`, **jamais de cadre ni de fond**.

- Familles d'opérations : commande, avis d'expédition, certificat, facture, paiement, lot, expédition, réception, opérations internes.
- Entreprises : usine (fournisseur), engrenage (fabricant), camion (distributeur), boutique (client).
- Sémantique : cadenas (gate), bouclier coché (vérifié), enveloppe scellée (alerte ou signalement signé) et sa variante barrée, goutte (contamination), cercle pointillé (quarantaine), flèche de retour (levée), cloche barrée (fausse alerte), chaîne (journal d'audit), deux rectangles (avec / sans).

## Composants clés

| Composant | Rôle |
|---|---|
| En-tête | sans fond : logo, « Voir comme », scénario, indicateur d'IA, Avalanche (si actif), Importer, Réinitialiser ; ligne de progression blanche de 1 px dessous |
| Chiffres | trois grands nombres fins, sans cadre, séparés de la carte par un filet ; étiquettes en Geist Mono majuscules |
| Carte | 4 colonnes flottantes, un filet en tête de chaque colonne (corail si l'entreprise est compromise, avec l'étiquette « Compromis ») |
| Dock d'action | pilule flottante en bas, floutée : un seul bouton primaire **blanc** avec un point corail qui pulse (« Déclarer… »), puis « Avec vs sans » et « Fausse alerte » |
| Incident qualité | scénarios `lot` et `recall` : le dock guide les gestes humains (« Étape 2/6 · Distributeur ») : signaler, confirmer, remonter, analyser l'origine, isoler le lot, signaler au fournisseur, confirmation. Le fournisseur n'est jamais blacklisté |
| Analyse de rappel | tiroir : causes possibles d'un produit en cause, impact d'un rappel, « cause probable » en corail, bouton « Isoler » |
| Fil d'événements | colonne de droite séparée par un filet, icônes sans cadre, une ligne par étape SSE, cliquable vers la preuve |
| Preuve | tiroir plein : faits, chemin de contamination (nœuds ronds), explication IA, plan de reprise |
| Avec / sans | deux panneaux pleins qui glissent des bords, mini-cartes, jauges fines précision / rappel |
| Journal d'audit | tiroir : chaîne d'entrées `#i · prev → hash`, onglets en pilule, vérification |
| Import | tiroir : dépôt de document, exemples, proposition de l'IA, confirmation humaine |
| Avalanche (optionnel) | pastille dans l'en-tête, tiroir des ancrages (confirmé = bleu, en cours = ambre, échec = corail) ; rien n'est affiché si la chaîne est éteinte |
| Toasts, skeletons | surface pleine ; skeleton à balayage discret, jamais de spinner seul |
| Mode allégé | si les images ralentissent, le dock et l'écran « avec vs sans » perdent leur flou |

## Écrans testés

1920×1080 (projecteur) et 1440×900 (portable), sans défilement horizontal.
