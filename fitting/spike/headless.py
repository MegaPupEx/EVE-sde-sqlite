"""Bootstrap pyfa's eos for headless use — no wxPython, no GUI, no saveddata on disk.

Usage: call bootstrap(pyfa_path) before importing anything from eos.

What this does and why (the spike's findings, in code):
- eos itself has no top-level GUI imports; the only wx dependency reaches it
  via eos/db/migration.py -> root config.py -> `import wx`, which uses wx
  solely for Colour UI constants. A 3-line stub satisfies it.
- eos/config.py checks sys._called_from_test and puts the saveddata DB
  in :memory: — pyfa's own CI hook, reused here.
- Root config.py also imports `cryptography` (ESI token storage): a real
  dependency, installed rather than stubbed.
"""
import sys
import types


def bootstrap(pyfa_path):
    sys._called_from_test = True  # eos/config.py: saveddata in :memory:

    if 'wx' not in sys.modules:
        wx = types.ModuleType('wx')

        class Colour:
            def __init__(self, *args, **kwargs):
                pass

        wx.Colour = Colour
        sys.modules['wx'] = wx

    if pyfa_path not in sys.path:
        sys.path.insert(0, pyfa_path)
