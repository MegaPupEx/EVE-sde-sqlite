"""EFT parse / build / render over pyfa's eos — no service layer, no GUI.

pyfa's own EFT importer (service/port/eft.py) imports wx-entangled service
and gui modules, so the MCP wraps this instead. Three functions:

    parse_eft(text)   -> list of FitSpec (neutral dicts; no eos needed)
    build_fit(spec)   -> eos Fit, calculated-ready (bootstrap first)
    render_eft(fit)   -> EFT text from a live eos fit

Dialect: standard EFT as the game client and pyfa emit it. Lines are
classified by item category (the pyfa approach), not by section position, so
shuffled sections import fine. "Module, Charge" splits are resolved by
lookup, trying rightmost commas first, which survives item names containing
commas. "/offline" suffix and "[Empty ... slot]" placeholders are handled.
Quantity lines ("Hobgoblin II x5") become drones/fighters/cargo by category.

Mutated (abyssal) modules are NOT supported yet — the pyfa mutation dialect
is a planned v1 item (roadmap open question); lines referencing unknown
items raise EftError naming the line, so mutated fits fail loudly, not
silently.
"""


class EftError(Exception):
    pass


class FitSpec:
    def __init__(self, ship, name):
        self.ship = ship
        self.name = name
        self.entries = []  # dicts: {'name', 'charge', 'offline', 'quantity'}

    def __repr__(self):
        return f'FitSpec({self.ship!r}, {self.name!r}, {len(self.entries)} entries)'


def parse_eft(text):
    """Parse EFT text (one or many fits) into FitSpecs. Pure text handling."""
    fits = []
    fit = None
    for rawline in text.splitlines():
        line = rawline.strip()
        if not line:
            continue
        if line.startswith('[') and ',' in line and line.endswith(']'):
            ship, name = line[1:-1].split(',', 1)
            fit = FitSpec(ship.strip(), name.strip())
            fits.append(fit)
            continue
        if line.startswith('[') and line.endswith(']'):  # [Empty Low slot] etc.
            continue
        if fit is None:
            raise EftError(f'module line before any [Ship, name] header: {line!r}')
        entry = {'name': line, 'charge': None, 'offline': False, 'quantity': None}
        if entry['name'].endswith('/offline'):
            entry['offline'] = True
            entry['name'] = entry['name'][:-len('/offline')].strip()
        head, sep, tail = entry['name'].rpartition(' x')
        if sep and tail.isdigit():
            entry['name'] = head.strip()
            entry['quantity'] = int(tail)
        fit.entries.append(entry)
    if not fits:
        raise EftError('no [Ship, name] header found')
    return fits


def _lookup(name):
    import eos.db
    return eos.db.getItem(name)


def _resolve(entry):
    """Return (item, charge_item) for an entry, resolving 'Module, Charge'."""
    item = _lookup(entry['name'])
    if item is not None:
        return item, None
    # try splitting at each comma, rightmost first: module name may contain commas
    parts = entry['name'].split(',')
    for i in range(len(parts) - 1, 0, -1):
        mod_name = ','.join(parts[:i]).strip()
        charge_name = ','.join(parts[i:]).strip()
        item = _lookup(mod_name)
        if item is not None:
            charge = _lookup(charge_name)
            if charge is None:
                raise EftError(f'unknown charge {charge_name!r} on {mod_name!r}')
            return item, charge
    raise EftError(f'unknown item: {entry["name"]!r}')


def build_fit(spec):
    """Build a calculated-ready eos Fit from a FitSpec. Call bootstrap() first."""
    import eos.db  # noqa: F401 — must precede eos.saveddata imports
    from eos.const import FittingModuleState
    from eos.saveddata.booster import Booster
    from eos.saveddata.cargo import Cargo
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.fit import Fit
    from eos.saveddata.implant import Implant
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    ship_item = _lookup(spec.ship)
    if ship_item is None:
        raise EftError(f'unknown ship: {spec.ship!r}')
    fit = Fit(Ship(ship_item), name=spec.name)
    fit.character = Character.getAll5()
    fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25,
                                      kineticAmount=25, explosiveAmount=25)
    for entry in spec.entries:
        item, charge = _resolve(entry)
        category = item.category.name
        if entry['quantity'] is not None and category == 'Drone':
            drone = Drone(item)
            drone.amount = entry['quantity']
            drone.amountActive = entry['quantity']
            fit.drones.append(drone)
            drone.owner = fit
        elif entry['quantity'] is not None and category == 'Fighter':
            fighter = Fighter(item)
            fit.fighters.append(fighter)
            fighter.owner = fit
        elif entry['quantity'] is not None:
            fit.cargo.append(Cargo(item, entry['quantity']))
        elif category == 'Implant':
            if item.group.name == 'Booster':
                fit.boosters.append(Booster(item))
            else:
                fit.implants.append(Implant(item))
        elif category == 'Charge':
            fit.cargo.append(Cargo(item, 1))
        else:
            mod = Module(item)
            if charge is not None:
                mod.charge = charge
            if entry['offline']:
                mod.state = FittingModuleState.OFFLINE
            elif mod.isValidState(FittingModuleState.ACTIVE):
                mod.state = FittingModuleState.ACTIVE
            fit.modules.append(mod)
            mod.owner = fit
    return fit


def render_eft(fit):
    """Render a live eos fit as EFT text, slot-grouped the way pyfa exports."""
    from eos.const import FittingSlot
    order = (FittingSlot.LOW, FittingSlot.MED, FittingSlot.HIGH,
             FittingSlot.RIG, FittingSlot.SUBSYSTEM)
    slots = {s: [] for s in order}
    for mod in fit.modules:
        if mod.isEmpty:
            continue
        line = mod.item.typeName
        if mod.charge is not None:
            line += f', {mod.charge.typeName}'
        from eos.const import FittingModuleState
        if mod.state == FittingModuleState.OFFLINE:
            line += ' /offline'
        slots.setdefault(mod.slot, []).append(line)
    out = [f'[{fit.ship.item.typeName}, {fit.name}]']
    blocks = ['\n'.join(slots[s]) for s in order if slots[s]]
    out.append('\n\n'.join(blocks))
    extras = []
    for implant in fit.implants:
        extras.append(implant.item.typeName)
    for booster in fit.boosters:
        extras.append(booster.item.typeName)
    for drone in fit.drones:
        extras.append(f'{drone.item.typeName} x{drone.amount}')
    for cargo in fit.cargo:
        extras.append(f'{cargo.item.typeName} x{cargo.amount}')
    if extras:
        out.append('\n' + '\n'.join(extras))
    return '\n'.join(out) + '\n'
