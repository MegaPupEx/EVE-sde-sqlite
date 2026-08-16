# Minimal wx stand-in for headless eos use. pyfa's root config.py imports wx
# only for Colour UI constants; nothing else reaches wx from eos code paths.
class Colour:
    def __init__(self, *args, **kwargs):
        pass
