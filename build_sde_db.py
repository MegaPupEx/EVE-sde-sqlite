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


def fetch(url, dest):
    log(f"  GET {url}")
    with urllib.request.urlopen(url, timeout=600) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest


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
        if not os.path.exists(zpath):
            fetch(f"{BASE}/eve-online-static-data-{build}-jsonl.zip", zpath)
        log(f"  extracting {os.path.getsize(zpath)/1e6:.0f} MB ...")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(raw)
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
  border INT, hub INT, regional INT, starID INT);
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
    ins("INSERT INTO systems VALUES (%s)" % ",".join("?" * 12),
        ((r["_key"], en(r.get("name")), r.get("constellationID"), r.get("regionID"),
          r.get("securityStatus"), r.get("securityClass"), r.get("luminosity"), r.get("radius"),
          int(bool(r.get("border"))), int(bool(r.get("hub"))), int(bool(r.get("regional"))),
          r.get("starID")) for r in rows(raw, "mapSolarSystems")))

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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="sde.sqlite", help="output database path")
    ap.add_argument("--workdir", default=".sde-cache", help="download/extract cache")
    ap.add_argument("--keep-raw", action="store_true", help="keep extracted JSONL")
    a = ap.parse_args()

    os.makedirs(a.workdir, exist_ok=True)
    t0 = time.time()
    raw, build_no, released = download_sde(a.workdir)
    build(raw, a.db, build_no, released)
    if not a.keep_raw:
        shutil.rmtree(raw, ignore_errors=True)
        log("Removed extracted JSONL (use --keep-raw to keep it)")
    log(f"Done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
