"""Garde-fou commun à toute la suite.

`api.py` charge `.env.local` au démarrage. Sur une machine où ce fichier
active la vraie L1 (`FIREBREAK_CHAIN=l1`), les tests enverraient de vraies
transactions. Une variable d'environnement l'emporte toujours sur
`.env.local` : on force donc la chaîne désactivée avant tout import. Les tests
de la chaîne construisent explicitement leur configuration (`tester`).
"""

import os

os.environ["FIREBREAK_CHAIN"] = "off"
