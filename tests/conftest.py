# -*- coding: utf-8 -*-
"""tests/conftest.py – Global pytest configuration & environment setup."""

import os
import sys

# Windows: Tcl/Tk-Pfade für Tkinter / CustomTkinter in venvs automatisch konfigurieren
if sys.platform.startswith("win"):
    base_tcl = os.path.join(sys.base_prefix, "tcl")
    if os.path.exists(base_tcl):
        for item in os.listdir(base_tcl):
            if item.startswith("tcl8.") and "TCL_LIBRARY" not in os.environ:
                os.environ["TCL_LIBRARY"] = os.path.join(base_tcl, item)
            elif item.startswith("tk8.") and "TK_LIBRARY" not in os.environ:
                os.environ["TK_LIBRARY"] = os.path.join(base_tcl, item)
