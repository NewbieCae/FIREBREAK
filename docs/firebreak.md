# FIREBREAK — Le pare-feu des supply chains

**Track 3 · Uncharted Frontiers** — Cyberdéfense × IA × Industrie

> Quand un partenaire est compromis, on isole ce qui est contaminé, pas toute l'activité.

## En une phrase

Firebreak empêche qu'une compromission chez une entreprise se propage à ses clients, fournisseurs et partenaires, en mettant en quarantaine **uniquement les opérations contaminées** et en laissant tourner tout le reste.

## Le problème

Les entreprises d'une même chaîne d'approvisionnement échangent des données en continu : commandes, niveaux de stock, confirmations de livraison, mises à jour de catalogue. Si l'une d'elles est compromise, elle peut injecter de fausses informations dans les processus de ses partenaires.

Exemple fictif : quatre entreprises connectées entre elles. Un fournisseur piraté envoie de fausses confirmations de livraison et des stocks falsifiés. Ces données alimentent des commandes, des paiements et des expéditions chez ses partenaires, qui les traitent comme fiables.

Face à ça, les partenaires n'ont aujourd'hui que deux options : tout couper avec le fournisseur, et paralyser l'activité, ou continuer, et laisser passer l'attaque.

## Ce qui existe, et ce qui manque

La gestion du risque fournisseur existe déjà. [SecurityScorecard](https://securityscorecard.com), par exemple, propose de la surveillance et de la réponse aux incidents de supply chain.

Ces outils répondent à la question **« quel fournisseur est dangereux ? »**. Firebreak répond à une question plus fine : **« quelles opérations précises ont été contaminées par les données de ce fournisseur ? »**.

> Si une attaque touche 3 commandes sur 100, pourquoi bloquer les 100 ?

## Comment ça marche

1. **Traçabilité.** Chaque entreprise installe un composant léger qui enregistre la provenance des événements métiers : de quelle source vient chaque donnée, et quelles opérations l'ont utilisée.
2. **Graphe de dépendances.** Ces enregistrements forment un graphe qui relie chaque opération aux données dont elle dépend.
3. **Déclaration de compromission.** Quand une source est déclarée compromise, Firebreak parcourt le graphe à partir de cette source.
4. **Confinement ciblé.** Firebreak :
   - identifie les opérations qui dépendent, directement ou indirectement, des données suspectes ;
   - met ces opérations en quarantaine ;
   - laisse passer les opérations indépendantes, qui restent autorisées.
5. **Alerte des partenaires.** Firebreak envoie des alertes signées aux partenaires concernés, sans divulguer leurs données commerciales.
6. **Remédiation.** L'IA prépare un plan de reprise pour chaque opération en quarantaine : revalidation, validation humaine ou reprise depuis une source de confiance.

## Principe clé : des règles qui décident, une IA qui explique

- **Le cœur technique est un graphe de dépendances**, pas un chatbot qui attribue des scores de risque.
- **La décision de blocage repose sur des règles vérifiables** : une opération est mise en quarantaine parce qu'elle dépend d'une source compromise, et on peut montrer le chemin exact dans le graphe.
- **L'IA intervient en soutien** : elle interprète les documents (bons de commande, avis d'expédition, mails fournisseurs), explique l'impact de l'incident et propose les actions de reprise.

Résultat : un confinement auditable, explicable, et qui préserve la continuité d'activité.
