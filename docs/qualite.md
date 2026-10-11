# FIREBREAK — incidents qualité : lot défectueux et rappel produit

> Fiche pour le pitch et la démo. Même règle que `docs/pitch-firebreak.md` : les seuls chiffres sont ceux de l'écran (scénarios `lot` et `recall`, déterministes) ou des mesures citées ici avec leur source.

## L'idée en une phrase

Un problème qualité ne se traite pas en coupant un fournisseur : on isole **le lot en cause**, au cas par cas, sur décision humaine — et l'alerte peut partir **dans les deux sens** de la chaîne.

## Pourquoi c'est important

- C'est le même problème que la cyber (« qu'est-ce qui dépend de cette donnée ? »), mais il arrive **tous les jours** dans l'industrie : défaut matière, faux certificat, analyse qualité tardive.
- Cas réels, à citer comme exemples publics : **Kobe Steel (2017)**, données de résistance falsifiées sur des lots précis d'aluminium et de cuivre, ~688 clients concernés selon l'enquête de l'entreprise ; **AOG Technics (2023)**, pièces de moteurs CFM56 vendues avec de faux certificats, retrouvées moteur par moteur (de 68 à 126 moteurs selon les sources). Dans les deux cas, la question était : *quels produits contiennent ces lots-là ?*
- Ça élargit le marché : qualité et rappels produit, pas seulement cybersécurité.

## Les deux sens

| Sens | Exemple | Ce que fait Firebreak |
|---|---|---|
| **Vers l'aval** | Le contrôle réception du fabricant découvre un défaut sur une bobine du fournisseur. | Il déclare **ce lot** suspect : seul ce lot et ce qui en dépend est isolé, chez lui puis chez ses clients (alertes signées). Le fournisseur, ses autres lots et ses factures continuent. |
| **Vers l'amont** | Le client constate une casse sur chantier, sur un produit livré depuis longtemps. | Il envoie un **signalement qualité signé** au maillon précédent, qui retrouve ses propres opérations, décide (confirmer ou rejeter), et remonte à son tour. Le fabricant analyse la généalogie, désigne la bobine en cause : tous les produits fabriqués avec elle, même déjà expédiés, sont isolés. |

Un signalement ne bloque rien tout seul : c'est toujours le destinataire qui décide. Il ne contient que des jetons opaques, jamais de données commerciales.

## Déroulé de démo (scénario `recall`, ~60 s)

Panneau « Qualité » du tableau de bord (ou interface finale si Yann l'a intégré).

1. **Repos** : « Une chaîne qui tourne, personne n'est compromis. »
2. **Le client signale** une casse sur la livraison du lot LOT-503 → signalement signé vers le distributeur. « Le client ne connaît pas la bobine : il signale ce qu'il a reçu. »
3. **Le distributeur confirme** → la livraison et le paiement du client pour ce lot sont mis en attente. Il **remonte** au fabricant.
4. **Le fabricant analyse** : l'écran liste les causes possibles (bobine COIL-103, documents reçus du fournisseur) avec le périmètre de chacune. L'analyste choisit la bobine. « C'est l'humain qui désigne la cause. »
5. **Bobine déclarée suspecte** → le lot frère LOT-A30, fabriqué avec la même bobine et déjà expédié, est isolé aussi. Les autres lots continuent.
6. **Signalement au fournisseur**, qui confirme. « À aucun moment le fournisseur n'a été blacklisté : ses autres livraisons et ses factures passent. »
7. Si la chaîne est active : « Chaque signalement, chaque décision et chaque accusé de réception est ancré sur notre L1 Avalanche. »

Chiffres affichés par la démo (scénario `recall`, à relire à l'écran) : 20 opérations isolées au total à la fin du parcours.

## Phrases pour le pitch

- « Un défaut qualité, ce n'est pas une raison de couper un fournisseur. Firebreak isole le lot, pas l'entreprise. »
- « L'alerte remonte aussi : du chantier jusqu'à la bobine, maillon par maillon, et chacun décide chez lui. »
- « Ce qu'on fait pour une cyberattaque, on le fait pour un rappel produit : même graphe, mêmes preuves. »

## Questions probables

- **« Qui décide qu'un lot est suspect ? »** Un humain (contrôle qualité, analyste). Firebreak calcule le périmètre et propose les causes ; il ne déclare rien seul.
- **« Et si le signalement est abusif ? »** Le destinataire le rejette : rien n'est bloqué chez lui. Les signalements sont signés et ancrés : on sait qui a signalé quoi, et quand.
- **« Le fournisseur voit-il mes données ? »** Non : il reçoit des jetons qu'il est seul à pouvoir relier à ses propres envois.
- **« Un contrôle à réception déjà validé ? »** Une déclaration explicite prime : un défaut découvert après coup rouvre le dossier.

## Mesures sur la vraie L1 (scénario `recall`, 11/10 vers 04 h)

Parcours complet (client → distributeur → fabricant → fournisseur) : 25 preuves ancrées, 0 échec au premier passage, vérification locale et Avalanche conformes ; l'API répond en 0,1 s pour les gestes, la file d'ancrage se vide en ~86 s après optimisation (~130 s avant), 25/25 confirmées (limite restante : débit du nœud hébergé). Détails : `docs/avalanche/pitch.md`.

## Limites à dire

- Tout est simulé ; scénarios déterministes.
- La généalogie n'est fiable que si les transformations (lots consommés → lot produit) sont enregistrées.
- Pas encore de mesure chiffrée « qualité » dans le banc d'essai de Céline (il porte sur des compromissions d'entreprise).

## Contrôle des entrées en stock : prévenir plutôt que contenir

À la réception d'une livraison, Firebreak donne une **note de confiance /100** au lot, en croisant le référentiel (commande ouverte ?, bonne pièce et nomenclature ?, quantité, date, certificat présent et cohérent, numéro de certificat dans la séquence habituelle, numéro de lot inédit, RIB conforme à la fiche, alertes en cours). Chaque point retiré a sa raison, affichée en clair. **Sous 80, le lot est mis en attente** : rien de ce qui en dépend ne peut avancer tant qu'un humain n'a pas accepté (le lot devient fiable) ou refusé (le lot reste isolé et un signalement signé part au fournisseur).

Résultats sur les scénarios (déterministes) : les 7 livraisons du matin ont 100/100 ; la bobine piégée de l'attaque mixte a **30/100** (commande BC-9999 inconnue, certificat hors séquence, RIB modifié) ; la livraison fantôme **40/100** ; le faux certificat **55/100** (nuance S355 au lieu de S235). **Sur les trois attaques, le lot piégé aurait été arrêté à la réception, avant toute production.**

Phrase pour le pitch : « Avant même qu'un lot piégé n'entre en stock, Firebreak le note, explique pourquoi il doute, et le met en attente. L'humain tranche. »

Réponse à « Où est l'IA ? » : la note vient de règles explicables (reproductibles, défendables devant un auditeur) ; l'IA rédige l'explication et lit les documents désordonnés. Elle ne décide jamais.

Mesure sur la vraie L1 (11/10, 05 h 30, scénario mixte) : crible des réceptions en 32 ms, refus de la bobine piégée (signalement au fournisseur) et acceptation de la livraison légitime ; 16 preuves ancrées en ~25 s, 0 échec, vérification locale et Avalanche conformes.
