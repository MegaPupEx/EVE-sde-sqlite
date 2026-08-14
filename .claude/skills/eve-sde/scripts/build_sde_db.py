#!/usr/bin/env python3
"""
Build a queryable SQLite database from the EVE Online Static Data Export (SDE).

Downloads the current SDE from CCP's official distribution, then flattens the
JSONL files into a normalised SQLite database with indexes.

    python3 build_sde_db.py                 # 25 core tables + meta -> ./sde.sqlite, ~92 MB
    python3 build_sde_db.py --complete      # all 107 tables, ~137 MB
    python3 build_sde_db.py --complete --positions          # + 3D coords, ~162 MB
    python3 build_sde_db.py --complete --positions --split --parts-only --compress xz
                                            # the published form: one .xz per domain
    python3 build_sde_db.py --db eve.sqlite # custom output path
    python3 build_sde_db.py --keep-raw      # don't delete the extracted JSONL
    python3 build_sde_db.py --portable      # drop descriptions, unpublished types, moons

The default build omits most tables. Anything that documents typeBonus,
mapStars, planetSchematics, dogmaUnits or moon statistics assumes --complete.

Requires only the Python standard library. Downloads ~99 MB, needs ~1.5 GB of
temporary disk, and takes a couple of minutes end to end.

Localised strings ({"en": ..., "de": ...}) are reduced to English.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
import urllib.request
import zipfile

BASE = "https://developers.eveonline.com/static-data/tranquility"
WANT_POSITIONS = False
LATEST = f"{BASE}/latest.jsonl"


def log(msg):
    print(msg, flush=True)


def fetch(url, dest, attempts=8):
    """Download to a .part file with resume, verify it, then rename into place.

    Transfers of this size are routinely truncated part-way through, so a
    single-shot download is not reliable. The server advertises
    'accept-ranges: bytes', so each retry resumes from what is already on disk
    via a Range request rather than starting over. The file is only renamed to
    its final name once the byte count matches and the archive opens, so a
    partial transfer can never be cached and reused -- that would turn one bad
    download into a permanently failing build.
    """
    log(f"  GET {url}")
    tmp = dest + ".part"
    expected = None
    for attempt in range(1, attempts + 1):
        have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        req = urllib.request.Request(url)
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                # On a 206 the Content-Length is only the remaining bytes;
                # Content-Range carries the true total.
                if r.status == 206:
                    crange = r.headers.get("Content-Range", "")
                    if "/" in crange:
                        expected = int(crange.rsplit("/", 1)[1])
                    mode = "ab"
                else:
                    cl = r.headers.get("Content-Length")
                    expected = int(cl) if cl else expected
                    mode, have = "wb", 0
                with open(tmp, mode) as f:
                    shutil.copyfileobj(r, f)
        except Exception as e:
            log(f"  ! attempt {attempt}/{attempts}: {e}")

        got = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if expected and got == expected and zipfile.is_zipfile(tmp):
            os.replace(tmp, dest)
            log(f"  downloaded {got/1e6:.0f} MB")
            return dest
        if got <= have and attempt < attempts:
            time.sleep(min(2 ** attempt, 30))  # no progress; back off
        if expected:
            log(f"  resuming at {got/1e6:.0f}/{expected/1e6:.0f} MB")

    raise IOError(f"could not download {url} after {attempts} attempts "
                  f"({got:,} of {expected or 0:,} bytes)")


def latest_build():
    with urllib.request.urlopen(LATEST, timeout=60) as r:
        meta = json.loads(r.read().decode())
    return meta["buildNumber"], meta.get("releaseDate", "?")


def download_sde(workdir):
    build, released = latest_build()
    log(f"Current SDE build {build} (released {released})")
    zpath = os.path.join(workdir, f"sde-{build}.zip")
    raw = os.path.join(workdir, f"sde-{build}")
    if not os.path.isdir(raw):
        if os.path.exists(zpath) and not zipfile.is_zipfile(zpath):
            log("  cached archive is corrupt, discarding it")
            os.remove(zpath)
        if not os.path.exists(zpath):
            fetch(f"{BASE}/eve-online-static-data-{build}-jsonl.zip", zpath)
        log(f"  extracting {os.path.getsize(zpath)/1e6:.0f} MB ...")
        try:
            with zipfile.ZipFile(zpath) as z:
                z.extractall(raw)
        except zipfile.BadZipFile:
            shutil.rmtree(raw, ignore_errors=True)
            os.remove(zpath)
            raise SystemExit("Archive was corrupt and has been removed; re-run to retry.")
    else:
        log("  reusing already-extracted data")
    return raw, build, released


def rows(raw, name):
    """Stream one JSONL file as dicts. Returns [] if the file is absent."""
    path = os.path.join(raw, f"{name}.jsonl")
    if not os.path.exists(path):
        # some builds nest the files one level down
        for root, _, files in os.walk(raw):
            if f"{name}.jsonl" in files:
                path = os.path.join(root, f"{name}.jsonl")
                break
        else:
            log(f"  ! missing {name}.jsonl")
            return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def num(v):
    """Store whole numbers as integers.

    A REAL-affinity column forces every value into an 8-byte float, even 1.0.
    NUMERIC affinity keeps integers as 1-2 byte integers, which is roughly 7%
    off the compressed size across a database this float-heavy.
    """
    if isinstance(v, float) and v.is_integer() and abs(v) < 2**53:
        return int(v)
    return v


def en(v, default=None):
    """SDE localises many strings as {'en': ..., 'de': ...}."""
    if isinstance(v, dict):
        return v.get("en", default)
    return v if v is not None else default


LOCALES = {"de", "en", "es", "fr", "it", "ja", "ko", "ru", "zh"}


def strip_locales(v):
    """Recursively reduce every localised block to English.

    Localised text is not only at the top level -- mission `messages`, for
    instance, is a list of dicts each carrying eight languages. Keeping all of
    them makes that one table 53 MB instead of about 6 MB.
    """
    if isinstance(v, dict):
        if "en" in v and set(v) <= LOCALES:
            return v["en"]
        # Localised blocks are sometimes tagged with an identifier alongside the
        # languages (mission messages carry a _key). Keep the tag, drop the
        # other eight translations.
        if "en" in v and set(v) - {"_key"} <= LOCALES:
            return {"_key": v.get("_key"), "text": v["en"]}
        return {k: strip_locales(x) for k, x in v.items()}
    if isinstance(v, list):
        return [strip_locales(x) for x in v]
    return v


SCHEMA = """
PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;

CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE categories(categoryID INT PRIMARY KEY, name TEXT, published INT, iconID INT);
CREATE TABLE groups_(groupID INT PRIMARY KEY, name TEXT, categoryID INT, published INT,
  anchorable INT, anchored INT, fittableNonSingleton INT, useBasePrice INT, iconID INT);
CREATE TABLE types(
  typeID INT PRIMARY KEY, name TEXT, description TEXT, groupID INT, categoryID INT,
  mass NUMERIC, volume NUMERIC, capacity NUMERIC, radius NUMERIC, basePrice NUMERIC, published INT,
  marketGroupID INT, portionSize INT, raceID INT, factionID INT,
  metaGroupID INT, metaLevel INT, techLevel INT, variationParentTypeID INT,
  packagedVolume NUMERIC, isRepackable INT, shipTreeGroupID INT, graphicID INT,
  iconID INT, soundID INT);
CREATE TABLE dogma_attributes(
  attributeID INT PRIMARY KEY, name TEXT, displayName TEXT, description TEXT,
  defaultValue NUMERIC, highIsGood INT, stackable INT, published INT,
  unitID INT, attributeCategoryID INT, dataType INT, displayWhenZero INT,
  minAttributeID INT, maxAttributeID INT, chargeRechargeTimeID INT,
  tooltipTitle TEXT, tooltipDescription TEXT, iconID INT);
CREATE TABLE dogma_effects(
  effectID INT PRIMARY KEY, name TEXT, displayName TEXT, description TEXT,
  effectCategoryID INT, published INT, isOffensive INT, isAssistance INT,
  isWarpSafe INT, disallowAutoRepeat INT, electronicChance INT, propulsionChance INT,
  rangeChance INT, distribution INT, guid TEXT,
  durationAttributeID INT, dischargeAttributeID INT, rangeAttributeID INT,
  falloffAttributeID INT, trackingSpeedAttributeID INT, resistanceAttributeID INT,
  fittingUsageChanceAttributeID INT, npcUsageChanceAttributeID INT,
  npcActivationChanceAttributeID INT, modifierInfo TEXT, iconID INT);
CREATE TABLE type_dogma(typeID INT, attributeID INT, value NUMERIC);
CREATE TABLE type_effects(typeID INT, effectID INT, isDefault INT);
CREATE TABLE blueprints(blueprintTypeID INT PRIMARY KEY, maxProductionLimit INT);
CREATE TABLE bp_activity(blueprintTypeID INT, activity TEXT, time INT);
CREATE TABLE bp_materials(blueprintTypeID INT, activity TEXT, typeID INT, quantity INT);
CREATE TABLE bp_products(blueprintTypeID INT, activity TEXT, typeID INT, quantity INT, probability NUMERIC);
CREATE TABLE bp_skills(blueprintTypeID INT, activity TEXT, typeID INT, level INT);
CREATE TABLE type_materials(typeID INT, materialTypeID INT, quantity INT);
CREATE TABLE market_groups(marketGroupID INT PRIMARY KEY, parentGroupID INT, name TEXT,
  description TEXT, hasTypes INT, iconID INT);
