# Design System — FIREBREAK

> Source de vérité du design. Synchro avec l'interface finale `web/app/` (servie sur `http://localhost:8000/app/`).
> Les slides du pitch reprennent ces valeurs à l'identique. Trois adjectifs à vérifier sur chaque écran : **tech, calme, prouvable**.

## Principes

- **Salle de contrôle la nuit** : fond bleu nuit, une aurore lente derrière, des panneaux de verre par-dessus.
- **Le verre hiérarchise** : un panneau de verre = une surface que l'on manie. Le fond = le monde qui vit.
- **Le verre ne porte jamais de texte long** : le texte long va sur une *surface opaque* à l'intérieur du panneau.
- **Quatre couleurs sémantiques, pas une de plus.** Chaque couleur signifie toujours la même chose.
- **Aucun chiffre inventé** : tout nombre affiché vient de l'API (`docs/api.md`) ; les chiffres du banc viennent de `docs/bench-results.md`.

## Couleurs

| Rôle | Valeur | Usage |
|---|---|---|
| Fond profond | `#070c18` | bas de page, jamais de noir pur |
| Fond haut | `#0b1424` | dégradé radial depuis le haut |
| Aurore | bleu `rgba(38,82,196,.55)`, cyan `rgba(28,170,200,.32)`, violet `rgba(110,76,230,.30)` | trois halos flous (90 px), dérive 46–64 s |
| Trame | blanc 2,5 %, pas de 48 px | grille de cockpit, masquée en radial |
| **Sain / continue** | `#5ce1b2` (vert menthe) | points sains, particules, « paiements qui continuent » |
| **Contaminé / bloqué** | `#ff6b5f` (rouge corail) | points bloqués, arêtes coupées, bouton de déclaration ; jamais plus de 15 % de l'écran |
| **En reprise / libéré** | `#f6b54c` (ambre) | remédiation, levée en cascade (transitoire) |
| **Accent** | `#3ddcff` (cyan électrique) | focus, liens, signatures vérifiées, boutons primaires, ligne de progression |
| Texte principal | blanc 92 % | |
| Texte secondaire | blanc 60 % | contraste ≥ 4,5:1 sur le verre |
| Texte tertiaire | blanc 40 % | décoratif seulement (compteurs de famille) |

Contrastes calculés (WCAG), sur le fond `#0b1424` puis sur le verre posé dessus : menthe 11,3 / 9,5 · corail 6,6 / 5,5 · ambre 10,2 / 8,6 · cyan 11,3 / 9,5 · texte principal 15,6 / 13,3 · texte secondaire 7,1 / 6,5. Le texte tertiaire (3,8:1) ne porte jamais d'information indispensable.

## Verre (une seule recette, partout)

```css
background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,0) 38%), rgba(255,255,255,.07);
backdrop-filter: blur(28px) saturate(140%);
border: 1px solid rgba(255,255,255,.12);
border-radius: 18px;
box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 0 24px 60px -28px rgba(0,0,0,.65);
```

**Surface opaque** (texte long, explications, faits) : `rgba(9,14,27,.82)`, bordure blanc 8 %, rayon 12 px.

## Typographie

Polices auto-hébergées dans `web/app/fonts/` (aucun réseau externe pendant la démo).

| Rôle | Police | Graisses | Tailles |
|---|---|---|---|
| Titres, chiffres | **Space Grotesk** | 500, 600 | gros chiffres 56–66 px (`clamp(40px, 3.5vw, 66px)`), titres 15–20 px |
| Texte courant | **Inter** | 400, 500, 600 | 15 px, interligne 1,5 ; libellés 12–13,5 px |
| Identifiants, jetons, hash, heures | **JetBrains Mono** | 400, 500 | 0,86 em ; jeton tronqué `7d4b…5efba` |

