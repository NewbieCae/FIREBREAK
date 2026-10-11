"""Anchoring Firebreak evidence on an Avalanche L1.

The chain decides nothing and blocks nothing: it serves as a timestamped
witness for audit journals, signed alerts and incident declarations.
Disabled by default (`FIREBREAK_CHAIN=off`); in that mode, no network
module (`web3`, `eth_account`) is imported.
See docs/avalanche/README.md.
"""
