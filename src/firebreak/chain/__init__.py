"""Ancrage des preuves Firebreak sur une L1 Avalanche.

La chaîne ne décide rien et ne bloque rien : elle sert de témoin horodaté
pour les journaux d'audit, les alertes signées et les déclarations
d'incident. Désactivée par défaut (`FIREBREAK_CHAIN=off`) ; dans ce mode,
aucun module réseau (`web3`, `eth_account`) n'est importé.
Voir docs/avalanche/README.md.
"""