- Chiffres en `font-variant-numeric: tabular-nums` (ils ne sautent pas en s'incrémentant).
- Pas de graisse light sur fond sombre.
- Nom de marque : `FIREBREAK` en Space Grotesk 600, 17 px, lettres espacées de 0,32 em. Sous-titre : « Pare-feu des supply chains ».
- Tout est en français ; les identifiants techniques restent tels quels.

## Espacement et rayons

- Grille de 4 px. Marges de scène 20 px, gouttières 16 px (12 px sous 940 px de haut).
- Rayons : panneaux 18 px · contrôles 12 px · petites surfaces 8–10 px · pastilles 999 px.
- Entre les colonnes de la carte : `clamp(32px, 3vw, 64px)` — c'est là que coulent les particules.
- Points d'opération : `clamp(10px, 1,45vh, 15px)` ; un point carré = action irréversible (gate) ; anneau cyan = vérifié.

## Mouvement

Une seule courbe : `cubic-bezier(0.2, 0.8, 0.2, 1)`. Jamais de rebond.

| Registre | Durées | Exemples |
|---|---|---|
| Ambiance | 3,8–64 s, continu | aurore, respiration des points, particules (46 px/s) |
| Causalité | 0,3–0,6 s par étape (flux SSE à 0,6 s) | trait corail parent → enfant, enveloppe scellée, onde de déclaration, cadenas qui se ferme, flash ambre |
| Micro-interactions | 160–240 ms, ease-out | survol, focus, menus, tiroir (300 ms), écran « avec vs sans » (260 ms) |

`prefers-reduced-motion` : aurore, respiration et particules s'arrêtent ; les traits apparaissent en fondu.

## Logo

Une ligne de points liés, **interrompue par une barre** : le pare-feu forestier qui arrête l'incendie (`web/app/icons.js` → `logo()`, `web/app/favicon.svg`).

- Monochrome blanc par défaut ; déclinaisons corail (points touchés) et cyan (barre).
- Une seule animation, à l'ouverture, 2 s, jamais en boucle : les deux premiers points passent au corail, le lien avance, la barre tombe en cyan et l'arrête, puis tout revient au blanc.

## Icônes

Jeu custom (`web/app/icons.js`) : grille 24 px, trait 1,5 px, bouts et jointures arrondis, mono-trait, `currentColor`.

- Familles d'opérations : commande, avis d'expédition, certificat, facture, paiement, lot, expédition, réception, opérations internes.
- Entreprises : usine (fournisseur), engrenage (fabricant), camion (distributeur), boutique (client).
- Sémantique : cadenas (gate), bouclier coché (vérifié), enveloppe scellée (alerte signée) et sa variante barrée (signature rejetée), goutte (contamination), cercle pointillé (quarantaine), flèche de retour (levée), cloche barrée (fausse alerte), chaîne (journal d'audit), deux rectangles (avec / sans).

## Composants clés

| Composant | Rôle |
|---|---|
| En-tête | verre fin fixe : logo, « Voir comme », scénario, indicateur d'IA, Avalanche (si actif), Importer, Réinitialiser ; ligne de progression cyan dessous |
| Chiffres | trois gros nombres : opérations bloquées, paiement frauduleux bloqué (€), paiements qui continuent (€) |
| Carte | 4 colonnes de verre (fournisseur → client), points regroupés par famille, particules dans les gouttières |
| Bouton de déclaration | seul bouton corail au repos, halo qui pulse |
| Fil d'événements | colonne de droite, une ligne par étape SSE, cliquable vers la preuve |
| Preuve | tiroir latéral : faits, chemin de contamination, explication IA, plan de reprise |
| Avec / sans | deux panneaux qui glissent des bords, mini-cartes hachurées, jauges précision / rappel |
| Journal d'audit | tiroir : chaîne d'entrées `#i · prev → hash`, vérification |
| Import | tiroir : dépôt de document, exemples, proposition de l'IA, confirmation humaine |
| Toasts, skeletons | verre ; skeleton avec balayage lumineux, jamais de spinner seul |

## Écrans testés

1920×1080 (projecteur) et 1440×900 (portable), sans défilement horizontal.
