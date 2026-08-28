# -*- coding: utf-8 -*-
"""conftest.py – Root pytest configuration & environment setup."""

import os
import sys
import pytest

# Windows: Tcl/Tk-Pfade für Tkinter / CustomTkinter in venvs automatisch konfigurieren
if sys.platform.startswith("win"):
    base_tcl = os.path.join(sys.base_prefix, "tcl")
    if os.path.exists(base_tcl):
        for item in os.listdir(base_tcl):
            if item.startswith("tcl8.") and "TCL_LIBRARY" not in os.environ:
                os.environ["TCL_LIBRARY"] = os.path.join(base_tcl, item)
            if item.startswith("tk8.") and "TK_LIBRARY" not in os.environ:
                os.environ["TK_LIBRARY"] = os.path.join(base_tcl, item)


@pytest.fixture(scope="session")
def app_root():
    """Initialisiert eine headless CustomTkinter Root Instanz für alle GUI-Tests."""
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass
