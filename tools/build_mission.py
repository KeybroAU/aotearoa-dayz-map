"""Build the server mission files for the Aotearoa terrain.

Reads the generated terrain (source/heightmap_4096.png, mask_4096.png, towns.csv, roads.json,
pois.json) and writes mission/dayzOffline.aotearoa/ with player spawns, vehicle and crash
events, infected zones, the Whakaari contaminated area, init.c and a cfggameplay snippet,
plus mission/serverDZ.cfg. economy.py adds loot positions and tiers, animals and weather. Copy the rest of the mission (db/, cfgeconomycore.xml and so on)
from vanilla dayzOffline.chernarusplus; see the README.

    python build_mission.py
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import economy
import generate_terrain as g

MISSION = "dayzOffline.aotearoa"
OUT = g.MAP_DIR / "mission"
SPAWN_COUNT = 40
HELI_CRASHES = 24
VEHICLE_SPACING_M = 450.0

VEHICLES = ["VehicleCivilianSedan", "VehicleSedan02", "VehicleHatchback02", "VehicleOffroadHatchback",
            "VehicleOffroad02", "VehicleTruck01"]
INFECTED_ZONES = {
    # tier: (zone name, zones per 100 m of radius, dmin, dmax)
    "capital": ("InfectedCity", 3.2, 3, 7),
    "city": ("InfectedCity", 3.0, 2, 6),
    "town": ("InfectedVillage", 2.6, 2, 5),
    "village": ("InfectedVillage", 2.4, 1, 3),
    "military": ("InfectedMilitary", 3.0, 2, 5),
}
# Monthly temperature range (deg C, January first), roughly Canterbury.
MIN_TEMPS = [12, 12, 10, 7, 4, 2, 1, 2, 4, 6, 8, 11]
MAX_TEMPS = [23, 22, 20, 17, 14, 11, 10, 12, 14, 17, 19, 21]


def load():
    meta = json.loads((g.SOURCE_DIR / "heightmap.json").read_text())
    raw = np.asarray(Image.open(g.SOURCE_DIR / "heightmap_4096.png")).astype(np.float32)
    h = meta["png_black_m"] + raw / 65535.0 * (meta["png_white_m"] - meta["png_black_m"])
    mask_rgb = np.asarray(Image.open(g.SOURCE_DIR / "mask_4096.png").convert("RGB")).astype(int)
    lut = np.array([s[1] for s in g.SURFACES])
    idx = np.argmin(((mask_rgb[..., None, :] - lut[None, None]) ** 2).sum(-1), axis=-1).astype(np.uint8)
    with (g.SOURCE_DIR / "towns.csv").open(encoding="utf-8") as f:
        towns = list(csv.DictReader(f))
    roads = json.loads((g.SOURCE_DIR / "roads.json").read_text(encoding="utf-8"))
    pois = json.loads((g.SOURCE_DIR / "pois.json").read_text(encoding="utf-8"))
    return h, idx, towns, roads, pois


def cell(x, y):
    r = int(np.clip((g.SIZE_M - y) / g.CELL, 0, g.GRID - 1))
    c = int(np.clip(x / g.CELL, 0, g.GRID - 1))
    return r, c


def world(r, c):
    return (c + 0.5) * g.CELL, g.SIZE_M - (r + 0.5) * g.CELL


def farthest_points(points: np.ndarray, k: int, rng) -> np.ndarray:
    if len(points) <= k:
        return points
    chosen = [int(rng.integers(len(points)))]
    d = np.hypot(*(points - points[chosen[0]]).T)
    for _ in range(k - 1):
        i = int(np.argmax(d))
        chosen.append(i)
        d = np.minimum(d, np.hypot(*(points - points[i]).T))
    return points[chosen]


def keep_out(towns, pois, extra=0.0):
    zones = [(float(t["x"]), float(t["y"]), float(t["radius"]) + extra + (300.0 if t["tier"] == "military" else 0.0))
             for t in towns]
    zones += [(p["x"], p["y"], p["radius"] + extra) for p in pois if p["kind"] != "farm"]
    return zones


def outside(zones, x, y):
    return all(math.hypot(x - zx, y - zy) > zr for zx, zy, zr in zones)


def spawn_points(h, land, slope, towns, pois, rng):
    dist_sea = ndimage.distance_transform_edt(land) * g.CELL
    # Only the two main islands: nobody should spawn on an islet with no way off.
    lab, n = ndimage.label(land)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    main = np.isin(lab, np.argsort(sizes)[-2:])
    cand = main & (dist_sea > 15.0) & (dist_sea < 60.0) & (slope < 12.0) & (h < 15.0)
    rows, cols = np.nonzero(cand[::4, ::4])
    pts = np.array([world(r * 4, c * 4) for r, c in zip(rows, cols)])
    zones = keep_out(towns, pois, 150.0)
    whakaari = [p for p in pois if p["kind"] == "whakaari"]
    zones += [(p["x"], p["y"], p["radius"] + 600.0) for p in whakaari]
    pts = np.array([p for p in pts if outside(zones, *p)])
    return farthest_points(pts, SPAWN_COUNT, rng)


def write_spawns(points, path):
    bubbles = "\n".join(f'            <pos x="{x:.1f}" z="{y:.1f}" />' for x, y in points)

    def block(tag, min_inf, max_inf):
        return f"""    <{tag}>
        <spawn_params>
            <min_dist_infected>{min_inf}</min_dist_infected>
            <max_dist_infected>{max_inf}</max_dist_infected>
            <min_dist_player>65</min_dist_player>
            <max_dist_player>150</max_dist_player>
            <min_dist_static>0</min_dist_static>
            <max_dist_static>2</max_dist_static>
        </spawn_params>
        <generator_params>
            <grid_density>4</grid_density>
            <grid_width>60</grid_width>
            <grid_height>60</grid_height>
            <min_dist_static>0</min_dist_static>
            <max_dist_static>2</max_dist_static>
            <min_steepness>-45</min_steepness>
            <max_steepness>45</max_steepness>
        </generator_params>
        <generator_posbubbles>
{bubbles}
        </generator_posbubbles>
    </{tag}>"""

    text = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<!-- Coastal spawns for Aotearoa, '
            'generated by tools/build_mission.py. -->\n<playerspawnpoints>\n'
            + "\n".join([block("fresh", 30, 70), block("hop", 25, 70), block("travel", 25, 70)])
            + "\n</playerspawnpoints>\n")
    path.write_text(text, encoding="utf-8")


def highway_samples(roads, step):
    out = []
    for r in roads["roads"]:
        if r["kind"] != "highway":
            continue
        pts = np.array(r["points"])
        seg = np.hypot(*np.diff(pts, axis=0).T)
        dist = np.concatenate([[0.0], np.cumsum(seg)])
        for s in np.arange(step / 2, dist[-1], step):
            i = int(np.searchsorted(dist, s) - 1)
            i = max(0, min(i, len(pts) - 2))
            k = (s - dist[i]) / max(seg[i], 1e-6)
            x, y = pts[i] + k * (pts[i + 1] - pts[i])
            dx, dy = pts[i + 1] - pts[i]
            out.append((float(x), float(y), math.degrees(math.atan2(dx, dy)) % 360, r["ref"]))
    return out


def events(h, idx, land, slope, towns, roads, pois, rng):
    ev: dict[str, list[tuple[float, float, float]]] = {}
    zones = keep_out(towns, pois, 60.0)

    # Cars parked on the left verge of the highways, facing along them.
    for i, (x, y, hd, _) in enumerate(p for p in highway_samples(roads, VEHICLE_SPACING_M) if outside(zones, p[0], p[1])):
        side = math.radians(hd - 90.0)
        px, py = x + 3.5 * math.sin(side), y + 3.5 * math.cos(side)
        ev.setdefault(VEHICLES[i % len(VEHICLES)], []).append((px, py, hd))

    # Boats tied up off each port pad.
    for p in pois:
        if p["kind"] != "port":
            continue
        pts = np.array(p["surfaces"][0]["points"])
        for (ax, ay), (bx, by) in zip(pts, np.roll(pts, -1, axis=0)):
            mx, my = (ax + bx) / 2, (ay + by) / 2
            nx, ny = mx - p["x"], my - p["y"]
            norm = math.hypot(nx, ny) or 1.0
            ox, oy = mx + nx / norm * 25.0, my + ny / norm * 25.0
            r, c = cell(ox, oy)
            if h[r, c] < -1.0:
                ev.setdefault("VehicleBoat", []).append((ox, oy, math.degrees(math.atan2(bx - ax, by - ay)) % 360))
                break

    # Helicopter crashes in open country well away from towns and roads.
    open_land = land & (slope < 8.0) & np.isin(idx, [g.SURFACE_INDEX[n] for n in ("pasture", "farmland", "tussock")])
    road_mask = np.asarray(Image.open(g.SOURCE_DIR / "roads_4096.png")) > 0
    open_land &= ndimage.distance_transform_edt(~road_mask) * g.CELL > 60.0
    rows, cols = np.nonzero(open_land[::6, ::6])
    pts = np.array([world(r * 6, c * 6) for r, c in zip(rows, cols)])
    far = keep_out(towns, pois, 300.0)
    pts = np.array([q for q in pts if outside(far, *q)])
    for x, y in farthest_points(pts, HELI_CRASHES, rng):
        ev.setdefault("StaticHeliCrash", []).append((x, y, float(rng.uniform(0, 360))))

    # Police cars on town streets; convoys on the highways near the bases.
    for t in towns:
        if t["tier"] not in ("capital", "city", "town"):
            continue
        streets = [r for r in roads["roads"] if r["kind"] == "street" and r["ref"] == class_name(t["name"])]
        for r in rng.permutation(len(streets))[:2 if t["tier"] == "town" else 3]:
            (ax, ay), (bx, by) = streets[r]["points"][0], streets[r]["points"][-1]
            ev.setdefault("StaticPoliceCar", []).append(((ax + bx) / 2, (ay + by) / 2,
                                                         math.degrees(math.atan2(bx - ax, by - ay)) % 360))
    bases = [t for t in towns if t["tier"] == "military"]
    for x, y, hd, _ in highway_samples(roads, 150.0):
        for b in bases:
            d = math.hypot(x - float(b["x"]), y - float(b["y"]))
            if float(b["radius"]) + 150.0 < d < 1500.0:
                ev.setdefault("StaticMilitaryConvoy", [])
                if all(math.hypot(x - a, y - c) > 500.0 for a, c, _ in ev["StaticMilitaryConvoy"]):
                    ev["StaticMilitaryConvoy"].append((x, y, hd))
    return ev


def class_name(name: str) -> str:
    import unicodedata

    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "".join(ch for ch in ascii_name.title() if ch.isalnum())


def write_events(ev, path):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             "<!-- Event positions for Aotearoa, generated by tools/build_mission.py. -->", "<eventposdef>"]
    for name in sorted(ev):
        lines.append(f'    <event name="{name}">')
        lines += [f'        <pos x="{x:.1f}" z="{y:.1f}" a="{a:.0f}" />' for x, y, a in ev[name]]
        lines.append("    </event>")
    lines.append("</eventposdef>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def infected_zones(land, towns, pois, rng):
    zones = []

    def scatter(x, y, radius, n, name, dmin, dmax, r=45.0):
        placed = 0
        for _ in range(n * 30):
            if placed >= n:
                break
            a, d = rng.uniform(0, 2 * math.pi), radius * math.sqrt(rng.uniform(0, 1))
            px, py = x + d * math.cos(a), y + d * math.sin(a)
            rr, cc = cell(px, py)
            if land[rr, cc]:
                zones.append((name, dmin, dmax, px, py, r))
                placed += 1

    for t in towns:
        name, per100, dmin, dmax = INFECTED_ZONES[t["tier"]]
        radius = float(t["radius"])
        scatter(float(t["x"]), float(t["y"]), radius * 0.9, max(2, int(round(per100 * radius / 100.0))), name, dmin, dmax)
    for p in pois:
        if p["kind"] == "farm":
            scatter(p["x"], p["y"], 20.0, 1, "InfectedSolitude", 1, 2, 30.0)
        elif p["kind"] in ("port", "industrial"):
            scatter(p["x"], p["y"], 60.0, 2, "InfectedIndustrial", 2, 4)
        elif p["kind"] == "airfield":
            kind = "InfectedMilitary" if "Ōhakea" in p["label"] else "InfectedIndustrial"
            scatter(p["x"], p["y"], 150.0, 3, kind, 2, 5)
        elif p["kind"] == "naval":
            scatter(p["x"], p["y"], 60.0, 3, "InfectedMilitary", 2, 4)
        elif p["kind"] == "landmark":
            scatter(p["x"], p["y"], 20.0, 1, "InfectedSolitude", 1, 2, 30.0)
        elif p["kind"] in ("ski", "hobbiton"):
            scatter(p["x"], p["y"], 50.0, 2, "InfectedVillage", 1, 3)
    return zones


def write_zombie_territories(zones, path):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
             "<!-- Infected zones for Aotearoa, generated by tools/build_mission.py. -->",
             "<territory-type>", '    <territory color="4291611852">']
    lines += [f'        <zone name="{n}" smin="0" smax="0" dmin="{a}" dmax="{b}" x="{x:.1f}" z="{y:.1f}" r="{r:.0f}" />'
              for n, a, b, x, y, r in zones]
    lines += ["    </territory>", "</territory-type>", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_effect_area(h, land, pois, path):
    areas, safe = [], []
    for p in pois:
        if p["kind"] != "whakaari":
            continue
        r, c = cell(p["x"], p["y"])
        areas.append({
            "AreaName": "Whakaari",
            "Type": "ContaminatedArea_Static",
            "TriggerType": "ContaminatedTrigger",
            "Data": {
                "Pos": [round(p["x"], 1), round(float(max(h[r, c], 0.0)), 1), round(p["y"], 1)],
                "Radius": round(p["zone"]["radius"]),
                "PosHeight": 60,
                "NegHeight": 20,
                "InnerRingCount": 2,
                "InnerPartDist": 50,
                "OuterRingToggle": 1,
                "OuterPartDist": 40,
                "OuterOffset": 0,
                "VerticalLayers": 0,
                "VerticalOffset": 0,
                "ParticleName": "graphics/particles/contaminated_area_gas_bigass",
            },
            "PlayerData": {
                "AroundPartName": "graphics/particles/contaminated_area_gas_around",
                "TinyPartName": "graphics/particles/contaminated_area_gas_around_tiny",
                "PPERequesterType": "PPERequester_ContaminatedAreaTint",
            },
        })
        # Safe positions are where players caught in the zone at login get moved to: the
        # nearest stretch of mainland coast.
        dist_sea = ndimage.distance_transform_edt(land) * g.CELL
        cand = np.argwhere((dist_sea > 20.0) & (dist_sea < 60.0))
        pts = np.array([world(rr, cc) for rr, cc in cand[::7]])
        d = np.hypot(pts[:, 0] - p["x"], pts[:, 1] - p["y"])
        pts = pts[d > p["zone"]["radius"] + 300.0]
        d = d[d > p["zone"]["radius"] + 300.0]
        for x, y in pts[np.argsort(d)[:200:50]]:
            safe.append([round(float(x), 1), round(float(y), 1)])
    path.write_text(json.dumps({"Areas": areas, "SafePositions": safe}, indent=4, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def write_gameplay_snippet(path):
    data = {
        "WorldsData": {
            "objectSpawnersArr": ["aotearoa/towns_spawner.json", "aotearoa/pois_spawner.json"],
            "environmentMinTemps": MIN_TEMPS,
            "environmentMaxTemps": MAX_TEMPS,
        }
    }
    path.write_text(json.dumps(data, indent=4) + "\n")


INIT_C = r"""// init.c for Aotearoa, based on vanilla dayzOffline.chernarusplus.
void main()
{
	Hive ce = CreateHive();
	if ( ce )
		ce.InitOffline();

	// Keep the date in the southern summer (January to February).
	int year, month, day, hour, minute;
	int reset_month = 1, reset_day = 10;
	GetGame().GetWorld().GetDate(year, month, day, hour, minute);
	if ((month == reset_month) && (day < reset_day))
	{
		GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
	}
	else if ((month == reset_month + 1) && (day > reset_day))
	{
		GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
	}
	else if ((month < reset_month) || (month > reset_month + 1))
	{
		GetGame().GetWorld().SetDate(year, reset_month, reset_day, hour, minute);
	}

	// Loot positions: once the world is built, uncomment the next line, start the server once,
	// and copy storage_1/export/mapgrouppos.xml into this mission folder. Then comment it out.
	// GetCEApi().ExportProxyData(Vector(12800, 0, 12800), 25600);
}