CREATE TABLE meta_groups(metaGroupID INT PRIMARY KEY, name TEXT, description TEXT,
  color TEXT, iconID INT, iconSuffix TEXT);
CREATE TABLE regions(regionID INT PRIMARY KEY, name TEXT, description TEXT,
  factionID INT, wormholeClassID INT, nebulaID INT, x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE constellations(constellationID INT PRIMARY KEY, name TEXT, regionID INT,
  factionID INT, wormholeClassID INT, x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE systems(
  solarSystemID INT PRIMARY KEY, name TEXT, constellationID INT, regionID INT,
  security NUMERIC, securityClass TEXT, luminosity NUMERIC, radius NUMERIC,
  border INT, hub INT, regional INT, fringe INT, corridor INT, international INT,
  starID INT, factionID INT, wormholeClassID INT, visualEffect TEXT, space TEXT,
  x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE planets(
  planetID INT PRIMARY KEY, solarSystemID INT, celestialIndex INT, typeID INT, radius NUMERIC,
  density NUMERIC, surfaceGravity NUMERIC, escapeVelocity NUMERIC, temperature NUMERIC, pressure NUMERIC,
  orbitRadius NUMERIC, orbitPeriod NUMERIC, rotationRate NUMERIC, eccentricity NUMERIC,
  massDust NUMERIC, massGas NUMERIC, locked INT, fragmented INT, moons INT, belts INT,
  orbitID INT, x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE moons(moonID INT PRIMARY KEY, solarSystemID INT, planetID INT,
  celestialIndex INT, orbitIndex INT, typeID INT, radius NUMERIC,
  x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE asteroid_belts(beltID INT PRIMARY KEY, solarSystemID INT, planetID INT,
  celestialIndex INT, orbitIndex INT, typeID INT, radius NUMERIC,
  x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE stargates(stargateID INT PRIMARY KEY, solarSystemID INT,
  destStargateID INT, destSystemID INT, typeID INT, x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE npc_stations(stationID INT PRIMARY KEY, solarSystemID INT, ownerID INT,
  typeID INT, operationID INT, reprocessingEfficiency NUMERIC,
  reprocessingStationsTake NUMERIC, reprocessingHangarFlag INT, useOperationName INT,
  orbitID INT, celestialIndex INT, orbitIndex INT, x NUMERIC, y NUMERIC, z NUMERIC);
CREATE TABLE factions(factionID INT PRIMARY KEY, name TEXT, description TEXT,
  shortDescription TEXT, corporationID INT, militiaCorporationID INT, solarSystemID INT,
  memberRaces TEXT, sizeFactor NUMERIC, uniqueName INT, iconID INT);
CREATE TABLE races(raceID INT PRIMARY KEY, name TEXT, description TEXT,
  shipTypeID INT, skills TEXT, iconID INT);
"""

INDEXES = """
CREATE INDEX i_types_name    ON types(name);
CREATE INDEX i_types_group   ON types(groupID);
CREATE INDEX i_types_cat     ON types(categoryID);
CREATE INDEX i_grp_cat       ON groups_(categoryID);
CREATE INDEX i_td_type       ON type_dogma(typeID);
CREATE INDEX i_td_attr       ON type_dogma(attributeID);
CREATE INDEX i_te_type       ON type_effects(typeID);
CREATE INDEX i_bpm           ON bp_materials(blueprintTypeID);
CREATE INDEX i_bpp_type      ON bp_products(typeID);
CREATE INDEX i_bps           ON bp_skills(blueprintTypeID);
CREATE INDEX i_tm            ON type_materials(typeID);
CREATE INDEX i_sys_name      ON systems(name);
CREATE INDEX i_sys_region    ON systems(regionID);
CREATE INDEX i_sys_space     ON systems(space);
CREATE INDEX i_const_region  ON constellations(regionID);
CREATE INDEX i_planet_sys    ON planets(solarSystemID);
CREATE INDEX i_moon_sys      ON moons(solarSystemID);
CREATE INDEX i_moon_planet   ON moons(planetID);
CREATE INDEX i_belt_sys      ON asteroid_belts(solarSystemID);
CREATE INDEX i_gate_src      ON stargates(solarSystemID);
CREATE INDEX i_gate_dst      ON stargates(destSystemID);
CREATE INDEX i_sta_sys       ON npc_stations(solarSystemID);
"""


def build(raw, dbpath, build_no, released):
    if os.path.exists(dbpath):
        os.remove(dbpath)
    db = sqlite3.connect(dbpath)
    db.executescript(SCHEMA)
    ins = lambda sql, data: db.executemany(sql, data)

    db.executemany("INSERT INTO meta VALUES (?,?)", [
        ("sdeBuildNumber", str(build_no)), ("sdeReleaseDate", released),
        ("builtAt", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        ("source", BASE)])

    log("Loading static data ...")
    ins("INSERT INTO categories VALUES (?,?,?,?)",
        ((r["_key"], en(r.get("name")), r.get("published", 0), r.get("iconID"))
         for r in rows(raw, "categories")))

    def xyz(r, key="position"):
        """3D coordinates, only when asked for.

        482,768 celestial positions are high-entropy floats that compress
        badly: they add ~9.4 MB to the archive, which is 31% of the 30 MB
        upload budget, to answer distance questions specifically. Off by
        default; --positions turns them on.
        """
        if not WANT_POSITIONS:
            return (None, None, None)
        p = r.get(key) or {}
        return (num(p.get("x")), num(p.get("y")), num(p.get("z")))

    def js(v):
        return None if v is None else json.dumps(v, separators=(",", ":"), ensure_ascii=False)

    gcat = {}
    grows = []
    for r in rows(raw, "groups"):
        gcat[r["_key"]] = r.get("categoryID")
        grows.append((r["_key"], en(r.get("name")), r.get("categoryID"), r.get("published", 0),
                      r.get("anchorable", 0), r.get("anchored", 0),
                      r.get("fittableNonSingleton", 0), r.get("useBasePrice", 0), r.get("iconID")))
    ins("INSERT INTO groups_ VALUES (?,?,?,?,?,?,?,?,?)", grows)
    del grows

    ins("INSERT INTO types VALUES (%s)" % ",".join("?" * 25),
        ((r["_key"], en(r.get("name")), en(r.get("description")), r.get("groupID"),
          gcat.get(r.get("groupID")), num(r.get("mass")), num(r.get("volume")),
          num(r.get("capacity")), num(r.get("radius")), num(r.get("basePrice")),
          r.get("published", 0), r.get("marketGroupID"),
          r.get("portionSize"), r.get("raceID"), r.get("factionID"), r.get("metaGroupID"),
          r.get("metaLevel"), r.get("techLevel"), r.get("variationParentTypeID"),
          num(r.get("packagedVolume")), r.get("isRepackable"), r.get("shipTreeGroupID"),
          r.get("graphicID"), r.get("iconID"), r.get("soundID"))
         for r in rows(raw, "types")))

    ins("INSERT INTO dogma_attributes VALUES (%s)" % ",".join("?" * 18),
        ((r["_key"], r.get("name"), en(r.get("displayName")), en(r.get("description")),
          num(r.get("defaultValue")), r.get("highIsGood", 0), r.get("stackable", 0),
          r.get("published", 0), r.get("unitID"), r.get("attributeCategoryID"),
          r.get("dataType"), r.get("displayWhenZero"), r.get("minAttributeID"),
          r.get("maxAttributeID"), r.get("chargeRechargeTimeID"),
          en(r.get("tooltipTitle")), en(r.get("tooltipDescription")), r.get("iconID"))
         for r in rows(raw, "dogmaAttributes")))

    ins("INSERT INTO dogma_effects VALUES (%s)" % ",".join("?" * 26),
        ((r["_key"], r.get("effectName") or r.get("name"), en(r.get("displayName")),
          en(r.get("description")), r.get("effectCategoryID"), r.get("published", 0),
          r.get("isOffensive", 0), r.get("isAssistance", 0), r.get("isWarpSafe", 0),
          r.get("disallowAutoRepeat", 0), r.get("electronicChance"), r.get("propulsionChance"),
          r.get("rangeChance"), r.get("distribution"), r.get("guid"),
          r.get("durationAttributeID"), r.get("dischargeAttributeID"), r.get("rangeAttributeID"),
          r.get("falloffAttributeID"), r.get("trackingSpeedAttributeID"),
          r.get("resistanceAttributeID"), r.get("fittingUsageChanceAttributeID"),
          r.get("npcUsageChanceAttributeID"), r.get("npcActivationChanceAttributeID"),
          js(r.get("modifierInfo")), r.get("iconID"))
         for r in rows(raw, "dogmaEffects")))

    attrs, effs = [], []
    for r in rows(raw, "typeDogma"):
        k = r["_key"]
        for a in r.get("dogmaAttributes", []):
            attrs.append((k, a.get("attributeID"), a.get("value")))
        for e in r.get("dogmaEffects", []):
            effs.append((k, e.get("effectID"), e.get("isDefault", 0)))
    ins("INSERT INTO type_dogma VALUES (?,?,?)", attrs)
    ins("INSERT INTO type_effects VALUES (?,?,?)", effs)
    del attrs, effs

    bp, act, mats, prods, skills = [], [], [], [], []
    for r in rows(raw, "blueprints"):
        k = r.get("blueprintTypeID", r["_key"])
        bp.append((k, r.get("maxProductionLimit")))
        for aname, a in (r.get("activities") or {}).items():
            act.append((k, aname, a.get("time")))
            for m in a.get("materials", []):
                mats.append((k, aname, m.get("typeID"), m.get("quantity")))
            for p in a.get("products", []):
                prods.append((k, aname, p.get("typeID"), p.get("quantity"), p.get("probability")))
            for s in a.get("skills", []):
                skills.append((k, aname, s.get("typeID"), s.get("level")))
    ins("INSERT OR REPLACE INTO blueprints VALUES (?,?)", bp)
    ins("INSERT INTO bp_activity VALUES (?,?,?)", act)
    ins("INSERT INTO bp_materials VALUES (?,?,?,?)", mats)
    ins("INSERT INTO bp_products VALUES (?,?,?,?,?)", prods)
    ins("INSERT INTO bp_skills VALUES (?,?,?,?)", skills)
    del bp, act, mats, prods, skills

    ins("INSERT INTO type_materials VALUES (?,?,?)",
        ((r["_key"], m.get("materialTypeID"), m.get("quantity"))
         for r in rows(raw, "typeMaterials") for m in r.get("materials", [])))

    ins("INSERT INTO market_groups VALUES (?,?,?,?,?,?)",
        ((r["_key"], r.get("parentGroupID"), en(r.get("name")), en(r.get("description")),
          r.get("hasTypes", 0), r.get("iconID")) for r in rows(raw, "marketGroups")))
    ins("INSERT INTO meta_groups VALUES (?,?,?,?,?,?)",
        ((r["_key"], en(r.get("name")), en(r.get("description")), js(r.get("color")),
          r.get("iconID"), r.get("iconSuffix")) for r in rows(raw, "metaGroups")))
    ins("INSERT INTO factions VALUES (%s)" % ",".join("?" * 11),
        ((r["_key"], en(r.get("name")), en(r.get("description")), en(r.get("shortDescription")),
          r.get("corporationID"), r.get("militiaCorporationID"), r.get("solarSystemID"),
          js(r.get("memberRaces")), num(r.get("sizeFactor")), r.get("uniqueName"), r.get("iconID"))
         for r in rows(raw, "factions")))
    ins("INSERT INTO races VALUES (?,?,?,?,?,?)",
        ((r["_key"], en(r.get("name")), en(r.get("description")), r.get("shipTypeID"),
          js(r.get("skills")), r.get("iconID")) for r in rows(raw, "races")))

    log("Loading universe ...")
    ins("INSERT INTO regions VALUES (?,?,?,?,?,?,?,?,?)",
        ((r["_key"], en(r.get("name")), en(r.get("description")), r.get("factionID"),
          r.get("wormholeClassID"), r.get("nebulaID")) + xyz(r)
         for r in rows(raw, "mapRegions")))
    ins("INSERT INTO constellations VALUES (?,?,?,?,?,?,?,?)",
        ((r["_key"], en(r.get("name")), r.get("regionID"), r.get("factionID"),
          r.get("wormholeClassID")) + xyz(r)
         for r in rows(raw, "mapConstellations")))
    # Every system outside known space carries securityStatus -0.99, so security
    # alone cannot separate nullsec from wormhole/abyssal/void. The regionID
    # band is what actually distinguishes them.
    SPACE = {10: "kspace", 11: "wormhole", 12: "abyssal", 14: "void"}
    ins("INSERT INTO systems VALUES (%s)" % ",".join("?" * 22),
        ((r["_key"], en(r.get("name")), r.get("constellationID"), r.get("regionID"),
          r.get("securityStatus"), r.get("securityClass"), num(r.get("luminosity")),
          num(r.get("radius")),
          int(bool(r.get("border"))), int(bool(r.get("hub"))), int(bool(r.get("regional"))),
          int(bool(r.get("fringe"))), int(bool(r.get("corridor"))),
          int(bool(r.get("international"))),
          r.get("starID"), r.get("factionID"), r.get("wormholeClassID"), r.get("visualEffect"),
          SPACE.get((r.get("regionID") or 0) // 1000000, "other")) + xyz(r)
         for r in rows(raw, "mapSolarSystems")))

    def planet_row(r):
        s = r.get("statistics") or {}
        return (r["_key"], r.get("solarSystemID"), r.get("celestialIndex"), r.get("typeID"),
                num(r.get("radius")), num(s.get("density")), num(s.get("surfaceGravity")),
                num(s.get("escapeVelocity")), num(s.get("temperature")), num(s.get("pressure")),
                num(s.get("orbitRadius")), num(s.get("orbitPeriod")),
                num(s.get("rotationRate")), num(s.get("eccentricity")),
                num(s.get("massDust")), num(s.get("massGas")),
                int(bool(s.get("locked"))), int(bool(s.get("fragmented"))),
                len(r.get("moonIDs") or []), len(r.get("asteroidBeltIDs") or []),
                r.get("orbitID")) + xyz(r)
    ins("INSERT OR REPLACE INTO planets VALUES (%s)" % ",".join("?" * 24),
        (planet_row(r) for r in rows(raw, "mapPlanets")))

    ins("INSERT OR REPLACE INTO moons VALUES (?,?,?,?,?,?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), r.get("orbitID"), r.get("celestialIndex"),
          r.get("orbitIndex"), r.get("typeID"), num(r.get("radius"))) + xyz(r)
         for r in rows(raw, "mapMoons")))
    ins("INSERT OR REPLACE INTO asteroid_belts VALUES (?,?,?,?,?,?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), r.get("orbitID"), r.get("celestialIndex"),
          r.get("orbitIndex"), r.get("typeID"), num(r.get("radius"))) + xyz(r)
         for r in rows(raw, "mapAsteroidBelts")))
    ins("INSERT OR REPLACE INTO stargates VALUES (?,?,?,?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), (r.get("destination") or {}).get("stargateID"),
          (r.get("destination") or {}).get("solarSystemID"), r.get("typeID")) + xyz(r)
         for r in rows(raw, "mapStargates")))
    ins("INSERT OR REPLACE INTO npc_stations VALUES (%s)" % ",".join("?" * 15),
        ((r["_key"], r.get("solarSystemID"), r.get("ownerID"), r.get("typeID"),
          r.get("operationID"), num(r.get("reprocessingEfficiency")),
          num(r.get("reprocessingStationsTake")), r.get("reprocessingHangarFlag"),
          int(bool(r.get("useOperationName"))), r.get("orbitID"), r.get("celestialIndex"),
          r.get("orbitIndex")) + xyz(r)
         for r in rows(raw, "npcStations")))

    log("Indexing ...")
    db.executescript(INDEXES)
    db.commit()

    log(f"\n{'table':<20}{'rows':>12}")
    log("-" * 32)
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        log(f"{t:<20}{db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>12,}")
    db.close()
    log(f"\nWrote {dbpath} ({os.path.getsize(dbpath)/1e6:.0f} MB), SDE build {build_no}")


# Trades completeness for a file small enough to upload anywhere. Drops the
# long description text, unpublished types (roughly half of all types: test
# items and unreleased content), and the 344k-row moon table.
PORTABLE = [
    "UPDATE types SET description = NULL",
    "UPDATE dogma_attributes SET description = NULL",
    "UPDATE factions SET description = NULL",
    "DELETE FROM moons",
    "DELETE FROM type_dogma   WHERE typeID NOT IN (SELECT typeID FROM types WHERE published=1)",
    "DELETE FROM type_effects WHERE typeID NOT IN (SELECT typeID FROM types WHERE published=1)",
    "DELETE FROM types WHERE published = 0",
]


def make_portable(dbpath):
    log("Slimming for portability ...")
    db = sqlite3.connect(dbpath)
    for stmt in PORTABLE:
        db.execute(stmt)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('portable','1')")
    db.commit()
    db.execute("VACUUM")
    db.close()
    log(f"  {os.path.getsize(dbpath)/1e6:.0f} MB after slimming")


def compress(path, fmt):
    """Compress the database for upload into environments that cannot download it.

    xz is the useful one. The base build (no --complete, no --positions) is
    ~92 MB and compresses to ~13 MB, comfortably under the 30 MB per-file limit
    on claude.ai. A --complete --positions build compresses to ~37 MB, which
    does *not* fit -- hence --split, which puts every part under the limit
    without dropping anything. Python decompresses all three formats from the
    standard library (gzip / lzma / bz2).
    """
    import gzip as _gzip, lzma as _lzma, bz2 as _bz2
    opener, ext = {"gz": (lambda p: _gzip.open(p, "wb", compresslevel=9), ".gz"),
                   "xz": (lambda p: _lzma.open(p, "wb", preset=9 | _lzma.PRESET_EXTREME), ".xz"),
                   "bz2": (lambda p: _bz2.open(p, "wb", compresslevel=9), ".bz2")}[fmt]
    out = path + ext
    log(f"Compressing with {fmt} (this takes a minute) ...")
    with open(path, "rb") as f, opener(out) as g:
        shutil.copyfileobj(f, g)
    log(f"Wrote {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


# Files the curated schema already covers; --complete ingests everything else.
CURATED = {
    "categories", "groups", "types", "dogmaAttributes", "dogmaEffects", "typeDogma",
    "blueprints", "typeMaterials", "marketGroups", "metaGroups", "factions", "races",
    "mapRegions", "mapConstellations", "mapSolarSystems", "mapPlanets", "mapMoons",
    "mapAsteroidBelts", "mapStargates", "npcStations",
}

MOON_STATS = ["density", "surfaceGravity", "escapeVelocity", "orbitRadius",
              "orbitPeriod", "rotationRate", "eccentricity", "massDust", "massGas",
              "temperature", "pressure", "fragmented", "locked"]


def add_moon_statistics(raw, db):
    """Promote each moon's statistics blob to real columns."""
    log("Adding moon statistics ...")
    for c in MOON_STATS:
        typ = "INT" if c in ("fragmented", "locked") else "NUMERIC"
        db.execute(f"ALTER TABLE moons ADD COLUMN {c} {typ}")
    sets = ",".join(f"{c}=?" for c in MOON_STATS)

    def vals(r):
        s = r.get("statistics") or {}
        out = []
        for c in MOON_STATS:
            v = s.get(c)
            out.append(int(bool(v)) if c in ("fragmented", "locked") and v is not None else num(v))
        return out + [r["_key"]]

    db.executemany(f"UPDATE moons SET {sets} WHERE moonID=?",
                   (vals(r) for r in rows(raw, "mapMoons")))
    db.execute("CREATE INDEX i_moon_grav ON moons(surfaceGravity)")


def ingest_remaining(raw, db):
    """Generic-ingest every SDE file the curated schema does not cover.

    Nested structures are stored as compact JSON (query with json_extract);
    localised text is reduced to English first.
    """
    log("Ingesting remaining SDE files ...")
    import re
    files = sorted(f[:-6] for f in os.listdir(raw)
                   if f.endswith(".jsonl") and f[:-6] not in CURATED and not f.startswith("_"))
    made = 0
    for name in files:
        recs, keys = [], {}
        for r in rows(raw, name):
            r = {k: strip_locales(v) for k, v in r.items()}
            recs.append(r)
            keys.update(dict.fromkeys(r))
        if not recs:
            continue
        tbl = re.sub(r"\W", "_", name)
        cols = list(keys)
        db.execute("CREATE TABLE \"%s\" (%s)" % (
            tbl, ", ".join('"%s"' % re.sub(r"\W", "_", c) for c in cols)))

        def cell(v):
            if isinstance(v, (dict, list)):
                return json.dumps(v, separators=(",", ":"), ensure_ascii=False)
            return num(v)

        db.executemany('INSERT INTO "%s" VALUES (%s)' % (tbl, ",".join("?" * len(cols))),
                       ([cell(r.get(c)) for c in cols] for r in recs))
        # Only index tables big enough for it to matter. Most of the long tail
        # is a few hundred rows, where a scan is instant and the index costs
        # more compressed size than it saves time.
        if len(recs) >= 5000:
            for c in cols:
                if c == "_key" or c.endswith("ID"):
                    try:
                        db.execute('CREATE INDEX "i_%s_%s" ON "%s"("%s")' % (tbl, c, tbl, c))
                    except sqlite3.OperationalError:
                        pass
        made += 1
    log(f"  added {made} tables")


# Domain groups for --split. Each file stands alone, and SQLite can ATTACH
# several and join across them, so splitting costs nothing at query time.
# Tables not listed here land in "misc".
GROUPS = {
    "items": ["types", "groups_", "categories", "market_groups", "meta_groups",
              "dogma_attributes", "dogma_effects", "type_dogma", "type_effects",
              "type_materials", "typeBonus", "typeLists", "typeElements",
              "dynamicItemAttributes", "compressibleTypes",
              "contrabandTypes", "dogmaUnits", "dogmaAttributeCategories"],
    # moons are 344k rows -- over half the universe data -- and are asked about
    # far less often than systems and planets, so they get their own part.
    "moons": ["moons"],
    "universe": ["regions", "constellations", "systems", "planets",
                 "asteroid_belts", "stargates", "npc_stations", "mapStars",
                 "mapSecondarySuns", "landmarks", "planetResources",
                 "sovereigntyUpgrades", "systemWideEffects", "systemDbuffEmitters"],
    "industry": ["blueprints", "bp_activity", "bp_materials", "bp_products",
                 "bp_skills", "planetSchematics", "industryActivities",
                 "industryAssemblyLines", "industryModifierSources",
                 "industryInstallationTypes", "industryTargetFilters",
                 "controlTowerResources", "metenoxMoonDrill"],
    "world": ["factions", "races", "missions", "dungeons", "npcCharacters",
              "npcCorporations", "npcCorporationDivisions", "agentTypes",
              "agentsInSpace", "certificates", "masteries", "epicArcs",
              "bloodlines", "ancestries", "schools", "schoolMap", "archetypes",
              "characterAttributes", "characterTitles", "cloneGrades",
              "corporationActivities", "corporationRoles", "corporationRoleGroups",
              "stationOperations", "stationServices", "stationStandingsRestrictions",
              "militaryCampaigns", "militaryCampaignObjectives",
              "mercenaryTacticalOperations", "freelanceJobSchemas",
              "expertSystems", "skillPlans", "shipTreeElements", "shipTreeGroups",
              "shipTreeFactions", "accountingEntryTypes", "notificationTypes",
              "translationLanguages"],
    "cosmetic": ["graphics", "icons", "graphicMaterialSets", "skins", "skinLicenses",
                 "skinMaterials", "skinrComponents", "skinrSlots",
                 "skinrSlotConfigurations", "skinrSlotNames", "skinrSlotCategories",
                 "skinrComponentPointValues", "skinrComponentRarities",
                 "skinrComponentCategories", "skinrTierThresholds",
                 "skinrSlotsToMaterials", "linkWithShip"],
}


def split_db(dbpath, fmt=None):
    """Emit one database per domain group, each independently usable.

    The 30 MB upload cap is per file, so several small files beat one large
    one -- and a consumer that only cares about the universe never has to
    fetch missions or skins. `meta` is copied into every part.
    """
    src = sqlite3.connect(dbpath)
    all_tables = {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assigned = {t for ts in GROUPS.values() for t in ts}
    groups = dict(GROUPS)
    misc = sorted(all_tables - assigned - {"meta"})
    if misc:
        groups["misc"] = misc

    base = dbpath[:-7] if dbpath.endswith(".sqlite") else dbpath
    outputs = []
    for group, tables in groups.items():
        tables = [t for t in tables if t in all_tables]
        if not tables:
            continue
        out = f"{base}-{group}.sqlite"
        if os.path.exists(out):
            os.remove(out)
        dst = sqlite3.connect(out)
        dst.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
        dst.execute("ATTACH DATABASE ? AS src", (dbpath,))
        for t in ["meta"] + tables:
            ddl = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
            if not ddl or not ddl[0]:
                continue
            dst.execute(ddl[0])
            dst.execute('INSERT INTO "%s" SELECT * FROM src."%s"' % (t, t))
            for (isql,) in src.execute(
                    "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? "
                    "AND sql IS NOT NULL", (t,)).fetchall():
                try:
                    dst.execute(isql)
                except sqlite3.OperationalError:
                    pass
        dst.execute("INSERT OR REPLACE INTO meta VALUES ('splitGroup', ?)", (group,))
        dst.commit()
        dst.execute("DETACH DATABASE src")
        dst.execute("VACUUM")
        dst.close()
        size = os.path.getsize(out)
        line = f"  {group:<10} {len(tables):>3} tables  {size/1e6:>6.1f} MB"
        if fmt:
            c = compress(out, fmt)
            line += f"  ->  {os.path.getsize(c)/1e6:.1f} MB {fmt}"
        log(line)
        outputs.append(out)
    src.close()
    return outputs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="sde.sqlite", help="output database path")
    ap.add_argument("--workdir", default=".sde-cache", help="download/extract cache")
    ap.add_argument("--keep-raw", action="store_true", help="keep extracted JSONL")
    ap.add_argument("--positions", action="store_true",
                    help="include 3D coordinates (+10 MB compressed; needed for distances)")
    ap.add_argument("--split", action="store_true",
                    help="also emit one database per domain group (items, universe, ...)")
    ap.add_argument("--parts-only", action="store_true",
                    help="with --split, do not compress the whole database (parts carry everything)")
    ap.add_argument("--complete", action="store_true",
                    help="also ingest every remaining SDE file and moon statistics")
    ap.add_argument("--portable", action="store_true",
                    help="drop descriptions, unpublished types and moons (~31 MB)")
    ap.add_argument("--compress", choices=["gz", "xz", "bz2"],
                    help="also write a compressed copy; xz takes the base DB to ~13 MB")
    ap.add_argument("--gzip", action="store_true", help=argparse.SUPPRESS)  # back-compat
    a = ap.parse_args()

    global WANT_POSITIONS
    WANT_POSITIONS = a.positions

    os.makedirs(a.workdir, exist_ok=True)
    t0 = time.time()
    raw, build_no, released = download_sde(a.workdir)
    build(raw, a.db, build_no, released)
    if a.complete:
        db = sqlite3.connect(a.db)
        db.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
        add_moon_statistics(raw, db)
        ingest_remaining(raw, db)
        db.execute("INSERT OR REPLACE INTO meta VALUES ('complete','1')")
        db.execute("INSERT OR REPLACE INTO meta VALUES ('positions', ?)",
                   ("1" if WANT_POSITIONS else "0",))
        db.commit()
        db.execute("VACUUM")
        n = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        db.close()
        log(f"Complete build: {n} tables, {os.path.getsize(a.db)/1e6:.0f} MB")
    if a.portable:
        make_portable(a.db)
    fmt = a.compress or ("gz" if a.gzip else None)
    if a.split:
        log("Splitting by domain group ...")
        split_db(a.db, fmt)
    if fmt and not (a.split and a.parts_only):
        compress(a.db, fmt)
    if not a.keep_raw:
        shutil.rmtree(raw, ignore_errors=True)
        log("Removed extracted JSONL (use --keep-raw to keep it)")
    log(f"Done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
