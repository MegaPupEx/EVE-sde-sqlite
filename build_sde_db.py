#!/usr/bin/env python3
"""
Build a queryable SQLite database from the EVE Online Static Data Export (SDE).

Downloads the current SDE from CCP's official distribution, then flattens the
JSONL files into a normalised SQLite database with indexes.

    python3 build_sde_db.py                 # download + build ./sde.sqlite
    python3 build_sde_db.py --db eve.sqlite # custom output path
    python3 build_sde_db.py --keep-raw      # don't delete the extracted JSONL

Requires only the Python standard library. Takes ~2 minutes and ~1.5 GB of
temporary disk; the resulting database is ~120 MB.

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


def en(v, default=None):
    """SDE localises many strings as {'en': ..., 'de': ...}."""
    if isinstance(v, dict):
        return v.get("en", default)
    return v if v is not None else default


SCHEMA = """
PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;

CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE categories(categoryID INT PRIMARY KEY, name TEXT, published INT);
CREATE TABLE groups_(groupID INT PRIMARY KEY, name TEXT, categoryID INT, published INT);
CREATE TABLE types(
  typeID INT PRIMARY KEY, name TEXT, description TEXT, groupID INT, categoryID INT,
  mass REAL, volume REAL, capacity REAL, radius REAL, basePrice REAL, published INT,
  marketGroupID INT, portionSize INT, raceID INT, factionID INT,
  metaGroupID INT, metaLevel INT, techLevel INT, variationParentTypeID INT);
CREATE TABLE dogma_attributes(
  attributeID INT PRIMARY KEY, name TEXT, description TEXT,
  defaultValue REAL, highIsGood INT, stackable INT, published INT);
CREATE TABLE dogma_effects(effectID INT PRIMARY KEY, name TEXT);
CREATE TABLE type_dogma(typeID INT, attributeID INT, value REAL);
CREATE TABLE type_effects(typeID INT, effectID INT, isDefault INT);
CREATE TABLE blueprints(blueprintTypeID INT PRIMARY KEY, maxProductionLimit INT);
CREATE TABLE bp_activity(blueprintTypeID INT, activity TEXT, time INT);
CREATE TABLE bp_materials(blueprintTypeID INT, activity TEXT, typeID INT, quantity INT);
CREATE TABLE bp_products(blueprintTypeID INT, activity TEXT, typeID INT, quantity INT, probability REAL);
CREATE TABLE bp_skills(blueprintTypeID INT, activity TEXT, typeID INT, level INT);
CREATE TABLE type_materials(typeID INT, materialTypeID INT, quantity INT);
CREATE TABLE market_groups(marketGroupID INT PRIMARY KEY, parentGroupID INT, name TEXT, hasTypes INT);
CREATE TABLE meta_groups(metaGroupID INT PRIMARY KEY, name TEXT);
CREATE TABLE regions(regionID INT PRIMARY KEY, name TEXT, factionID INT, wormholeClassID INT);
CREATE TABLE constellations(constellationID INT PRIMARY KEY, name TEXT, regionID INT, factionID INT);
CREATE TABLE systems(
  solarSystemID INT PRIMARY KEY, name TEXT, constellationID INT, regionID INT,
  security REAL, securityClass TEXT, luminosity REAL, radius REAL,
  border INT, hub INT, regional INT, starID INT, space TEXT);
CREATE TABLE planets(
  planetID INT PRIMARY KEY, solarSystemID INT, celestialIndex INT, typeID INT, radius REAL,
  density REAL, surfaceGravity REAL, escapeVelocity REAL, temperature REAL, pressure REAL,
  orbitRadius REAL, orbitPeriod REAL, rotationRate REAL, eccentricity REAL,
  massDust REAL, massGas REAL, locked INT, moons INT, belts INT);
CREATE TABLE moons(moonID INT PRIMARY KEY, solarSystemID INT, planetID INT,
  celestialIndex INT, orbitIndex INT, typeID INT, radius REAL);
CREATE TABLE asteroid_belts(beltID INT PRIMARY KEY, solarSystemID INT, planetID INT,
  celestialIndex INT, orbitIndex INT, typeID INT);
