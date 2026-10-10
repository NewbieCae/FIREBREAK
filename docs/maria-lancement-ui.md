# Maria : lancer le build de l'interface (UI/UX)

> Écrit par l'agent de Mika (pc2) pour Maria. Rendu dimanche 12 h, **gel du code à 10 h**, pitchs jusqu'à 17 h.
> Ce fichier ne remplace pas `sessions/maria.md` (à tenir à jour par ton agent).

## En deux mots

Le moteur et l'API sont livrés. Il manque **l'interface finale** : une « salle de contrôle d'incident » sombre, en verre, où un juré clique et comprend seul. Tout est décrit dans [`docs/brief-ui.md`](brief-ui.md) : lis-le en entier, c'est la commande. Le dashboard `web/index.html` est un outil de debug, à ne pas imiter, mais il montre chaque appel API qui marche.

## Mise en route (5 min)

```powershell
git clone git@github.com:Sc4rville/finswag.git   # ou git pull si déjà cloné
cd finswag
uv sync            # ou : python -m venv .venv ; .venv\Scripts\pip install -e . pytest httpx tzdata
$env:FIREBREAK_DEMO='1'; $env:PYTHONUTF8='1'
uv run uvicorn firebreak.api:app --port 8000   # puis http://localhost:8000
```

Sous Windows, `PYTHONUTF8=1` évite des échecs de tests (encodage cp1252).

## Ce que tu dis à ton agent (à coller tel quel)

```
Tu travailles sur FIREBREAK, hackathon Secure Horizons, équipe de 4. Je suis Maria.
Rendu dimanche 12 h, gel du code à 10 h. Ma mission : construire l'interface finale (UI/UX).

1. Lis dans cet ordre : AGENTS.md, goal.md, docs/firebreak.md, docs/brief-ui.md (c'est mon cahier
   des charges, à suivre à la lettre), docs/api.md (contrat de l'API, on ne le casse pas),
   docs/agents-canal.md (fin du fichier), web/index.html (exemples d'appels qui marchent).
2. Inscris-toi dans sessions/maria.md et goal.md : tâche « Interface finale (UI/UX) ».
   Ne touche pas au moteur (engine, federation, simulation, audit) ni à api.py : si tu as besoin
   d'un champ ou d'un endpoint, écris-le dans docs/agents-canal.md et demande à Yann.
3. Fichiers à moi : un dossier web/app/ (ou web/ui/) et design.md. Ne remplace pas
   web/index.html tant que la nouvelle UI n'est pas prête : garde-le comme secours.
4. Livre en 4 étapes, une démo qui marche à la fin de chacune, un commit à chaque étape :
   a) Squelette : fond sombre + dégradé lent, en-tête (sélecteur de scénario, Réinitialiser,
      indicateur IA), 3 gros chiffres (/api/state counters.global), carte des 4 entreprises.
   b) Propagation : bouton de compromission, flux SSE /api/events, particules sur les arêtes
      cross, rouge corail précis, compteurs animés (tabular-nums).
   c) Preuve et guérison : clic sur une opération bloquée -> chemin exact + explication
      (/explain), remédiation, cascade de levée en ambre puis vert, fausse alerte.
   d) Avec/sans Firebreak (côte à côte), logo animé (une fois), jeu d'icônes cohérent,
      skeletons, toasts d'erreur en français, prefers-reduced-motion.
5. Règles de design non négociables : 4 couleurs sémantiques (sain vert menthe, bloqué rouge
   corail < 15 % de l'écran, reprise ambre, accent cyan), verre = une seule recette, jamais de
   texte long sur le verre, contraste >= 4,5:1, tout en français, mono pour hash/jetons.
   Consigne les choix finaux dans design.md.
6. Teste en vrai : lance le serveur, ouvre la page dans le navigateur, déroule la démo de
   3 minutes (section 6 du brief), vérifie qu'aucune erreur n'apparaît en console.
7. Pas de dépendance lourde : choisis ce qui est le plus rapide (HTML/CSS/JS natif ou Vite).
   Si un build est nécessaire, committe le résultat pour que le serveur le serve sans Node.
8. Tiens sessions/maria.md à jour à chaque étape. Pas de force-push. Commits courts en français.
```

## Prévoir dès maintenant : le panneau Avalanche

Mika intègre une blockchain Avalanche L1 (ancrage des journaux d'audit et des alertes). Elle ajoute des endpoints **optionnels** à l'API, jamais bloquants :

| Endpoint | Pour l'UI |
|---|---|
| `GET /api/chain/status` | `mode` (off/tester/l1), `connected`, `chain_id`, `queue` : badge « Avalanche » dans l'en-tête |
| `GET /api/chain/anchors` | liste d'ancrages (type, entreprise, hash, statut, `explorer_link`) : panneau « Preuves sur Avalanche » |
| `GET /api/audit/verify` | champ `onchain` par journal + `onchain_ok` : coche « ancré sur Avalanche » dans la vue preuve |
| `POST /api/demo/rewrite` | démo : réécriture d'un journal ; local = intègre, on-chain = **ne correspond pas** |

Règles côté UI : si `mode` vaut `off` ou si `onchain` est `null`, **n'affiche rien** (pas de panneau vide). Un statut `pending` ou `failed` est un état normal, pas une erreur. Le contrat détaillé est dans `docs/avalanche/` (branche `mika/avalanche-l1`) ; Mika branche le panneau lui-même dans `web/index.html`, ton design reprendra les mêmes données quand la chaîne sera fusionnée.

## Coordination

- Questions, besoins d'API : `docs/agents-canal.md` (ajout seul en bas, signe `maria/…`).
- Conflit de décision : voir `AGENTS.md` et le canal.
- Calendrier : démo jouable à **9 h** dimanche, polish jusqu'au gel de **10 h**, plus rien après.
