"""Safety net shared by the whole suite.

`api.py` loads `.env.local` at startup. On a machine where that file
enables the real L1 (`FIREBREAK_CHAIN=l1`), the tests would send real
transactions. An environment variable always wins over `.env.local`, so
the chain is forced off before any import. The chain tests build their
configuration explicitly (`tester`).
"""

import os

os.environ["FIREBREAK_CHAIN"] = "off"