CREATE TABLE stargates(stargateID INT PRIMARY KEY, solarSystemID INT,
  destStargateID INT, destSystemID INT, typeID INT);
CREATE TABLE npc_stations(stationID INT PRIMARY KEY, solarSystemID INT, ownerID INT,
  typeID INT, operationID INT, reprocessingEfficiency REAL);
CREATE TABLE factions(factionID INT PRIMARY KEY, name TEXT, description TEXT,
  corporationID INT, militiaCorporationID INT, solarSystemID INT);
CREATE TABLE races(raceID INT PRIMARY KEY, name TEXT);
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
    ins("INSERT INTO categories VALUES (?,?,?)",
        ((r["_key"], en(r.get("name")), r.get("published", 0)) for r in rows(raw, "categories")))

    gcat = {}
    grows = []
    for r in rows(raw, "groups"):
        gcat[r["_key"]] = r.get("categoryID")
        grows.append((r["_key"], en(r.get("name")), r.get("categoryID"), r.get("published", 0)))
    ins("INSERT INTO groups_ VALUES (?,?,?,?)", grows)
    del grows

    ins("INSERT INTO types VALUES (%s)" % ",".join("?" * 19),
        ((r["_key"], en(r.get("name")), en(r.get("description")), r.get("groupID"),
          gcat.get(r.get("groupID")), r.get("mass"), r.get("volume"), r.get("capacity"),
          r.get("radius"), r.get("basePrice"), r.get("published", 0), r.get("marketGroupID"),
          r.get("portionSize"), r.get("raceID"), r.get("factionID"), r.get("metaGroupID"),
          r.get("metaLevel"), r.get("techLevel"), r.get("variationParentTypeID"))
         for r in rows(raw, "types")))

    ins("INSERT INTO dogma_attributes VALUES (?,?,?,?,?,?,?)",
        ((r["_key"], r.get("name"), en(r.get("description")), r.get("defaultValue"),
          r.get("highIsGood", 0), r.get("stackable", 0), r.get("published", 0))
         for r in rows(raw, "dogmaAttributes")))

    ins("INSERT INTO dogma_effects VALUES (?,?)",
        ((r["_key"], r.get("effectName") or en(r.get("name"))) for r in rows(raw, "dogmaEffects")))

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

    ins("INSERT INTO market_groups VALUES (?,?,?,?)",
        ((r["_key"], r.get("parentGroupID"), en(r.get("name")), r.get("hasTypes", 0))
         for r in rows(raw, "marketGroups")))
    ins("INSERT INTO meta_groups VALUES (?,?)",
        ((r["_key"], en(r.get("name"))) for r in rows(raw, "metaGroups")))
    ins("INSERT INTO factions VALUES (?,?,?,?,?,?)",
        ((r["_key"], en(r.get("name")), en(r.get("description")), r.get("corporationID"),
          r.get("militiaCorporationID"), r.get("solarSystemID")) for r in rows(raw, "factions")))
    ins("INSERT INTO races VALUES (?,?)",
        ((r["_key"], en(r.get("name"))) for r in rows(raw, "races")))

    log("Loading universe ...")
    ins("INSERT INTO regions VALUES (?,?,?,?)",
        ((r["_key"], en(r.get("name")), r.get("factionID"), r.get("wormholeClassID"))
         for r in rows(raw, "mapRegions")))
    ins("INSERT INTO constellations VALUES (?,?,?,?)",
        ((r["_key"], en(r.get("name")), r.get("regionID"), r.get("factionID"))
         for r in rows(raw, "mapConstellations")))
    # Every system outside known space carries securityStatus -0.99, so security
    # alone cannot separate nullsec from wormhole/abyssal/void. The regionID
    # band is what actually distinguishes them.
    SPACE = {10: "kspace", 11: "wormhole", 12: "abyssal", 14: "void"}
    ins("INSERT INTO systems VALUES (%s)" % ",".join("?" * 13),
        ((r["_key"], en(r.get("name")), r.get("constellationID"), r.get("regionID"),
          r.get("securityStatus"), r.get("securityClass"), r.get("luminosity"), r.get("radius"),
          int(bool(r.get("border"))), int(bool(r.get("hub"))), int(bool(r.get("regional"))),
          r.get("starID"), SPACE.get((r.get("regionID") or 0) // 1000000, "other"))
         for r in rows(raw, "mapSolarSystems")))

    def planet_row(r):
        s = r.get("statistics") or {}
        return (r["_key"], r.get("solarSystemID"), r.get("celestialIndex"), r.get("typeID"),
                r.get("radius"), s.get("density"), s.get("surfaceGravity"), s.get("escapeVelocity"),
                s.get("temperature"), s.get("pressure"), s.get("orbitRadius"), s.get("orbitPeriod"),
                s.get("rotationRate"), s.get("eccentricity"), s.get("massDust"), s.get("massGas"),
                int(bool(s.get("locked"))), len(r.get("moonIDs") or []),
                len(r.get("asteroidBeltIDs") or []))
    ins("INSERT OR REPLACE INTO planets VALUES (%s)" % ",".join("?" * 19),
        (planet_row(r) for r in rows(raw, "mapPlanets")))

    ins("INSERT OR REPLACE INTO moons VALUES (?,?,?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), r.get("orbitID"), r.get("celestialIndex"),
          r.get("orbitIndex"), r.get("typeID"), r.get("radius")) for r in rows(raw, "mapMoons")))
    ins("INSERT OR REPLACE INTO asteroid_belts VALUES (?,?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), r.get("orbitID"), r.get("celestialIndex"),
          r.get("orbitIndex"), r.get("typeID")) for r in rows(raw, "mapAsteroidBelts")))
    ins("INSERT OR REPLACE INTO stargates VALUES (?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), (r.get("destination") or {}).get("stargateID"),
          (r.get("destination") or {}).get("solarSystemID"), r.get("typeID"))
         for r in rows(raw, "mapStargates")))
    ins("INSERT OR REPLACE INTO npc_stations VALUES (?,?,?,?,?,?)",
        ((r["_key"], r.get("solarSystemID"), r.get("ownerID"), r.get("typeID"),
          r.get("operationID"), r.get("reprocessingEfficiency")) for r in rows(raw, "npcStations")))

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

    xz is the useful one: it takes the full ~92 MB database to ~13 MB, which is
    comfortably under the 30 MB per-file limit on claude.ai, so nothing has to
    be stripped out to make it fit. Python decompresses all three from the
    standard library (gzip / lzma / bz2).
    """
    import gzip as _gzip, lzma as _lzma, bz2 as _bz2
    opener, ext = {"gz": (lambda p: _gzip.open(p, "wb", compresslevel=9), ".gz"),
                   "xz": (lambda p: _lzma.open(p, "wb", preset=9), ".xz"),
                   "bz2": (lambda p: _bz2.open(p, "wb", compresslevel=9), ".bz2")}[fmt]
    out = path + ext
    log(f"Compressing with {fmt} (this takes a minute) ...")
    with open(path, "rb") as f, opener(out) as g:
        shutil.copyfileobj(f, g)
    log(f"Wrote {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="sde.sqlite", help="output database path")
    ap.add_argument("--workdir", default=".sde-cache", help="download/extract cache")
    ap.add_argument("--keep-raw", action="store_true", help="keep extracted JSONL")
    ap.add_argument("--portable", action="store_true",
                    help="drop descriptions, unpublished types and moons (~31 MB)")
    ap.add_argument("--compress", choices=["gz", "xz", "bz2"],
                    help="also write a compressed copy; xz takes the full DB to ~13 MB")
    ap.add_argument("--gzip", action="store_true", help=argparse.SUPPRESS)  # back-compat
    a = ap.parse_args()

    os.makedirs(a.workdir, exist_ok=True)
    t0 = time.time()
    raw, build_no, released = download_sde(a.workdir)
    build(raw, a.db, build_no, released)
    if a.portable:
        make_portable(a.db)
    fmt = a.compress or ("gz" if a.gzip else None)
    if fmt:
        compress(a.db, fmt)
    if not a.keep_raw:
        shutil.rmtree(raw, ignore_errors=True)
        log("Removed extracted JSONL (use --keep-raw to keep it)")
    log(f"Done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
