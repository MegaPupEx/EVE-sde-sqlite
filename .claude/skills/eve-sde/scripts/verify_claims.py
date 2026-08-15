#!/usr/bin/env python3
"""Re-verify the documented claims in this skill against a live database.

Every hard number the reference files assert is encoded here as a query with
its expected value. When `meta.sdeBuildNumber` differs from the build the docs
were verified against, run this to see WHICH documented figures moved, instead
of re-deriving all of them by hand:

    python3 verify_claims.py --parts DIR    # directory of eve-sde-*.sqlite parts
    python3 verify_claims.py --db FILE      # a complete single-file build

Checks whose parts are not present are skipped and counted. Exit code is 0
when nothing drifted, 1 otherwise. Standard library only.

This is also the regression suite for editing the docs: a claim changed in a
reference file should have its entry updated here in the same commit.
"""

import argparse
import collections
import glob
import json
import math
import os
import sqlite3
import sys

DOC_BUILD = "3466501"

LN4 = math.log(4)

TITANS = ["Avatar", "Azariel", "Erebus", "Komodo", "Leviathan", "Molok",
          "Ragnarok", "Vanquisher"]

SHIP = "t.published = 1 AND t.categoryID = 6"


# ---------------------------------------------------------------- helpers

def one(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def col(conn, sql, *args):
    return [r[0] for r in conn.execute(sql, args)]


def rows(conn, sql, *args):
    return conn.execute(sql, args).fetchall()


def table_columns(conn, table):
    for part in [r[1] for r in conn.execute("PRAGMA database_list")]:
        cols = [r[1] for r in conn.execute(f'PRAGMA {part}.table_info("{table}")')]
        if cols:
            return cols
    return []


def align(conn, name, ndigits):
    mass, inertia = conn.execute(
        "SELECT t.mass, d.value FROM types t JOIN type_dogma d "
        "ON d.typeID = t.typeID AND d.attributeID = 70 WHERE t.name = ?",
        (name,)).fetchone()
    return round(LN4 * inertia * mass / 1e6, ndigits)


def bfs_jumps(conn, src_name, dst_name, threshold):
    sec = dict(rows(conn, "SELECT solarSystemID, security FROM systems"))
    ids = dict(rows(conn, "SELECT name, solarSystemID FROM systems WHERE name IN (?, ?)",
                    src_name, dst_name))
    src, dst = ids[src_name], ids[dst_name]
    adj = collections.defaultdict(list)
    for a, b in rows(conn, "SELECT solarSystemID, destSystemID FROM stargates"):
        if sec.get(a, -1) >= threshold and sec.get(b, -1) >= threshold:
            adj[a].append(b)
    seen, frontier, dist = {src}, [src], 0
    while frontier:
        dist += 1
        nxt = []
        for n in frontier:
            for m in adj[n]:
                if m == dst:
                    return dist
                if m not in seen:
                    seen.add(m)
                    nxt.append(m)
        frontier = nxt
    return None


# ---------------------------------------------------------------- fn checks

def fn_dogma_units_key(conn):
    cols = table_columns(conn, "dogmaUnits")
    return ("_key" in cols, "unitID" in cols)


def fn_align_base(conn):
    return (align(conn, "Rifter", 2), align(conn, "Onyx", 2))


def fn_align_log10(conn):
    mass, inertia = conn.execute(
        "SELECT t.mass, d.value FROM types t JOIN type_dogma d "
        "ON d.typeID = t.typeID AND d.attributeID = 70 WHERE t.name = 'Rifter'"
    ).fetchone()
    return round(math.log10(4) * inertia * mass / 1e6, 2)


def fn_align_t2(conn):
    return (align(conn, "Nergal", 3), align(conn, "Hydra", 3), align(conn, "Ares", 3))


def fn_routes(conn):
    return (bfs_jumps(conn, "Jita", "Amarr", 0.45),
            bfs_jumps(conn, "Jita", "Amarr", 0.5))


def fn_odd_moon(conn):
    return conn.execute(
        "SELECT s.name, p.celestialIndex, m.orbitIndex FROM moons m "
        "JOIN systems s ON s.solarSystemID = m.solarSystemID "
        "JOIN planets p ON p.planetID = m.planetID "
        "WHERE m.typeID != 14").fetchall()


def fn_moon_counts_exact(conn):
    actual = dict(rows(conn, "SELECT planetID, COUNT(*) FROM moons GROUP BY planetID"))
    mism = 0
    for pid, n in rows(conn, "SELECT planetID, moons FROM planets"):
        if actual.get(pid, 0) != n:
            mism += 1
    return mism


def fn_titan_metagroups(conn):
    d = dict(rows(conn, """
        SELECT t.metaGroupID, COUNT(*) FROM types t
        JOIN groups_ g ON g.groupID = t.groupID
        WHERE g.name = 'Titan' AND t.published = 1 GROUP BY t.metaGroupID"""))
    tech1 = one(conn, """
        SELECT COUNT(*) FROM types t JOIN groups_ g ON g.groupID = t.groupID
        WHERE g.name = 'Titan' AND t.published = 1 AND t.techLevel = 1""")
    return (d.get(1, 0), d.get(4, 0), d.get(None, 0), tech1)


def fn_special_edition(conn):
    cte = """
        WITH RECURSIVE up(typeID, mg) AS (
          SELECT typeID, marketGroupID FROM types
          WHERE categoryID = 6 AND published = 1 {meta}
          UNION ALL
          SELECT u.typeID, g.parentGroupID FROM up u
          JOIN market_groups g ON g.marketGroupID = u.mg
        )
        SELECT DISTINCT up.typeID FROM up
        JOIN market_groups g ON g.marketGroupID = up.mg
        WHERE g.name = 'Special Edition Ships'"""
    t2 = col(conn, cte.format(meta="AND metaGroupID = 2"))
    everyone = col(conn, cte.format(meta=""))
    names = sorted(col(conn, "SELECT name FROM types WHERE typeID IN (%s)"
                   % ",".join(map(str, t2))))
    return (names, len(everyone))


def fn_ship_tree_groups(conn):
    cols = table_columns(conn, "shipTreeGroups")
    namecol = "name" if "name" in cols else None
    keys = rows(conn, "SELECT _key, %s FROM shipTreeGroups" %
                (namecol or "NULL"))
    gnames = dict(rows(conn, "SELECT groupID, name FROM groups_"))
    collide = [k for k, _ in keys if k in gnames]
    agree = [k for k, n in keys if k in gnames and n == gnames[k]]
    return (len(keys), len(collide), len(agree))


def fn_clone_grades(conn):
    payloads = col(conn, "SELECT skills FROM cloneGrades")
    distinct = len(set(payloads))
    skills = json.loads(payloads[0])
    if isinstance(skills, dict):
        skills = list(skills.items())
    n = len(skills)
    at5 = sum(1 for s in skills
              if (s.get("level") if isinstance(s, dict) else s[1]) == 5)
    return (len(payloads), distinct, n, at5)


def fn_masteries_identical(conn):
    total = ident = 0
    for (v,) in rows(conn, "SELECT _value FROM masteries"):
        tiers = [json.dumps(t.get("_value"), sort_keys=True) for t in json.loads(v)]
        total += 1
        if len(set(tiers)) == 1:
            ident += 1
    return (total, ident)


def fn_wh_beacons(conn):
    beacons = col(conn, "SELECT DISTINCT effectBeaconTypeID FROM mapSecondarySuns")
    ph = ",".join(map(str, beacons))
    shield = sorted(col(conn, f"""
        SELECT d.value FROM type_dogma d
        JOIN dogma_attributes a ON a.attributeID = d.attributeID
        WHERE a.name = 'shieldEmDamageResistanceBonus' AND d.typeID IN ({ph})"""))
    armor = sorted(col(conn, f"""
        SELECT d.value FROM type_dogma d
        JOIN dogma_attributes a ON a.attributeID = d.attributeID
        WHERE a.name = 'armorEmDamageResistanceBonus' AND d.typeID IN ({ph})"""))
    with_resist = col(conn, f"""
        SELECT DISTINCT d.typeID FROM type_dogma d
        JOIN dogma_attributes a ON a.attributeID = d.attributeID
        WHERE a.name IN ('shieldEmDamageResistanceBonus',
                         'armorEmDamageResistanceBonus') AND d.typeID IN ({ph})""")
    return (len(beacons), shield, armor, len(beacons) - len(with_resist))


def fn_wh_signature(conn):
    beacons = col(conn, "SELECT DISTINCT effectBeaconTypeID FROM mapSecondarySuns")
    ph = ",".join(map(str, beacons))
    wr = sorted(col(conn, f"""
        SELECT d.value FROM type_dogma d
        JOIN dogma_attributes a ON a.attributeID = d.attributeID
        JOIN types t ON t.typeID = d.typeID
        WHERE a.name = 'signatureRadiusMultiplier' AND d.typeID IN ({ph})
          AND t.name LIKE '%Wolf Rayet%'"""))
    pulsar = sorted(col(conn, f"""
        SELECT d.value FROM type_dogma d
        JOIN dogma_attributes a ON a.attributeID = d.attributeID
        JOIN types t ON t.typeID = d.typeID
        WHERE a.name = 'signatureRadiusMultiplier' AND d.typeID IN ({ph})
          AND t.name LIKE '%Pulsar%'"""))
    return (wr, pulsar)


def fn_weather_pairs(conn):
    # Per present weather row: (penalty displayName, n resonance attrs, bonus displayName)
    out = set()
    for pat, in rows(conn, "SELECT DISTINCT t.name FROM appliedProximityEffects e "
                           "JOIN types t ON t.typeID = e._key "
                           "JOIN groups_ g ON g.groupID = t.groupID "
                           "WHERE g.name = 'Cloud' AND t.name LIKE 'CD %'"):
        db = one(conn, "SELECT dbuffs FROM appliedProximityEffects WHERE _key = "
                       "(SELECT typeID FROM types WHERE name = ?)", pat)
        effs = []
        for e in json.loads(db):
            d = conn.execute("SELECT displayName, itemModifiers FROM dbuffCollections "
                             "WHERE _key = ?", (e["_key"],)).fetchone()
            n_res = sum(1 for m in json.loads(d[1] or "[]")
                        if "Resonance" in (one(conn, "SELECT name FROM dogma_attributes "
                                                     "WHERE attributeID = ?",
                                               m["dogmaAttributeID"]) or ""))
            effs.append((d[0], n_res, e["_value"]))
        pen = [x for x in effs if "penalty" in (x[0] or "")]
        bon = [x for x in effs if x not in pen]
        out.add((pen[0][0], pen[0][1], bon[0][0], bon[0][2]))
    return sorted(out)


def fn_weather(conn):
    out = []
    for pat in ("%Electric%", "%Exotic%", "%Firestorm%", "%Gamma%", "%Dark%"):
        out.append(one(conn, """
            SELECT COUNT(*) FROM appliedProximityEffects e
            JOIN types t ON t.typeID = e._key
            JOIN groups_ g ON g.groupID = t.groupID
            WHERE g.name = 'Cloud' AND t.name LIKE ?
              AND t.name NOT LIKE '[HF]%'""", pat))
    hf = one(conn, "SELECT COUNT(*) FROM appliedProximityEffects e "
                   "JOIN types t ON t.typeID = e._key "
                   "WHERE t.name LIKE '[HF] Weather Effect%'")
    return (tuple(out), hf)


def fn_planet_resources(conn):
    planet = one(conn, "SELECT COUNT(*) FROM planetResources r "
                       "WHERE EXISTS (SELECT 1 FROM planets p WHERE p.planetID = r._key)")
    star = one(conn, "SELECT COUNT(*) FROM planetResources r "
                     "WHERE EXISTS (SELECT 1 FROM mapStars s WHERE s._key = r._key)")
    return (planet, star)


def fn_contraband(conn):
    entries = rows(conn, """
        SELECT json_extract(j.value, '$.attackMinSec'),
               json_extract(j.value, '$.confiscateMinSec')
        FROM contrabandTypes c JOIN json_each(c.factions) j""")
    attack_11 = sum(1 for a, _ in entries if a == 1.1)
    conf_neg1 = sum(1 for _, c in entries if c == -1.0)
    elite = rows(conn, """
        SELECT json_extract(j.value, '$.confiscateMinSec'),
               json_extract(j.value, '$.fineByValue'),
               json_extract(j.value, '$.standingLoss')
        FROM contrabandTypes c JOIN types t ON t.typeID = c._key
        JOIN json_each(c.factions) j WHERE t.name = 'Elite Slaves'""")
    slaves = one(conn, """
        SELECT t.basePrice * json_extract(j.value, '$.fineByValue')
        FROM contrabandTypes c JOIN types t ON t.typeID = c._key
        JOIN json_each(c.factions) j
        WHERE t.name = 'Slaves' AND json_extract(j.value, '$._key') = 500002""")
    return (len(entries), attack_11, conf_neg1,
            len(elite), len(set(elite)), list(set(elite)), slaves)


def fn_control_towers(conn):
    purpose = collections.Counter()
    charters = 0
    charter_sec = set()
    stront = set()
    for (res,) in rows(conn, "SELECT resources FROM controlTowerResources"):
        for e in json.loads(res):
            purpose[e["purpose"]] += 1
            if e["purpose"] == 4:
                stront.add(e["quantity"])
            if e["purpose"] == 1 and "factionID" in e:
                charters += 1
                charter_sec.add(e.get("minSecurityLevel"))
    amarr = rows(conn, """
        SELECT rt.name, json_extract(j.value, '$.quantity')
        FROM controlTowerResources ct
        JOIN types t ON t.typeID = ct._key
        JOIN json_each(ct.resources) j
        JOIN types rt ON rt.typeID = json_extract(j.value, '$.resourceTypeID')
        WHERE t.name = 'Amarr Control Tower'
          AND json_extract(j.value, '$.purpose') = 1
          AND json_extract(j.value, '$.factionID') IS NULL""")
    return (dict(purpose), charters, sorted(charter_sec),
            sorted(stront), amarr)


def fn_target_filters(conn):
    cols = table_columns(conn, "industryTargetFilters")
    gcol = next((c for c in cols if "roup" in c), None)
    namecol = "name" if "name" in cols else "_key"
    for name, groups in rows(conn, f"SELECT {namecol}, {gcol} FROM industryTargetFilters"):
        if "Capital" in str(name):
            g = json.loads(groups) if isinstance(groups, str) else groups
            return (len(g), 30 in g, 659 in g)
    return None


def fn_modifier_sources(conn):
    # Count dogmaAttributeID references in the manufacturing column that
    # resolve against the source type's own type_dogma rows.
    total = resolved = 0
    for key, v in rows(conn, "SELECT _key, manufacturing FROM industryModifierSources "
                             "WHERE manufacturing IS NOT NULL"):
        def walk(node):
            found = []
            if isinstance(node, dict):
                if "dogmaAttributeID" in node:
                    found.append(node["dogmaAttributeID"])
                for x in node.values():
                    found += walk(x)
            elif isinstance(node, list):
                for x in node:
                    found += walk(x)
            return found
        for attr in walk(json.loads(v)):
            total += 1
            if one(conn, "SELECT COUNT(*) FROM type_dogma WHERE typeID = ? "
                         "AND attributeID = ?", key, attr):
                resolved += 1
    return (total, resolved)


def fn_batch_arkonor(conn):
    batch, ark = (one(conn, "SELECT typeID FROM types WHERE name = ?", n)
                  for n in ("Batch Compressed Arkonor", "Arkonor"))
    diff = one(conn, """
        SELECT COUNT(*) FROM (
          SELECT materialTypeID, quantity FROM type_materials WHERE typeID = ?
          UNION
          SELECT materialTypeID, quantity FROM type_materials WHERE typeID = ?
        )""", batch, ark) - one(conn,
        "SELECT COUNT(*) FROM type_materials WHERE typeID = ?", batch)
    return diff


def fn_reprocessing_service(conn):
    ops = {}
    for k, services in rows(conn, "SELECT _key, services FROM stationOperations"):
        ops[k] = json.loads(services) if services else []
    target = set(col(conn, "SELECT _key FROM stationServices "
                           "WHERE serviceName LIKE '%Reprocess%'"))
    n = 0
    for (op,) in rows(conn, "SELECT operationID FROM npc_stations"):
        if target & set(ops.get(op, [])):
            n += 1
    return n


def fn_typelists_shape(conn):
    total = one(conn, "SELECT COUNT(*) FROM typeLists")
    nn = tuple(one(conn, f"SELECT COUNT(*) FROM typeLists WHERE {c} IS NOT NULL")
               for c in ("includedTypeIDs", "includedGroupIDs", "includedCategoryIDs",
                         "excludedTypeIDs", "excludedGroupIDs", "excludedCategoryIDs"))
    disp_null = one(conn, "SELECT COUNT(*) FROM typeLists WHERE displayName IS NULL")
    overlap = one(conn, "SELECT COUNT(*) FROM typeLists tl WHERE EXISTS "
                        "(SELECT 1 FROM types t WHERE t.typeID = tl._key)")
    return (total, nn, disp_null, overlap)


def fn_linkwithship(conn):
    total = one(conn, "SELECT COUNT(*) FROM linkWithShip")
    out = {}
    for key, tl in rows(conn, "SELECT _key, linkableShipTypeListID FROM linkWithShip"):
        r = conn.execute("SELECT includedTypeIDs, includedGroupIDs FROM typeLists "
                         "WHERE _key = ?", (tl,)).fetchone()
        tids = json.loads(r[0]) if r[0] else []
        gids = json.loads(r[1]) if r[1] else []
        out[tl] = (len(tids), sorted(gids) if tl == 946 else len(gids))
    return (total, out.get(946), out.get(300), out.get(602))


def fn_token_table(conn):
    # SKILL.md's Files table lists an approximate token cost per reference
    # file (bytes/4). Those numbers rot as files grow -- this pins them to
    # within 15% / 0.3k of the real size.
    import re
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    skill = open(os.path.join(base, "SKILL.md")).read()
    bad = []
    for m in re.finditer(r"\| `references/([\w.-]+)` \| ([\d.]+)k \|", skill):
        f, listed = m.group(1), float(m.group(2))
        actual = os.path.getsize(os.path.join(base, "references", f)) / 4096
        if abs(actual - listed) > max(0.3, 0.15 * actual):
            bad.append((f, listed, round(actual, 1)))
    return bad


def fn_jita_reachability(conn):
    sec_ids = set(col(conn, "SELECT solarSystemID FROM systems"))
    adj = collections.defaultdict(list)
    for a, b in rows(conn, "SELECT solarSystemID, destSystemID FROM stargates"):
        adj[a].append(b)
    jita = one(conn, "SELECT solarSystemID FROM systems WHERE name = 'Jita'")
    seen = {jita}
    frontier = [jita]
    while frontier:
        nxt = []
        for n in frontier:
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    nxt.append(m)
        frontier = nxt
    return len(sec_ids) - len(seen)


def fn_stargate_order(conn):
    cols = table_columns(conn, "stargates")
    return cols.index("destStargateID") < cols.index("destSystemID")


def fn_stargate_symmetry(conn):
    edges = set(map(tuple, rows(conn, "SELECT solarSystemID, destSystemID FROM stargates")))
    return sum(1 for a, b in edges if (b, a) not in edges)


def fn_factions_races_keys(conn):
    f = table_columns(conn, "factions")
    r = table_columns(conn, "races")
    return ("_key" in f, "factionID" in f, "_key" in r, "raceID" in r)


def fn_lowercase_generics(conn):
    missing = []
    for t in ("missions", "dungeons", "certificates", "masteries", "skins",
              "graphics", "icons", "landmarks", "bloodlines", "ancestries",
              "schools", "archetypes"):
        cols = table_columns(conn, t)
        if cols and "_key" not in cols:
            missing.append(t)
    return missing


def fn_pochven_gates(conn):
    poch = set(col(conn, """
        SELECT s.solarSystemID FROM systems s
        JOIN regions r ON r.regionID = s.regionID WHERE r.name = 'Pochven'"""))
    internal = external = 0
    # One row per gate object (two per link) -- the doc's "60 internal gates"
    # counts gate objects.
    for a, b in rows(conn, "SELECT solarSystemID, destSystemID FROM stargates"):
        if a in poch and b in poch:
            internal += 1
        elif (a in poch) != (b in poch):
            external += 1
    return (internal, external)


def fn_sensor_multi(conn):
    return sorted(col(conn, f"""
        SELECT t.name FROM types t WHERE {SHIP} AND 2 <= (
          SELECT COUNT(*) FROM type_dogma d WHERE d.typeID = t.typeID
          AND d.attributeID IN (208, 209, 210, 211) AND d.value > 0)"""))


# ---------------------------------------------------------------- checks

def C(doc, claim, needs, expect, sql=None, fn=None):
    return dict(doc=doc, claim=claim, needs=set(needs.split()),
                expect=expect, sql=sql, fn=fn)


CHECKS = [
    # ---------------- gotchas-dogma.md
    C("gotchas-dogma.md", "unitID 108: 58 attributes, 69,032 rows", "items",
      (58, 69032), sql="""
      SELECT (SELECT COUNT(*) FROM dogma_attributes WHERE unitID = 108),
             (SELECT COUNT(*) FROM type_dogma d JOIN dogma_attributes a
              ON a.attributeID = d.attributeID WHERE a.unitID = 108)"""),
    C("gotchas-dogma.md", "unitID 108 names: 24 *DamageResonance, 39 'resonance' anywhere",
      "items", (24, 39), sql="""
      SELECT SUM(name LIKE '%DamageResonance'), SUM(name LIKE '%resonance%')
      FROM dogma_attributes WHERE unitID = 108"""),
    C("gotchas-dogma.md", "unitID 101: 92 attributes, 40,522 rows", "items",
      (92, 40522), sql="""
      SELECT (SELECT COUNT(*) FROM dogma_attributes WHERE unitID = 101),
             (SELECT COUNT(*) FROM type_dogma d JOIN dogma_attributes a
              ON a.attributeID = d.attributeID WHERE a.unitID = 101)"""),
    C("gotchas-dogma.md", "attribute names 51/70/101/479", "items",
      ["speed", "agility", "launcherSlotsLeft", "shieldRechargeRate"], sql="""
      SELECT name FROM dogma_attributes WHERE attributeID IN (51, 70, 101, 479)
      ORDER BY attributeID"""),
    C("gotchas-dogma.md", "423 published ships", "items", 423,
      sql=f"SELECT COUNT(*) FROM types t WHERE {SHIP}"),
    C("gotchas-dogma.md", "attr 2115: 3 distinct values; 409 at 1.0, 6 at 0.5, 8 at 0.2",
      "items", (3, 409, 6, 8), sql=f"""
      SELECT COUNT(DISTINCT d.value),
             SUM(d.value = 1.0), SUM(d.value = 0.5), SUM(d.value = 0.2)
      FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE d.attributeID = 2115 AND {SHIP}"""),
    C("gotchas-dogma.md", "the eight titans at 80% web resist", "items", TITANS,
      sql=f"""
      SELECT t.name FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE d.attributeID = 2115 AND d.value = 0.2 AND {SHIP} ORDER BY t.name"""),
    C("gotchas-dogma.md", "bare structure resonance 0.67 on all 423 ships", "items",
      423, sql=f"""
      SELECT COUNT(*) FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE d.attributeID = 113 AND d.value = 0.67 AND {SHIP}"""),
    C("gotchas-dogma.md", "hull* resonance on 9 published ships, Rifter among them",
      "items", (9, 1), sql=f"""
      SELECT COUNT(DISTINCT d.typeID), SUM(t.name = 'Rifter')
      FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE d.attributeID = 974 AND {SHIP}"""),
    C("gotchas-dogma.md", "attr 112 attached to zero types", "items", 0,
      sql="SELECT COUNT(*) FROM type_dogma WHERE attributeID = 112"),
    C("gotchas-dogma.md", "Rifter armor resists 60/35/25/10 in client order", "items",
      [60.0, 35.0, 25.0, 10.0], sql="""
      SELECT ROUND((1 - d.value) * 100, 1) FROM type_dogma d
      JOIN types t ON t.typeID = d.typeID
      WHERE t.name = 'Rifter' AND d.attributeID IN (267, 270, 269, 268)
      ORDER BY CASE d.attributeID WHEN 267 THEN 1 WHEN 270 THEN 2
                                  WHEN 269 THEN 3 ELSE 4 END"""),
    C("gotchas-dogma.md", "Onyx full resist panel (role bonus applied)", "items",
      [20.0, 84.0, 76.0, 60.0, 50.0, 86.25, 62.5, 10.0, 33.0, 33.0, 33.0, 33.0],
      sql="""
      WITH layer(attributeID, lyr, ord) AS (VALUES
        (271,1,1),(274,1,2),(273,1,3),(272,1,4),
        (267,2,1),(270,2,2),(269,2,3),(268,2,4),
        (113,3,1),(110,3,2),(109,3,3),(111,3,4))
      SELECT ROUND((1 - d.value * (1 + COALESCE(rb.value, 0) / 100.0)) * 100, 2)
      FROM types t CROSS JOIN layer l
      JOIN type_dogma d ON d.typeID = t.typeID AND d.attributeID = l.attributeID
      LEFT JOIN type_dogma rb ON rb.typeID = t.typeID
        AND rb.attributeID = CASE l.lyr WHEN 2 THEN 1825 WHEN 1 THEN 1829 END
      WHERE t.name = 'Onyx' ORDER BY l.lyr, l.ord"""),
    C("gotchas-dogma.md", "shield role bonus roster (1829)", "items",
      [("Broadsword", -20.0), ("Fiend", -20.0), ("Laelaps", -20.0),
       ("Onyx", -20.0), ("Taipan", -12.0), ("Ibis", -8.0)], sql=f"""
      SELECT t.name, d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE d.attributeID = 1829 AND {SHIP} ORDER BY d.value, t.name"""),
    C("gotchas-dogma.md", "armor role bonus roster (1825, published)", "items",
      [("Devoter", -20.0), ("Gold Magnate", -20.0), ("Phobos", -20.0),
       ("Silver Magnate", -20.0), ("Impairor", -8.0)], sql=f"""
      SELECT t.name, d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE d.attributeID = 1825 AND {SHIP} ORDER BY d.value, t.name"""),
    C("gotchas-dogma.md", "'resist' prose: 31 mention it, 11 carry 1825/1829, 50 NULL",
      "items", (31, 11, 50), sql=f"""
      SELECT (SELECT COUNT(*) FROM typeBonus b JOIN types t ON t.typeID = b._key
              WHERE {SHIP} AND b.roleBonuses LIKE '%resist%'),
             (SELECT COUNT(DISTINCT d.typeID) FROM type_dogma d
              JOIN types t ON t.typeID = d.typeID
              WHERE d.attributeID IN (1825, 1829) AND {SHIP}),
             (SELECT COUNT(*) FROM typeBonus b JOIN types t ON t.typeID = b._key
              WHERE {SHIP} AND b.roleBonuses IS NULL)"""),
    C("gotchas-dogma.md", "Monitor 0.1 on all four shield; Cybele ties kinetic",
      "items", (4, 0.1), sql="""
      SELECT (SELECT COUNT(*) FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              WHERE t.name = 'Monitor' AND d.attributeID IN (271,272,273,274)
                AND d.value = 0.1),
             (SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              WHERE t.name = 'Cybele' AND d.attributeID = 273)"""),
    C("gotchas-dogma.md", "two ships with more than one non-zero sensor strength",
      "items", ["Apotheosis", "Council Diplomatic Shuttle"], fn=fn_sensor_multi),
    C("gotchas-dogma.md", "Onyx gravimetric 19, Rifter ladar 8", "items",
      (19.0, 8.0), sql="""
      SELECT (SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              WHERE t.name = 'Onyx' AND d.attributeID = 211),
             (SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              WHERE t.name = 'Rifter' AND d.attributeID = 209)"""),
    C("gotchas-dogma.md", "maxActiveDrones (352): zero rows, defaultValue 0", "items",
      (0, 0.0), sql="""
      SELECT (SELECT COUNT(*) FROM type_dogma WHERE attributeID = 352),
             (SELECT defaultValue FROM dogma_attributes WHERE attributeID = 352)"""),
    C("gotchas-dogma.md", "pre-skill panels: Rifter 250/125000/22500/365, Onyx 1250/335000/80000/200",
      "items", [250.0, 125000.0, 22500.0, 365.0, 1250.0, 335000.0, 80000.0, 200.0],
      sql="""
      SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
      WHERE t.name IN ('Rifter', 'Onyx') AND d.attributeID IN (482, 55, 76, 37)
      ORDER BY t.name DESC, CASE d.attributeID WHEN 482 THEN 1 WHEN 55 THEN 2
                                               WHEN 76 THEN 3 ELSE 4 END"""),
    C("gotchas-dogma.md", "align: Rifter 4.73 s, Onyx 11.74 s", "items",
      (4.73, 11.74), fn=fn_align_base),
    C("gotchas-dogma.md", "base-10 LOG trap: Rifter reads 2.06 s", "items",
      2.06, fn=fn_align_log10),
    C("gotchas-dogma.md", "structure EM displayName: three-way collision 113/974/1426",
      "items", 1, sql="""
      SELECT COUNT(DISTINCT displayName) FROM dogma_attributes
      WHERE attributeID IN (113, 974, 1426)"""),
    C("gotchas-dogma.md", "passiveHull 1426-1429 are unitID 127", "items", 4, sql="""
      SELECT COUNT(*) FROM dogma_attributes
      WHERE attributeID BETWEEN 1426 AND 1429 AND unitID = 127"""),
    C("gotchas-dogma.md", "94 fighters in fighterAbilitiesByType", "misc", 94,
      sql="SELECT COUNT(*) FROM fighterAbilitiesByType"),
    C("gotchas-dogma.md", "one restricted ability: 7, banned in high AND low sec",
      "misc", (7, 1, 1), sql="""
      SELECT _key, disallowInHighSec, disallowInLowSec FROM fighterAbilities
      WHERE disallowInHighSec = 1"""),
    C("gotchas-dogma.md", "16 of 94 fighters carry ability 7", "misc", 16, sql="""
      SELECT COUNT(*) FROM fighterAbilitiesByType
      WHERE json_extract(abilitySlot0, '$.abilityID') = 7
         OR json_extract(abilitySlot1, '$.abilityID') = 7
         OR json_extract(abilitySlot2, '$.abilityID') = 7"""),
    C("gotchas-dogma.md", "dogmaUnits is keyed on _key, no unitID column", "items",
      (True, False), fn=fn_dogma_units_key),
    C("gotchas-dogma.md", "Miner I: 10 m3 per 15000 ms cycle", "items",
      (10.0, 15000.0), sql="""
      SELECT (SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              WHERE t.name = 'Miner I' AND d.attributeID = 77),
             (SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              WHERE t.name = 'Miner I' AND d.attributeID = 73)"""),

    # ---------------- gotchas-types.md
    C("gotchas-types.md", "26,992 of 52,863 types published", "items",
      (26992, 52863), sql="SELECT SUM(published), COUNT(*) FROM types"),
    C("gotchas-types.md", "Rifter 27,289 m3 assembled, 2,500 packaged", "items",
      (27289.0, 2500.0),
      sql="SELECT volume, packagedVolume FROM types WHERE name = 'Rifter'"),
    C("gotchas-types.md", "volume != packagedVolume: 685 published, 242 modules",
      "items", (685, 242), sql="""
      SELECT COUNT(*), SUM(categoryID = 7) FROM types
      WHERE published = 1 AND volume != packagedVolume"""),
    C("gotchas-types.md", "capacity NULL for 25,265 published types", "items",
      25265, sql="SELECT COUNT(*) FROM types WHERE published = 1 AND capacity IS NULL"),
    C("gotchas-types.md", "8 contraband cargoes", "items", 8,
      sql="SELECT COUNT(*) FROM contrabandTypes"),
    C("gotchas-types.md",
      "contraband: 50 entries; attackMinSec 1.1 on all; -1.0 on 21; "
      "Elite Slaves 8x(1.0, 0.0, 0.0); Slaves x Minmatar = 7500 ISK/unit",
      "items", (50, 50, 21, 8, 1, [(1.0, 0.0, 0.0)], 7500.0), fn=fn_contraband),
    C("gotchas-types.md", "basePrice dead for 17,652 of 26,992 published", "items",
      17652, sql="""
      SELECT COUNT(*) FROM types WHERE published = 1
      AND (basePrice IS NULL OR basePrice = 0)"""),
    C("gotchas-types.md", "map furniture types: 10+1+29+44+38, all unpublished",
      "universe items", (10, 1, 29, 44, 38, 0), sql="""
      SELECT (SELECT COUNT(DISTINCT typeID) FROM planets),
             (SELECT COUNT(DISTINCT typeID) FROM asteroid_belts),
             (SELECT COUNT(DISTINCT typeID) FROM stargates),
             (SELECT COUNT(DISTINCT typeID) FROM npc_stations),
             (SELECT COUNT(DISTINCT typeID) FROM mapStars),
             (SELECT COUNT(*) FROM types WHERE published = 1 AND typeID IN (
                SELECT typeID FROM planets UNION SELECT typeID FROM asteroid_belts
                UNION SELECT typeID FROM stargates UNION SELECT typeID FROM npc_stations
                UNION SELECT typeID FROM mapStars))"""),
    C("gotchas-types.md", "10 planet type names span 17 rows in types",
      "universe items", 17, sql="""
      SELECT COUNT(*) FROM types WHERE name IN
      (SELECT DISTINCT t2.name FROM planets p JOIN types t2 ON t2.typeID = p.typeID)"""),
    C("gotchas-types.md", "shipTreeGroups: 52 keys, 30 collide, 0 names agree",
      "world items", (52, 30, 0), fn=fn_ship_tree_groups),
    C("gotchas-types.md", "tech level disagrees: 2,537 / 2,434 / 1,892", "items",
      (2537, 2434, 1892), sql="""
      SELECT (SELECT COUNT(*) FROM types WHERE published = 1 AND techLevel = 2),
             (SELECT COUNT(*) FROM types t JOIN type_dogma d ON d.typeID = t.typeID
              WHERE t.published = 1 AND d.attributeID = 422 AND d.value = 2),
             (SELECT COUNT(*) FROM types WHERE published = 1 AND metaGroupID = 2)"""),
    C("gotchas-types.md", "43 types contradict their dogma; 19 hulls T2-by-column, Faction-by-meta",
      "items", (43, 19), sql="""
      SELECT (SELECT COUNT(*) FROM types t JOIN type_dogma d ON d.typeID = t.typeID
              WHERE d.attributeID = 422 AND t.techLevel IS NOT NULL
                AND t.techLevel != d.value),
             (SELECT COUNT(*) FROM types t
              WHERE t.published = 1 AND t.categoryID = 6
                AND t.techLevel = 2 AND t.metaGroupID = 4)"""),
    C("gotchas-types.md",
      "titan metaGroupID: 3x1, 4x4, Ragnarok NULL; techLevel 1 on all eight",
      "items", (3, 4, 1, 8), fn=fn_titan_metagroups),
    C("gotchas-types.md", "121 published T2 hulls", "items", 121, sql=f"""
      SELECT COUNT(*) FROM types t WHERE {SHIP} AND t.metaGroupID = 2"""),
    C("gotchas-types.md", "Special Edition walk: the 7 T2, 68 without the meta filter",
      "items", (sorted(["Chameleon", "Enforcer", "Hydra", "Marshal",
                        "Pacifier", "Tiamat", "Whiptail"]), 68),
      fn=fn_special_edition),
    C("gotchas-types.md", "T2 frigate aligns: Nergal 4.193, Hydra 4.148, Ares 4.544",
      "items", (4.193, 4.148, 4.544), fn=fn_align_t2),
    C("gotchas-types.md", "the Pacifier aligns at 6.99 s (purchasable special)",
      "items", 6.99, fn=lambda conn: align(conn, "Pacifier", 2)),
    C("gotchas-types.md",
      "prize signal: 15 published ships mention the Alliance Tournament; "
      "Chameleon/Whiptail/Freki/Mimir do not",
      "items", (15, 0), sql="""
      SELECT (SELECT COUNT(*) FROM types WHERE published = 1 AND categoryID = 6
              AND description LIKE '%lliance Tournament%'),
             (SELECT COUNT(*) FROM types WHERE published = 1 AND categoryID = 6
              AND name IN ('Chameleon', 'Whiptail', 'Freki', 'Mimir')
              AND description LIKE '%lliance Tournament%')"""),
    C("gotchas-types.md",
      "the Monitor is metaGroupID 2 in the normal tree (market group CONCORD)",
      "items", (2, "CONCORD"), sql="""
      SELECT t.metaGroupID, m.name FROM types t
      JOIN market_groups m ON m.marketGroupID = t.marketGroupID
      WHERE t.name = 'Monitor' AND t.published = 1"""),
    C("gotchas-types.md", "duplicate names: 12 types, 6 groups, 2 attributes",
      "items", (12, 6, 2), sql="""
      SELECT (SELECT COUNT(*) FROM (SELECT name FROM types WHERE published = 1
              GROUP BY name HAVING COUNT(*) > 1)),
             (SELECT COUNT(*) FROM (SELECT name FROM groups_
              GROUP BY name HAVING COUNT(*) > 1)),
             (SELECT COUNT(*) FROM (SELECT name FROM dogma_attributes
              GROUP BY name HAVING COUNT(*) > 1))"""),
    C("gotchas-types.md", "cyno pair: 2794 is seconds, 2795 milliseconds", "items",
      [("cynoJammerActivationDelay", 3), ("cynoJammerActivationDelay", 101)], sql="""
      SELECT name, unitID FROM dogma_attributes WHERE attributeID IN (2794, 2795)
      ORDER BY attributeID"""),
    C("gotchas-types.md", "960 published types have NULL volume", "items", 960,
      sql="SELECT COUNT(*) FROM types WHERE published = 1 AND volume IS NULL"),
    C("gotchas-types.md", "category 25 has 49 groups", "items", 49,
      sql="SELECT COUNT(*) FROM groups_ WHERE categoryID = 25"),

    # ---------------- gotchas-universe.md
    C("gotchas-universe.md", "k-space bands: 5,485 = 1,246 + 687 + 3,552",
      "universe", (5485, 1246, 687, 3552), sql="""
      SELECT COUNT(*), SUM(security >= 0.45),
             SUM(security < 0.45 AND security > 0.0), SUM(security <= 0.0)
      FROM systems WHERE space = 'kspace'"""),
    C("gotchas-universe.md", "Jita security 0.9459 unrounded", "universe", 0.9459,
      sql="SELECT ROUND(security, 4) FROM systems WHERE name = 'Jita'"),
    C("gotchas-universe.md", "Jita-Amarr: 34 jumps at 0.45, 39 at 0.5",
      "universe", (34, 39), fn=fn_routes),
    C("gotchas-universe.md", "344,457 moons, one not typeID 14", "moons",
      (344457, 1), sql="SELECT COUNT(*), SUM(typeID != 14) FROM moons"),
    C("gotchas-universe.md", "the odd moon out is Jita IV - Moon 4",
      "moons universe", [("Jita", 4, 4)],
      fn=lambda conn: [tuple(r) for r in fn_odd_moon(conn)]),
    C("gotchas-universe.md", "1,364 moons NULL surfaceGravity, all typeID 14",
      "moons", (1364, 1364), sql="""
      SELECT COUNT(*), SUM(typeID = 14) FROM moons WHERE surfaceGravity IS NULL"""),
    C("gotchas-universe.md", "planets: 68,407 = 46,618 k-space + 21,789 wormhole",
      "universe", (68407, 46618, 21789), sql="""
      SELECT COUNT(*), SUM(s.space = 'kspace'), SUM(s.space = 'wormhole')
      FROM planets p JOIN systems s ON s.solarSystemID = p.solarSystemID"""),
    C("gotchas-universe.md", "planets.moons denormalised count is exact (0 mismatches)",
      "universe moons", 0, fn=fn_moon_counts_exact),
    C("gotchas-universe.md", "40,928 belts, all typeID 15", "universe",
      (40928, 40928), sql="SELECT COUNT(*), SUM(typeID = 15) FROM asteroid_belts"),
    C("gotchas-universe.md", "1,179 of 1,246 high-sec systems have belts",
      "universe", 1179, sql="""
      SELECT COUNT(DISTINCT s.solarSystemID) FROM systems s
      JOIN asteroid_belts b ON b.solarSystemID = s.solarSystemID
      WHERE s.space = 'kspace' AND s.security >= 0.45"""),
    C("gotchas-universe.md", "Exordium: 53 systems, all at 1.0, zero belts",
      "universe", (53, 53, 0), sql="""
      SELECT COUNT(*), SUM(s.security = 1.0),
             (SELECT COUNT(*) FROM asteroid_belts b
              JOIN systems s2 ON s2.solarSystemID = b.solarSystemID
              JOIN regions r2 ON r2.regionID = s2.regionID
              WHERE r2.name = 'Exordium')
      FROM systems s JOIN regions r ON r.regionID = s.regionID
      WHERE r.name = 'Exordium'"""),
    C("gotchas-universe.md", "Zarzakh: the only k-space system with no planets",
      "universe", "Zarzakh", sql="""
      SELECT name FROM systems s WHERE space = 'kspace' AND NOT EXISTS
      (SELECT 1 FROM planets p WHERE p.solarSystemID = s.solarSystemID)"""),
    C("gotchas-universe.md",
      "3,222 gateless: 2,604 wh + 200 abyssal + 200 void + 217 k + 1 other",
      "universe", [("abyssal", 200), ("kspace", 217), ("other", 1),
                   ("void", 200), ("wormhole", 2604)], sql="""
      SELECT space, COUNT(*) FROM systems s WHERE NOT EXISTS
      (SELECT 1 FROM stargates g WHERE g.solarSystemID = s.solarSystemID)
      GROUP BY space ORDER BY space"""),
    C("gotchas-universe.md", "Tew 0.949794, Eystur 0.949232; 53 systems at 0.949 in 13 regions",
      "universe", (0.949794, 0.949232, 53, 13), sql="""
      SELECT (SELECT ROUND(security, 6) FROM systems WHERE name = 'Tew'),
             (SELECT ROUND(security, 6) FROM systems WHERE name = 'Eystur'),
             (SELECT COUNT(*) FROM systems WHERE security = 0.949),
             (SELECT COUNT(DISTINCT regionID) FROM systems WHERE security = 0.949)"""),
    C("gotchas-universe.md", "unused regions: UUA-F4 107, J7HZ-F 77, A821-A 46",
      "universe", [("A821-A", 46), ("J7HZ-F", 77), ("UUA-F4", 107)], sql="""
      SELECT r.name, COUNT(*) FROM systems s JOIN regions r ON r.regionID = s.regionID
      WHERE r.name IN ('UUA-F4', 'J7HZ-F', 'A821-A') GROUP BY r.name ORDER BY r.name"""),
    C("gotchas-universe.md", "Pochven: 27 systems at -1.0, 60 internal gates, 0 external",
      "universe", (27, (60, 0)), fn=lambda conn: (
          one(conn, """SELECT COUNT(*) FROM systems s
                       JOIN regions r ON r.regionID = s.regionID
                       WHERE r.name = 'Pochven' AND s.security = -1.0"""),
          fn_pochven_gates(conn))),
    C("gotchas-universe.md", "space has five values; 'other' is GPMS-01 at (1,1,1), sec 1.0",
      "universe", (5, [("GPMS-01", 1.0, 1.0, 1.0, 1.0)]), fn=lambda conn: (
          one(conn, "SELECT COUNT(DISTINCT space) FROM systems"),
          rows(conn, "SELECT name, security, x, y, z FROM systems WHERE space = 'other'"))),
    C("gotchas-universe.md", "wormholeClassID: 5 wh systems system-level; 687 k-space class 8",
      "universe", (5, 687), sql="""
      SELECT (SELECT COUNT(*) FROM systems WHERE space = 'wormhole'
              AND wormholeClassID IS NOT NULL),
             (SELECT COUNT(*) FROM systems WHERE space = 'kspace'
              AND wormholeClassID = 8)"""),
    C("gotchas-universe.md", "k-space constellation classes: 7:1880 9:3188 10:6 11:7 25:27",
      "universe", [(7, 1880), (9, 3188), (10, 6), (11, 7), (25, 27)], sql="""
      SELECT c.wormholeClassID, COUNT(*) FROM systems s
      JOIN constellations c ON c.constellationID = s.constellationID
      WHERE s.space = 'kspace' AND c.wormholeClassID IS NOT NULL
      GROUP BY 1 ORDER BY 1"""),
    C("gotchas-universe.md", "J124611 resolves to class 2 via the upward join",
      "universe", 2, sql="""
      SELECT COALESCE(s.wormholeClassID, c.wormholeClassID, r.wormholeClassID)
      FROM systems s
      JOIN constellations c ON c.constellationID = s.constellationID
      JOIN regions r ON r.regionID = s.regionID
      WHERE s.space = 'wormhole' AND s.name = 'J124611'"""),
    C("gotchas-universe.md", "security storage: 121 INTEGER, 8,369 REAL",
      "universe", [("integer", 121), ("real", 8369)], sql="""
      SELECT typeof(security), COUNT(*) FROM systems GROUP BY 1 ORDER BY 1"""),
    C("gotchas-universe.md", "1,038 of 2,604 J-space systems have a secondary sun",
      "universe", (1038, 2604), sql="""
      SELECT (SELECT COUNT(*) FROM mapSecondarySuns),
             (SELECT COUNT(*) FROM systems WHERE space = 'wormhole')"""),
    C("gotchas-universe.md",
      "36 beacons; WR shield & Pulsar armor scale 15..50; 24 carry no resist bonus",
      "universe items",
      (36, [15.0, 22.0, 29.0, 36.0, 43.0, 50.0],
           [15.0, 22.0, 29.0, 36.0, 43.0, 50.0], 24), fn=fn_wh_beacons),
    C("gotchas-universe.md", "signature multipliers scale WR 0.85..0.50, Pulsar 1.30..2.00",
      "universe items",
      ([0.5, 0.57, 0.64, 0.71, 0.78, 0.85],
       [1.3, 1.44, 1.58, 1.72, 1.86, 2.0]), fn=fn_wh_signature),
    C("gotchas-universe.md",
      "beacon recharge effect targets capacitor (55), never shield (479)",
      "universe items", (1, 0), sql="""
      SELECT (SELECT COUNT(DISTINCT e.effectID) FROM type_effects te
              JOIN dogma_effects e ON e.effectID = te.effectID
              WHERE te.typeID IN (SELECT effectBeaconTypeID FROM mapSecondarySuns)
                AND e.modifierInfo LIKE '%"modifiedAttributeID":55,%'),
             (SELECT COUNT(DISTINCT e.effectID) FROM type_effects te
              JOIN dogma_effects e ON e.effectID = te.effectID
              WHERE te.typeID IN (SELECT effectBeaconTypeID FROM mapSecondarySuns)
                AND e.modifierInfo LIKE '%"modifiedAttributeID":479,%')"""),
    C("gotchas-universe.md", "the beacon name is unhyphenated 'Wolf Rayet'",
      "universe items", (1, 0), sql="""
      SELECT (SELECT COUNT(*) FROM types WHERE name = 'Class 6 Wolf Rayet Effects'),
             (SELECT COUNT(*) FROM types t
              WHERE t.typeID IN (SELECT effectBeaconTypeID FROM mapSecondarySuns)
                AND t.name LIKE '%Wolf-Rayet%')"""),
    C("gotchas-universe.md",
      "dbuff IDs collide with attributeIDs: 229 of 276; 55 of 55 referenced",
      "misc items universe", (276, 229, 55, 55), fn=lambda conn: (
          one(conn, "SELECT COUNT(*) FROM dbuffCollections"),
          one(conn, """SELECT COUNT(*) FROM dbuffCollections c WHERE EXISTS
                       (SELECT 1 FROM dogma_attributes a WHERE a.attributeID = c._key)"""),
          len(set(k for (v,) in rows(conn, "SELECT dbuffs FROM systemWideEffects "
                                           "WHERE dbuffs IS NOT NULL")
                  for k in [e["_key"] for e in json.loads(v)])),
          len(set(k for (v,) in rows(conn, "SELECT dbuffs FROM systemWideEffects "
                                           "WHERE dbuffs IS NOT NULL")
                  for k in [e["_key"] for e in json.loads(v)]
                  if one(conn, "SELECT COUNT(*) FROM dogma_attributes "
                               "WHERE attributeID = ?", k))))),
    C("gotchas-universe.md", "planetResources: 23,086 planet rows + 2,712 star rows",
      "universe", (23086, 2712), fn=fn_planet_resources),
    C("gotchas-universe.md",
      "abyssal weather rows: Electric 3, Exotic 1, Firestorm 1, Gamma 1, Dark 0; 15 [HF]",
      "misc items", ((3, 1, 1, 1, 0), 15), fn=fn_weather),
    C("gotchas-universe.md",
      "weather pairs: each penalty hits 3 resonance layers; bonuses fixed "
      "(Electric's stored as rechargeRate -50)",
      "misc items",
      [("EM Resistance penalty", 3, "Capacitor Recharge bonus", -50.0),
       ("Explosive Resistance penalty", 3, "Shield HP bonus", 50.0),
       ("Kinetic Resistance penalty", 3, "Scan Resolution bonus", 50.0),
       ("Thermal Resistance penalty", 3, "Armor HP bonus", 50.0)],
      fn=fn_weather_pairs),
    C("gotchas-universe.md", "sovereigntyUpgrades: 49 rows; 44/4/1 split; 14 fuel; 5 unpublished",
      "universe items", (49, 44, 4, 1, 14, 5), sql="""
      SELECT COUNT(*),
             SUM(power_allocation IS NOT NULL),
             SUM(power_production IS NOT NULL),
             SUM(power_allocation IS NULL AND power_production IS NULL),
             SUM(fuel IS NOT NULL),
             (SELECT COUNT(*) FROM sovereigntyUpgrades u
              JOIN types t ON t.typeID = u._key WHERE t.published = 0)
      FROM sovereigntyUpgrades"""),
    C("gotchas-universe.md",
      "Deprecated Cynosural types are published but have no upgrades row",
      "universe items", (2, 0), sql="""
      SELECT (SELECT COUNT(*) FROM types WHERE name LIKE 'Deprecated Cynosural%'
              AND published = 1),
             (SELECT COUNT(*) FROM sovereigntyUpgrades u
              JOIN types t ON t.typeID = u._key
              WHERE t.name LIKE 'Deprecated%')"""),
    C("gotchas-universe.md", "the QA producer: 9,000 power, 90,000 workforce",
      "universe items", (9000, 90000), sql="""
      SELECT u.power_production, u.workforce_production FROM sovereigntyUpgrades u
      JOIN types t ON t.typeID = u._key
      WHERE t.name = 'QA Colony Resources Management Enhancer'"""),
    C("gotchas-universe.md", "mapStars: one row per real system (8,089)",
      "universe", 8089, sql="SELECT COUNT(*) FROM mapStars"),
    C("gotchas-universe.md", "faction inheritance: systems 70, constellations 386, regions 33",
      "universe", (70, 386, 33), sql="""
      SELECT (SELECT COUNT(*) FROM systems WHERE factionID IS NOT NULL),
             (SELECT COUNT(*) FROM constellations WHERE factionID IS NOT NULL),
             (SELECT COUNT(*) FROM regions WHERE factionID IS NOT NULL)"""),
    C("gotchas-universe.md", "system-column-only faction count: CONCORD Assembly 26; real: Amarr 706",
      "universe world", (("CONCORD Assembly", 26), ("Amarr Empire", 706)),
      fn=lambda conn: (
          conn.execute("""SELECT f.name, COUNT(*) FROM systems s
                          JOIN factions f ON f.factionID = s.factionID
                          WHERE s.space = 'kspace'
                          GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").fetchone(),
          conn.execute("""SELECT f.name, COUNT(*) FROM systems s
                          JOIN constellations c ON c.constellationID = s.constellationID
                          JOIN regions r ON r.regionID = s.regionID
                          JOIN factions f ON f.factionID =
                            COALESCE(s.factionID, c.factionID, r.factionID)
                          WHERE s.space = 'kspace'
                          GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").fetchone())),

    # ---------------- gotchas-industry.md
    C("gotchas-industry.md", "Antimatter Charge S: 204 Tritanium per run of 100",
      "industry items", (204, 100), sql="""
      SELECT m.quantity, p.quantity FROM bp_products p
      JOIN types t ON t.typeID = p.typeID
      JOIN bp_materials m ON m.blueprintTypeID = p.blueprintTypeID
        AND m.activity = p.activity
      JOIN types mt ON mt.typeID = m.typeID
      WHERE t.name = 'Antimatter Charge S' AND p.activity = 'manufacturing'
        AND mt.name = 'Tritanium'"""),
    C("gotchas-industry.md", "368 multi-output manufacturing blueprints; reactions reach 10,000",
      "industry", (368, 10000), sql="""
      SELECT (SELECT COUNT(*) FROM bp_products
              WHERE activity = 'manufacturing' AND quantity > 1),
             (SELECT MAX(quantity) FROM bp_products WHERE activity = 'reaction')"""),
    C("gotchas-industry.md", "planetSchematics: 68 rows, 60 produce more than one",
      "industry items", (68, 60), fn=lambda conn: (
          one(conn, "SELECT COUNT(*) FROM planetSchematics"),
          sum(1 for (v,) in rows(conn, "SELECT types FROM planetSchematics")
              if any(not t["isInput"] and t["quantity"] > 1
                     for t in json.loads(v)))),
    ),
    C("gotchas-industry.md", "portionSize vs batch: 30 published disagree, 24 are 100->5,000",
      "industry items", (30, 24), sql="""
      SELECT COUNT(*), SUM(t.portionSize = 100 AND p.quantity = 5000)
      FROM bp_products p JOIN types t ON t.typeID = p.typeID
      WHERE p.activity = 'manufacturing' AND t.published = 1
        AND t.portionSize != p.quantity"""),
    C("gotchas-industry.md", "Mjolnir Javelin XL Torpedo: portion 100, run 5,000; plain runs 100",
      "industry items", [(100, 5000), (100, 100)], sql="""
      SELECT t.portionSize, p.quantity FROM bp_products p
      JOIN types t ON t.typeID = p.typeID
      WHERE p.activity = 'manufacturing'
        AND t.name IN ('Mjolnir Javelin XL Torpedo', 'Mjolnir XL Torpedo')
      ORDER BY t.name"""),
    C("gotchas-industry.md", "Dominix blueprint: 1 manufacturing skill, 3 invention",
      "industry items", (1, 3), sql="""
      SELECT SUM(s.activity = 'manufacturing'), SUM(s.activity = 'invention')
      FROM bp_skills s JOIN bp_products p ON p.blueprintTypeID = s.blueprintTypeID
        AND p.activity = 'manufacturing'
      JOIN types t ON t.typeID = p.typeID WHERE t.name = 'Dominix'"""),
    C("gotchas-industry.md", "probability NULL: 4,848 mfg / 120 reaction / 8 invention",
      "industry", (4848, 120, 8), sql="""
      SELECT SUM(activity = 'manufacturing'), SUM(activity = 'reaction'),
             SUM(activity = 'invention')
      FROM bp_products WHERE probability IS NULL"""),
    C("gotchas-industry.md",
      "invention: 1,361 products; 978 T2; 216 T3 rows from 72 blueprints",
      "industry items", (1361, 978, 216, 72), sql="""
      SELECT COUNT(*),
             SUM(t.metaGroupID = 2),
             SUM(t.metaGroupID = 14),
             COUNT(DISTINCT CASE WHEN t.metaGroupID = 14 THEN p.typeID END)
      FROM bp_products p JOIN types t ON t.typeID = p.typeID
      WHERE p.activity = 'invention'"""),
    C("gotchas-industry.md",
      "relic base chances: published .26/.21/.14; the 48 legacy OLD rows .34/.30/.22",
      "industry items", ([0.14, 0.21, 0.26], [0.22, 0.3, 0.34], 48),
      fn=lambda conn: (
          col(conn, """SELECT DISTINCT p.probability FROM bp_products p
              JOIN types rel ON rel.typeID = p.blueprintTypeID
              JOIN types prod ON prod.typeID = p.typeID
              WHERE p.activity = 'invention' AND rel.categoryID = 34
                AND prod.published = 1 ORDER BY 1"""),
          col(conn, """SELECT DISTINCT p.probability FROM bp_products p
              JOIN types rel ON rel.typeID = p.blueprintTypeID
              JOIN types prod ON prod.typeID = p.typeID
              WHERE p.activity = 'invention' AND rel.categoryID = 34
                AND prod.published = 0 ORDER BY 1"""),
          one(conn, """SELECT COUNT(*) FROM bp_products p
              JOIN types rel ON rel.typeID = p.blueprintTypeID
              JOIN types prod ON prod.typeID = p.typeID
              WHERE p.activity = 'invention' AND rel.categoryID = 34
                AND prod.published = 0"""))),
    C("gotchas-industry.md", "84 multi-blueprint products: 4 mfg, 79 invention, 1 reaction; Firewall 5",
      "industry items", (84, 4, 79, 1, 5), sql="""
      WITH multi AS (
        SELECT typeID, activity, COUNT(DISTINCT blueprintTypeID) AS n
        FROM bp_products GROUP BY typeID, activity HAVING n > 1)
      SELECT (SELECT COUNT(*) FROM multi),
             (SELECT COUNT(*) FROM multi WHERE activity = 'manufacturing'),
             (SELECT COUNT(*) FROM multi WHERE activity = 'invention'),
             (SELECT COUNT(*) FROM multi WHERE activity = 'reaction'),
             (SELECT n FROM multi JOIN types t ON t.typeID = multi.typeID
              WHERE t.name = '''Firewall'' Signal Amplifier')"""),
    C("gotchas-industry.md", "18,915 published types have no type_materials row",
      "items", 18915, sql="""
      SELECT COUNT(*) FROM types t WHERE t.published = 1 AND NOT EXISTS
      (SELECT 1 FROM type_materials m WHERE m.typeID = t.typeID)"""),
    C("gotchas-industry.md", "Batch Compressed Arkonor: 1,000 in, 1 out, reprocesses as 100 Arkonor",
      "industry items", ((1000, 1), 0), fn=lambda conn: (
          conn.execute("""
            SELECT m.quantity, p.quantity FROM bp_products p
            JOIN types t ON t.typeID = p.typeID
            JOIN bp_materials m ON m.blueprintTypeID = p.blueprintTypeID
              AND m.activity = p.activity
            WHERE t.name = 'Batch Compressed Arkonor'
              AND p.activity = 'manufacturing'""").fetchone(),
          fn_batch_arkonor(conn))),
    C("gotchas-industry.md", "21 dangling blueprint refs: 20 products, 1 material",
      "industry items", (20, 1), sql="""
      SELECT (SELECT COUNT(*) FROM bp_products p WHERE NOT EXISTS
              (SELECT 1 FROM types t WHERE t.typeID = p.typeID)),
             (SELECT COUNT(*) FROM bp_materials m WHERE NOT EXISTS
              (SELECT 1 FROM types t WHERE t.typeID = m.typeID))"""),
    C("gotchas-industry.md",
      "control towers: 44 rows; purpose 1:295 / 4:44; 252 charters at 0.45; "
      "Amarr burns 40 Helium; reinforced stront burn 100/200/400 per hour",
      "industry items",
      ({1: 295, 4: 44}, 252, [0.45], [100, 200, 400],
       [("Helium Fuel Block", 40)]), fn=fn_control_towers),
    C("gotchas-industry.md",
      "stront bay is capacitySecondary: 12,500 x14 / 25,000 x14 / 50,000 x16 m3",
      "industry items", [(12500.0, 14), (25000.0, 14), (50000.0, 16)], sql="""
      SELECT d.value, COUNT(*) FROM type_dogma d
      JOIN dogma_attributes a ON a.attributeID = d.attributeID
      WHERE a.name = 'capacitySecondary'
        AND d.typeID IN (SELECT _key FROM controlTowerResources)
      GROUP BY 1 ORDER BY 1"""),
    C("gotchas-industry.md", "industryModifierSources: 13 of 371 mfg references resolve",
      "industry items", (371, 13), fn=fn_modifier_sources),
    C("gotchas-industry.md", "'Capital Ships' filter: 6 groups, neither 30 nor 659",
      "industry", (6, False, False), fn=fn_target_filters),
    C("gotchas-industry.md", "engineering complexes: mat 0.99, time .85/.80/.70; Tatara .75",
      "items", [("Azbel", 0.99, 0.8), ("Raitaru", 0.99, 0.85), ("Sotiyo", 0.99, 0.7)],
      sql="""
      SELECT t.name,
             MAX(CASE WHEN a.name = 'strEngMatBonus' THEN d.value END),
             MAX(CASE WHEN a.name = 'strEngTimeBonus' THEN d.value END)
      FROM types t JOIN type_dogma d ON d.typeID = t.typeID
      JOIN dogma_attributes a ON a.attributeID = d.attributeID
      WHERE t.name IN ('Raitaru', 'Azbel', 'Sotiyo')
        AND a.name IN ('strEngMatBonus', 'strEngTimeBonus')
      GROUP BY t.name ORDER BY t.name"""),
    C("gotchas-industry.md", "Tatara reaction time multiplier 0.75", "items",
      0.75, sql="""
      SELECT d.value FROM types t JOIN type_dogma d ON d.typeID = t.typeID
      JOIN dogma_attributes a ON a.attributeID = d.attributeID
      WHERE t.name = 'Tatara' AND a.name = 'strReactionTimeMultiplier'"""),
    C("examples.md", "Rifter build: 32,000 / 6,000 / 2,500 / 500", "industry items",
      [("Tritanium", 32000), ("Pyerite", 6000), ("Mexallon", 2500), ("Isogen", 500)],
      sql="""
      SELECT mt.name, m.quantity FROM bp_materials m
      JOIN types mt ON mt.typeID = m.typeID
      JOIN bp_products p ON p.blueprintTypeID = m.blueprintTypeID
        AND p.activity = m.activity
      JOIN types t ON t.typeID = p.typeID
      WHERE t.name = 'Rifter' AND m.activity = 'manufacturing'
      ORDER BY m.quantity DESC"""),
    C("gotchas-industry.md", "Veldspar: 400 Tritanium per portion of 100", "items",
      (100, "Tritanium", 400), sql="""
      SELECT t.portionSize, mt.name, m.quantity FROM type_materials m
      JOIN types t ON t.typeID = m.typeID
      JOIN types mt ON mt.typeID = m.materialTypeID
      WHERE t.name = 'Veldspar'"""),
    C("gotchas-industry.md",
      "station refining: 5,210 stations, 4,649 at 0.50, range .25-.50; "
      "Jita 18 all at 0.50; 283 of 1,143 multi-station systems have a spread",
      "universe", (5210, 4649, 0.25, 0.5, 18, 18, 1143, 283), sql="""
      SELECT COUNT(*), SUM(reprocessingEfficiency = 0.5),
             MIN(reprocessingEfficiency), MAX(reprocessingEfficiency),
             (SELECT COUNT(*) FROM npc_stations n JOIN systems s
              ON s.solarSystemID = n.solarSystemID WHERE s.name = 'Jita'),
             (SELECT COUNT(*) FROM npc_stations n JOIN systems s
              ON s.solarSystemID = n.solarSystemID
              WHERE s.name = 'Jita' AND n.reprocessingEfficiency = 0.5),
             (SELECT COUNT(*) FROM (SELECT solarSystemID FROM npc_stations
              GROUP BY solarSystemID HAVING COUNT(*) > 1)),
             (SELECT COUNT(*) FROM (SELECT solarSystemID FROM npc_stations
              GROUP BY solarSystemID HAVING COUNT(*) > 1
              AND MIN(reprocessingEfficiency) != MAX(reprocessingEfficiency)))
      FROM npc_stations"""),
    C("gotchas-industry.md", "Oursulaert refining runs 0.25 to 0.50", "universe",
      (0.25, 0.5), sql="""
      SELECT MIN(n.reprocessingEfficiency), MAX(n.reprocessingEfficiency)
      FROM npc_stations n JOIN systems s ON s.solarSystemID = n.solarSystemID
      WHERE s.name = 'Oursulaert'"""),
    C("gotchas-industry.md", "5,197 of 5,210 stations offer a Reprocessing Plant",
      "universe world", 5197, fn=fn_reprocessing_service),

    # ---------------- schema.md (world and generic tables)
    C("gotchas-world.md", "10,966 agents; 180 level-5, of which 37 real and 143 event",
      "world", (10966, 180, 37, 143), sql="""
      SELECT COUNT(*),
             SUM(json_extract(agent, '$.level') = 5),
             SUM(json_extract(agent, '$.level') = 5
                 AND json_extract(agent, '$.agentTypeID') = 2),
             SUM(json_extract(agent, '$.level') = 5
                 AND json_extract(agent, '$.agentTypeID') = 8)
      FROM npcCharacters WHERE agent IS NOT NULL"""),
    C("gotchas-world.md", "agentTypes names all 13 kinds", "world", 13,
      sql="SELECT COUNT(*) FROM agentTypes"),
    C("gotchas-world.md", "killMission: 1,662 rows, 1,661 with dungeonID, 3 resolve, odd row 16414",
      "world", (1662, 1661, 3, [16414]), fn=lambda conn: (
          one(conn, "SELECT COUNT(*) FROM missions WHERE killMission IS NOT NULL"),
          one(conn, """SELECT COUNT(*) FROM missions
                       WHERE json_extract(killMission, '$.dungeonID') IS NOT NULL"""),
          one(conn, """SELECT COUNT(*) FROM missions m JOIN dungeons d
                       ON d._key = json_extract(m.killMission, '$.dungeonID')"""),
          col(conn, """SELECT _key FROM missions WHERE killMission IS NOT NULL
                       AND json_extract(killMission, '$.dungeonID') IS NULL"""))),
    C("gotchas-world.md", "killMission and courierMission are mutually exclusive", "world",
      0, sql="""
      SELECT COUNT(*) FROM missions
      WHERE killMission IS NOT NULL AND courierMission IS NOT NULL"""),
    C("gotchas-world.md", "agentsInSpace: 360 rows, dungeonID resolves 0", "world",
      (360, 0), sql="""
      SELECT COUNT(*),
             (SELECT COUNT(*) FROM agentsInSpace a
              JOIN dungeons d ON d._key = a.dungeonID)
      FROM agentsInSpace"""),
    C("gotchas-world.md", "dungeons: 1,409 rows, 1,014 distinct names, 226 descriptions",
      "world", (1409, 1014, 226), sql="""
      SELECT COUNT(*), COUNT(DISTINCT name), SUM(description IS NOT NULL)
      FROM dungeons"""),
    C("gotchas-world.md", "DED ratings: 'Threat Assessment' 44, strict 'DED Threat Assessment:' 38",
      "world", (44, 38), sql="""
      SELECT SUM(description LIKE '%Threat Assessment%'),
             SUM(description LIKE '%DED Threat Assessment:%')
      FROM dungeons"""),
    C("gotchas-world.md", "cloneGrades: 4 rows, 1 distinct payload, 175 skills, 23 at V",
      "world", (4, 1, 175, 23), fn=fn_clone_grades),
    C("gotchas-world.md", "masteries: 476 rows, 72 identical at every level", "world",
      (476, 72), fn=fn_masteries_identical),
    C("schema.md", "typeLists: 462 rows; 218/268/45 + 26/27/2 non-NULL; 425 unnamed; 229 key-collisions",
      "items", (462, (218, 268, 45, 26, 27, 2), 425, 229), fn=fn_typelists_shape),
    C("schema.md", "linkWithShip: 3 rows; C-CRAB {547,5120}; CRAB 1+6; skyhook 5+22",
      "cosmetic items", (3, (0, [547, 5120]), (1, 6), (5, 22)), fn=fn_linkwithship),
    C("schema.md", "typeBonus: all 423 published ships have a row", "items", 423,
      sql=f"""
      SELECT COUNT(*) FROM typeBonus b JOIN types t ON t.typeID = b._key
      WHERE {SHIP}"""),
    C("schema.md", "fighterAbilities: 36 rows, name column is displayName", "misc",
      (36, True, False), fn=lambda conn: (
          one(conn, "SELECT COUNT(*) FROM fighterAbilities"),
          "displayName" in table_columns(conn, "fighterAbilities"),
          "name" in table_columns(conn, "fighterAbilities"))),
    C("schema.md", "appliedProximityEffects 118 rows; proximityTrap 24", "misc",
      (118, 24), sql="""
      SELECT (SELECT COUNT(*) FROM appliedProximityEffects),
             (SELECT COUNT(*) FROM proximityTrap)"""),
    C("schema.md", "stargates: destStargateID column comes before destSystemID",
      "universe", True, fn=fn_stargate_order),
    C("gotchas-universe.md", "every gate has its reverse edge (0 asymmetric)",
      "universe", 0, fn=fn_stargate_symmetry),
    C("schema.md", "factions/races: keyed on factionID/raceID, no _key", "world",
      (False, True, False, True), fn=fn_factions_races_keys),
    C("SKILL.md", "the twelve lowercase generic tables are all _key-keyed",
      "world cosmetic items universe", [], fn=fn_lowercase_generics),
    C("SKILL.md", "stargate rows: 13,978", "universe", 13978,
      sql="SELECT COUNT(*) FROM stargates"),
    C("SKILL.md", "volume equals packagedVolume for 25,347 published types",
      "items", 25347, sql="""
      SELECT COUNT(*) FROM types WHERE published = 1
      AND volume = packagedVolume"""),
    C("gotchas-types.md",
      "Bowhead ship bay 1,600,000 m3; Charon cargo 465,000 m3",
      "items", (1600000.0, 465000.0), sql="""
      SELECT (SELECT d.value FROM type_dogma d JOIN types t ON t.typeID = d.typeID
              JOIN dogma_attributes a ON a.attributeID = d.attributeID
              WHERE t.name = 'Bowhead' AND a.name = 'shipMaintenanceBayCapacity'),
             (SELECT capacity FROM types WHERE name = 'Charon')"""),
    C("gotchas-universe.md", "3,262 systems are gate-unreachable from Jita",
      "universe", 3262, fn=fn_jita_reachability),
    C("SKILL.md", "the Files table's token costs are within 15% of bytes/4",
      "", [], fn=fn_token_table),
]


# ---------------------------------------------------------------- runner

def normalize(rows_):
    if len(rows_) == 1 and len(rows_[0]) == 1:
        return rows_[0][0]
    if len(rows_) == 1:
        return tuple(rows_[0])
    if all(len(r) == 1 for r in rows_):
        return [r[0] for r in rows_]
    return [tuple(r) for r in rows_]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parts", help="directory containing eve-sde-*.sqlite parts")
    ap.add_argument("--db", help="a complete single-file build")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print passing checks too")
    args = ap.parse_args()

    conn = sqlite3.connect(":memory:")
    have = set()
    builds = {}
    if args.db:
        conn.execute("ATTACH DATABASE ? AS sde", (args.db,))
        have = {"items", "universe", "moons", "industry", "world",
                "cosmetic", "misc"}
        builds["complete"] = one(conn, "SELECT value FROM sde.meta WHERE key = 'sdeBuildNumber'")
    else:
        pdir = args.parts or "."
        for path in sorted(glob.glob(os.path.join(pdir, "eve-sde-*.sqlite"))):
            group = os.path.basename(path)[len("eve-sde-"):-len(".sqlite")]
            if group in ("", "full") or "-" in group:
                continue
            conn.execute(f"ATTACH DATABASE ? AS {group}", (path,))
            have.add(group)
            builds[group] = one(conn, f"SELECT value FROM {group}.meta "
                                      "WHERE key = 'sdeBuildNumber'")
        if not have:
            # Exit 2 for setup failure, so automation can tell "could not
            # run" apart from exit 1's "ran and found drift".
            print(f"no eve-sde-*.sqlite parts found in {pdir!r} "
                  "(use --parts DIR or --db FILE)", file=sys.stderr)
            sys.exit(2)

    print(f"docs pinned to build {DOC_BUILD}")
    for k, v in sorted(builds.items()):
        flag = "" if v == DOC_BUILD else "   <-- DIFFERS"
        print(f"  {k:10s} {v}{flag}")
    if len(set(builds.values())) > 1:
        print("  WARNING: parts are from different builds -- "
              "cross-part joins may be inconsistent")
    print()

    per_doc = collections.Counter()
    per_doc_total = collections.Counter()
    drift = skipped = errors = 0
    for c in CHECKS:
        per_doc_total[c["doc"]] += 1
        if not c["needs"] <= have:
            skipped += 1
            if args.verbose:
                print(f"SKIP  [{c['doc']}] {c['claim']} "
                      f"(needs {' '.join(sorted(c['needs'] - have))})")
            continue
        try:
            if c["sql"]:
                actual = normalize(conn.execute(c["sql"]).fetchall())
            else:
                actual = c["fn"](conn)
        except Exception as e:
            errors += 1
            print(f"ERROR [{c['doc']}] {c['claim']}\n      {e}")
            continue
        if actual == c["expect"]:
            per_doc[c["doc"]] += 1
            if args.verbose:
                print(f"ok    [{c['doc']}] {c['claim']}")
        else:
            drift += 1
            print(f"DRIFT [{c['doc']}] {c['claim']}\n"
                  f"      documented: {c['expect']!r}\n"
                  f"      actual:     {actual!r}")

    print()
    for doc in sorted(per_doc_total):
        print(f"  {doc:24s} {per_doc[doc]}/{per_doc_total[doc]}")
    ran = len(CHECKS) - skipped
    print(f"\n{len(CHECKS)} checks: {ran - drift - errors} ok, {drift} drifted, "
          f"{errors} errored, {skipped} skipped (parts absent)")
    if drift or errors:
        print("\nA drifted check means the documented figure no longer matches "
              "this build.\nUpdate the claim in the named doc (and its entry "
              "here), or re-pin DOC_BUILD\nafter a full pass.")
    sys.exit(1 if (drift or errors) else 0)


if __name__ == "__main__":
    main()