class CustomMission: MissionServer
{
	void SetRandomHealth(EntityAI itemEnt)
	{
		if ( itemEnt )
		{
			float rndHlt = Math.RandomFloat( 0.45, 0.65 );
			itemEnt.SetHealth01( "", "", rndHlt );
		}
	}

	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		Entity playerEnt;
		playerEnt = GetGame().CreatePlayer( identity, characterName, pos, 0, "NONE" );
		Class.CastTo( m_player, playerEnt );
		GetGame().SelectPlayer( identity, m_player );
		return m_player;
	}

	override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
	{
		EntityAI itemClothing;
		EntityAI itemEnt;
		float rand;

		itemClothing = player.FindAttachmentBySlotName( "Body" );
		if ( itemClothing )
		{
			SetRandomHealth( itemClothing );
			itemEnt = itemClothing.GetInventory().CreateInInventory( "BandageDressing" );
			player.SetQuickBarEntityShortcut( itemEnt, 2 );

			string chemlightArray[] = { "Chemlight_White", "Chemlight_Yellow", "Chemlight_Green", "Chemlight_Red" };
			int rndIndex = Math.RandomInt( 0, 4 );
			itemEnt = itemClothing.GetInventory().CreateInInventory( chemlightArray[rndIndex] );
			SetRandomHealth( itemEnt );
			player.SetQuickBarEntityShortcut( itemEnt, 1 );

			rand = Math.RandomFloatInclusive( 0.0, 1.0 );
			if ( rand < 0.35 )
				itemEnt = player.GetInventory().CreateInInventory( "Apple" );
			else if ( rand > 0.65 )
				itemEnt = player.GetInventory().CreateInInventory( "Pear" );
			else
				itemEnt = player.GetInventory().CreateInInventory( "Plum" );
			player.SetQuickBarEntityShortcut( itemEnt, 3 );
			SetRandomHealth( itemEnt );
		}

		itemClothing = player.FindAttachmentBySlotName( "Legs" );
		if ( itemClothing )
			SetRandomHealth( itemClothing );

		itemClothing = player.FindAttachmentBySlotName( "Feet" );
	}
};

