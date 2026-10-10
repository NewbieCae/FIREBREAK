# FIREBREAK — Le pare-feu des supply chains

Track 3 · Uncharted Frontiers · Cyberdéfense × IA × Industrie

L'idée : lorsqu'une entreprise est compromise, empêcher que l'attaque se propage à ses clients, fournisseurs et partenaires, sans interrompre toute leur activité.

## 1. Le problème

Imagine quatre entreprises connectées numériquement.

Exemple fictif : un fournisseur compromis injecte de fausses informations dans les processus de ses partenaires.

Aujourd'hui, la gestion du risque fournisseur existe déjà. [SecurityScorecard](https://securityscorecard.com) propose notamment de la surveillance et de la réponse aux incidents de supply chain.

Mais notre angle serait différent : ne pas seulement déterminer quel fournisseur est dangereux, mais quelles opérations précises ont été contaminées par les informations provenant de ce fournisseur.

> Si une attaque affecte 3 commandes sur 100, pourquoi immobiliser les 100 ?

## 2. Le fonctionnement de Firebreak

Chaque entreprise possède un petit composant qui suit la provenance des événements de ses processus métiers : commandes, changements de stock, confirmations de livraison ou mises à jour fournisseurs.

Lorsqu'une source est déclarée compromise, Firebreak :

- Identifie les opérations qui dépendent des données suspectes.
- Met en quarantaine les opérations concernées.
- Préserve les opérations indépendantes qui restent autorisées.
- Transmet des alertes signées aux partenaires concernés, sans publier leurs données commerciales.
- Prépare une réponse avec l'IA : revalidation, intervention humaine ou reprise par une source de confiance.

Le cœur technique est un graphe de dépendances entre opérations, pas un chatbot qui attribue des scores de risque.

L'IA sert à interpréter des documents et à expliquer les impacts. Le blocage lui-même dépend de règles vérifiables.