Mission CreateCustomMission(string path)
{
	return new CustomMission();
}
"""

SERVER_CFG = """// serverDZ.cfg template for an Aotearoa server. Start the server with -mod=@Aotearoa
// (and the same mod on clients), and put dayzOffline.aotearoa in the server's mpmissions folder.
hostname = "Aotearoa";
password = "";
passwordAdmin = "CHANGE_ME";
description = "A 25.6 km New Zealand terrain";
maxPlayers = 60;
verifySignatures = 2;
forceSameBuild = 1;
disableVoN = 0;
vonCodecQuality = 20;
disable3rdPerson = 0;
disableCrosshair = 0;
disablePersonalLight = 1;
lightingConfig = 0;
serverTime = "SystemTime";
serverTimeAcceleration = 4;
serverNightTimeAcceleration = 8;
serverTimePersistent = 0;
guaranteedUpdates = 1;
loginQueueConcurrentPlayers = 5;
loginQueueMaxPlayers = 500;
instanceId = 1;
storageAutoFix = 1;
enableCfgGameplayFile = 1;

class Missions
{
	class DayZ
	{
		template = "dayzOffline.aotearoa";
	};
};
"""


def draw_preview(spawns, ev, zones):
    from PIL import ImageDraw

    img = Image.open(g.PREVIEW_DIR / "relief_2048.png").convert("RGB")
    d = ImageDraw.Draw(img)
    k = img.width / g.SIZE_M

    def dot(x, y, r, fill):
        px, py = x * k, (g.SIZE_M - y) * k
        d.ellipse([px - r, py - r, px + r, py + r], fill=fill, outline=(0, 0, 0))

    for _, _, _, x, y, _ in zones:
        dot(x, y, 2, (150, 0, 0))
    for name, pts in ev.items():
        colour = {"StaticHeliCrash": (255, 140, 0), "StaticMilitaryConvoy": (60, 90, 40), "StaticPoliceCar": (40, 80, 255),
                  "VehicleBoat": (0, 220, 255)}.get(name, (255, 255, 255))
        for x, y, _ in pts:
            dot(x, y, 3, colour)
    for x, y in spawns:
        dot(x, y, 6, (0, 255, 0))
    return img


def main() -> None:
    rng = np.random.default_rng(g.SEED + 20)
    h, idx, towns, roads, pois = load()
    land = h > 0.3
    gy, gx = np.gradient(h, g.CELL)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    out = OUT / MISSION
    out.mkdir(parents=True, exist_ok=True)
    (out / "init.c").write_text(INIT_C, newline="\r\n")
    (OUT / "serverDZ.cfg").write_text(SERVER_CFG, newline="\r\n")

    spawns = spawn_points(h, land, slope, towns, pois, rng)
    write_spawns(spawns, out / "cfgplayerspawnpoints.xml")
    ev = events(h, idx, land, slope, towns, roads, pois, rng)
    write_events(ev, out / "cfgeventspawns.xml")
    zones = infected_zones(land, towns, pois, rng)
    write_zombie_territories(zones, out / "env" / "zombie_territories.xml")
    write_effect_area(h, land, pois, out / "cfgeffectarea.json")
    write_gameplay_snippet(out / "cfggameplay.worldsdata.json")
    economy.build(out, h, idx, land, towns, pois, rng)

    draw_preview(spawns, ev, zones).save(g.PREVIEW_DIR / "mission_2048.png", optimize=True)
    print(f"Spawn points: {len(spawns)}")
    for name in sorted(ev):
        print(f"  {name}: {len(ev[name])}")
    print(f"Infected zones: {len(zones)}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
