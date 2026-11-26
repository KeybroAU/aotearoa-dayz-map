# Terrain Builder walkthrough

A step-by-step checklist that takes this repo to a packed `@Aotearoa` mod you can play on. Tick each box as you go. Every number and path below matches what the repo generates, so you can copy them as they are.

Menu names are from the Steam version of DayZ Tools. If a menu has moved in your version, the field names are still the same, so search for those.

**Time:** about 2 to 4 hours the first time, mostly waiting on imports and layer generation.
**Disk:** about 40 GB free on the drive that holds P:.
**Memory:** 16 GB or more. Layer generation for a 25600 px satellite is heavy.

---

## 0. Before you start

- [ ] **DayZ Tools** installed from Steam (Library → Tools → DayZ Tools).
- [ ] **Python 3.10+** installed with "Add python.exe to PATH" ticked.
- [ ] **P: drive mounted.** Open DayZ Tools → **Settings**, set the Work Drive path (for example `D:\DayZWork`), click **Mount**.
- [ ] **Game data extracted to P:.** DayZ Tools → **Tools → Extract Game Data**. When it finishes, `P:\DZ\structures`, `P:\DZ\plants` and `P:\DZ\surfaces` should exist, and the DLC folders `P:\DZ\structures_bliss` and `P:\DZ\plants_takistan`. Install the DLC in Steam first (DayZ → Properties → DLC) and re-run the extraction after big game updates.

> Check: open `P:\DZ\surfaces\data\terrain` in Explorer and confirm `cp_grass.rvmat` is there. If it isn't, extraction didn't finish.

---

## 1. Put the map on P: and build the big files

- [ ] Copy (or `git clone`) this repo to **`P:\maps\aotearoa`**. The folder must be exactly that, because `config.cpp`, `$PBOPREFIX$` and `layers.cfg` all use `maps\aotearoa`.
- [ ] Double-click **`setup.bat`** (installs the Python packages, once).
- [ ] Double-click **`build_all.bat`** and wait about 25 minutes. It ends with `All checks passed` and `All done`.

> Check: these files now exist:
>
> | File | Size (roughly) |
> |---|---|
> | `source\heightmap_4096.asc` | 120 MB |
> | `source\satellite_25600.png` | 1 to 2 GB |
> | `source\mask_25600.png` | 30 to 60 MB |
> | `preview\player_map_4096.jpg` | 1.6 MB |

- [ ] **Check the model names before importing objects** (optional now, but it saves a re-import later). In a Command Prompt:

  ```bat
  dir /s /b P:\DZ\*.p3d > P:\maps\aotearoa\models.txt
  cd /d P:\maps\aotearoa\tools
  python check_models.py ..\models.txt
  ```

  Every model it lists as not found will be skipped by Terrain Builder. Send `models.txt` to the map maintainer, or use `--fix` then `--apply` (see the README).

---

## 2. Create the project

- [ ] Open **Terrain Builder** (DayZ Tools → Terrain Builder).
- [ ] **File → New project**.
  - Name: `aotearoa`
  - Location: `P:\maps\aotearoa\source`
- [ ] Save straight away (**File → Save project**). Save often from here on; Terrain Builder can crash on big imports.
- The console may say `Can not enumerate files in directory 'p:\maps\aotearoa\source\aotearoa.cache\'`. That's normal for a new project: the cache folder is made on the first save or import. Create the empty folder yourself if you want the message gone.

---

## 3. Mapframe properties

The mapframe is the square that becomes the world.

- [ ] In the **Mapframes** panel, right-click → **Add mapframe** (if your project didn't make one), then right-click it → **Properties**.

### Location tab

| Field | Value |
|---|---|
| Easting | **200000** |
| Northing | **0** |

### Samplers tab

| Field | Value |
|---|---|
| Terrain grid size | **4096 x 4096** |
| Terrain cell size | **6.25** m |
| Terrain size (shown) | **25600** m |
| Satellite / surface mask image size | **25600 x 25600** px |
| Satellite resolution (shown) | **1** m per px |

### Processing tab

| Field | Value |
|---|---|
| Tile size | **512** px |
| Desired overlap | **16** px |
| Layers configuration file | `P:\maps\aotearoa\source\layers.cfg` |
| Output root folder | `P:\maps\aotearoa\data\layers` |

- [ ] Click **OK**, then save the project.

> Check: the mapframe outline in the main view is a square. Hovering the bottom-left corner shows about 200000, 0 and the top-right shows about 225600, 25600.

---

## 4. Import the heightmap

- [ ] **File → Import → Terrain**, choose `P:\maps\aotearoa\source\heightmap_4096.asc`.
- [ ] Accept the defaults. The file header already carries the corner (200000, 0) and cell size (6.25).
- [ ] Switch to 3D view (**View → 3D view**, or the Buldozer button) and look around.

> Check:
> - Two islands, north-up, with snowy Southern Alps down the South Island and cones in the middle of the North Island.
> - The lowest point is about -53 m (sea floor) and the highest about 532 m.
> - If the terrain is flat or is a tiny square in one corner, the mapframe sizes in step 3 don't match the file. Fix them and import again.

---

## 5. Import the satellite and surface mask

- [ ] **File → Import → Satellite image**, choose `source\satellite_25600.png`.
- [ ] **File → Import → Surface mask**, choose `source\mask_25600.png`.

Both take a few minutes. Terrain Builder may look frozen while it reads the satellite; leave it.

> Check: toggle the satellite on in the 2D view. Towns show as grids of rooftops, roads as grey lines, the railway as a dark line with a lighter bed, and lakes are blue. If the image is shifted, the mapframe location (step 3) is wrong.

**Surface mask colours.** They must match `layers.cfg`:

| Layer | RGB |
|---|---|
| beach | 255, 230, 140 |
| pasture | 120, 190, 60 |
| farmland | 200, 200, 90 |
| bush | 20, 90, 30 |
| pine | 60, 110, 70 |
| tussock | 190, 160, 80 |
| scree | 150, 150, 150 |
| rock | 90, 80, 75 |
| volcanic | 120, 60, 50 |

---

## 6. Template libraries (the models)

Terrain Builder places objects by **template name**, which is the model file name in lowercase without `.p3d`. A missing template means a missing object, so do this before importing objects.

- [ ] Open the **Library manager** panel (**Window → Library manager**, if hidden).
- [ ] For each folder below: right-click → **Create library from folder** (or **New library → From directory**), point it at the folder, and accept.

| Library | Folder | Used by |
|---|---|---|
| residential | `P:\DZ\structures\residential` | towns, baches, holiday parks, huts |
| industrial | `P:\DZ\structures\industrial` | ports, containers, factories, sheds, power station |
| military | `P:\DZ\structures\military` | bases, tents, towers, Devonport |
| specific | `P:\DZ\structures\specific` | airfields, lighthouse, bus stop |
| rail | `P:\DZ\structures\rail` | track, rail bridges, stations |
| roads | `P:\DZ\structures\roads` | bridges, lamps, guardrails, wrecks |
| walls | `P:\DZ\structures\walls` | farm and garden fences |
| trees | `P:\DZ\plants\tree` | forest, garden trees |
| bushes | `P:\DZ\plants\bush` | understorey, hedgerows |
| rocks | `P:\DZ\rocks` | rocks and stones |
| wrecks | `P:\DZ\structures\wrecks` | roadside and town wrecks |
| trees_takistan | `P:\DZ\plants_takistan\tree` | pine plantations (Brutian pine), garden plum trees |
| bushes_takistan | `P:\DZ\plants_takistan\bush` | tree ferns in the native bush (cycads) |
| bliss | `P:\DZ\structures_bliss` | bunkers, control tower, guardhouse, church ruin |

Folder names can differ slightly between DayZ versions. If one doesn't exist, search P:\DZ for the model (for example `rail_track`) and use the folder it's in.

- [ ] Save the project.

> Check: in the library list, search for `house_1w01`, `t_pinusbrutia_2s`, `b_cycas_2s` and `wall_fen1_5`. All four should be found.

---

## 7. Import the objects

Put each file on its own layer so you can hide, re-import or delete it on its own.

- [ ] In the **Layers** panel, right-click → **Add layer** and make one layer per file below (use the names in the first column).
- [ ] Select a layer, then **File → Import → Objects**, choose the file, and pick **Text file** (the format is `"template";x;y;yaw;pitch;roll;scale;zoffset;`).
- [ ] Do them in this order (smallest first, so problems show early):

| Layer | File in `source\objects\` | Objects |
|---|---|---|
| towns | `towns_tb.txt` | 3,143 |
| sites | `pois_tb.txt` | 786 |
| setpieces | `setpieces_tb.txt` | 54 |
| bridges | `bridges_tb.txt` | 72 |
| rail | `rail_tb.txt` | 1,545 |
| powerlines | `powerlines_tb.txt` | 989 |
| guardrails | `guardrails_tb.txt` | 1,502 |
| fences | `fences_tb.txt` | 3,500 |
| wrecks | `wrecks_tb.txt` | 133 |
| streetlamps | `streetlamps_tb.txt` | 3,997 |
| busstops | `busstops_tb.txt` | 47 |
| townwrecks | `townwrecks_tb.txt` | 164 |
| gardenfences | `gardenfences_tb.txt` | 6,774 |
| gardentrees | `gardentrees_tb.txt` | 1,331 |
| hedgerows | `hedgerows_tb.txt` | 14,066 |
| rocks | `rocks_tb.txt` | 20,989 |
| forest | `forest_tb.txt` | 357,383 (slow, save first) |
| lakes | `lakes_tb.txt` | 267, see below |

- [ ] After each import, glance at the log/status. If it says templates were missing, note the names and fix them (step 1 checker, or step 6 libraries), then delete that layer's objects and import again.

**Set pieces.** `setpieces_tb.txt` holds the landmarks, the Interislander wreck, the Hercules crash and the base extensions. Until they are in the world, the mission spawns them with the object spawner. Once you have exported the world with them, pack with `pack.bat --setpieces-in-wrp` so they are not spawned twice.

**Lakes.** `lakes_tb.txt` places a 50 m water plane per tile, and its last field is the lake's **absolute** water level, not an offset from the ground. Either:
- after importing, select all objects in the `lakes` layer and switch them to absolute height in the object properties, or
- skip this file until you have a water plane model. `aotearoa_water_50` is a placeholder, and vanilla DayZ has no standalone lake surface.

> Check, in 3D view:
> - Auckland: houses sit on the ground in a grid, with street lamps along the streets and fences behind the houses.
> - A river crossing on a highway has a bridge deck level with the road.
> - The railway near Waiouru runs as one continuous line of track.
> - Forest stands are thick on the West Coast and in rows in the pine plantations.

---

## 8. Roads

- [ ] Add a layer called `roads`.
- [ ] **File → Import → Shapes**, choose `P:\maps\aotearoa\data\roads\roads.shp`. Keep `RoadsLib.cfg` in the same folder; Terrain Builder reads it from there.
- [ ] Check that road types are recognised (the `ID` field picks the type):

| ID | Type | Width |
|---|---|---|
| 1 | highway | 8 m |
| 2 | street | 6 m |
| 3 | track | 4 m |
| 4 | gravel | 5 m |

The textures in `RoadsLib.cfg` are placeholders that point at `DZ\structures\roads\data\`. If roads show as untextured, open that folder on P: and change the `.paa` / `.rvmat` names in `RoadsLib.cfg` to ones that exist.

> Check: SH1 runs the length of both islands, and gravel roads branch out to the small hamlets.

---

## 9. Generate layers

- [ ] Save the project.
- [ ] Right-click the mapframe → **Generate layers** (or **Tools → Generate layers**). This cuts the satellite and mask into tiles and writes them to `data\layers`. Expect 20 to 60 minutes.

> Check: `P:\maps\aotearoa\data\layers` fills with `s_*.paa` (satellite), `m_*.paa` (mask) and `p_*.rvmat` files.

**"Rvmat conf - LayerRvmatCFG.cpp ... Source file cannot be opened" error.** A material in `layers.cfg` isn't on your P: drive. Check that `P:\DZ\surfaces\data\terrain\` exists and holds the `cp_*.rvmat` files (if the folder is missing, run **Extract Game Data** in DayZ Tools → Tools/P: drive setup). If one file is still missing, swap that line for another `cp_*.rvmat` in that folder, then reload the layers config in the mapframe's **Processing** tab.

**"Too many surfaces on tile" error.** Each 512 px tile can mix only a few surface types, and this map has nine. Fix it by merging similar layers in `layers.cfg` and the mask, in this order until the error goes away:
1. farmland into pasture
2. pine into bush
3. volcanic into scree

To merge, edit `SURFACE_INDEX` / the layer list in `tools/generate_terrain.py` (or just recolour the merged layer in the mask), run `build_all.bat` again, re-import the mask (step 5), and generate layers again.

---

## 10. Export the world

- [ ] **File → Export → WRP** (sometimes **Export world**).
- [ ] Save to **`P:\maps\aotearoa\world\aotearoa.wrp`**. Create the `world` folder if it doesn't exist.

> Check: `aotearoa.wrp` exists and is a few hundred MB.

---

## 11 to 13, the quick way: `pack.bat`

- [ ] Double-click **`pack.bat`** in `P:\maps\aotearoa` (or run `pack.bat --key aotearoa --zip` to sign and zip as well).
- [ ] When it finishes, copy everything in **`dist\server\`** into your DayZ Server folder, set `passwordAdmin` in `serverDZ.cfg`, and run `start_server.bat`.
- [ ] Give players **`dist\@Aotearoa`** (or `dist\Aotearoa_mod.zip`).
- [ ] Optional: add `--difficulty easy` or `--difficulty hard` to scale loot, vehicles and infected (see the README).
- [ ] Set `RConPassword` in `dist\server\profiles\BattlEye\BEServer_x64.cfg` if you use an RCon tool, and add admins' and banned players' IDs to `whitelist.txt` / `ban.txt` as needed.

It does the image conversion, packing, signing and mission merging in steps 11 to 13 for you. Then skip to the in-game checks at the end of step 13. If it fails, the step that failed is printed above the error, and you can do that step by hand below.

## 11. Branding images to .paa

- [ ] Open **ImageToPAA** (DayZ Tools → Tools → ImageToPAA).
- [ ] Convert, from `P:\maps\aotearoa\data\branding\`:

| From | To |
|---|---|
| `logo_512.png` | `logo_512_ca.paa` |
| `icon_128.png` | `icon_128_ca.paa` |
| `icon_64.png` | `icon_64_ca.paa` |
| `loading_1.jpg` (save as PNG first if the tool refuses JPG) | `loading_1_co.paa` |
| `map_picture.jpg` (same) | `map_picture_co.paa` |

`_ca` is for images with transparency, `_co` for images without.

---

## 12. Pack the mod

- [ ] Open **Addon Builder** (DayZ Tools → Addon Builder).
- [ ] Source directory: `P:\maps\aotearoa`
- [ ] Destination: a folder such as `D:\DayZMods\@Aotearoa\addons`
- [ ] **Options**:
  - Addon prefix: `maps\aotearoa`
  - Binarize: on
  - Files to copy directly: `*.paa;*.rvmat;*.wrp;*.png;*.jpg;*.hpp;*.cfg;*.shp;*.shx;*.dbf`
  - Exclude: `source\*;tools\*;preview\*;mission\*;docs\*;*.md;*.bat;*.txt;.git*`
- [ ] Click **Pack**. You get `aotearoa.pbo`.
- [ ] Copy `P:\maps\aotearoa\mod\mod.cpp` into `D:\DayZMods\@Aotearoa\`.
- [ ] If your server verifies signatures: DayZ Tools → **DS Utils**, make a key, sign `aotearoa.pbo`, and put the `.bikey` in the server's `keys` folder and `@Aotearoa\keys`.

> Check: `@Aotearoa\addons\aotearoa.pbo` is several hundred MB, and opening it in PBO Manager shows `config.cpp`, `world\aotearoa.wrp` and `data\layers\`.

---

## 13. Run a test server

- [ ] In your DayZ Server folder (Steam → Tools → DayZ Server):
  - copy `@Aotearoa` in;
  - copy vanilla `mpmissions\dayzOffline.chernarusplus` to `mpmissions\dayzOffline.aotearoa`, then copy everything from the repo's `mission\dayzOffline.aotearoa\` over it;
  - merge `cfggameplay.worldsdata.json` into the mission's `cfggameplay.json`;
  - paste the `<ce>` block from `cfgeconomycore.aotearoa.xml` into `cfgeconomycore.xml`;
  - copy `mission\serverDZ.cfg` and `mission\server\start_server.bat` next to `DayZServer_x64.exe`, and set `passwordAdmin`.
- [ ] Run `start_server.bat`.
- [ ] Start DayZ with `-mod=@Aotearoa` (DayZ Launcher → Mods → add local mod) and connect to `127.0.0.1:2302`.

> Check, in game:
> - You spawn on a coast in Farmer, Tramper or Beach gear, and get the "Kia ora" message.
> - The map (M) shows town names in both languages and the 1 km grid.
> - Walk into the nearest town: buildings have loot and doors open.
> - The server's `.RPT` log in `profiles\` has no long run of `Cannot create object` lines. If it does, those are model or class names to fix (step 1 checker).

---

## 14. After the first run

- [ ] Uncomment the `ExportProxyData` line in `init.c`, start the server once, copy `storage_1\export\mapgrouppos.xml` over the mission's `mapgrouppos.xml`, then comment the line out again. This gives exact loot positions.
- [ ] Paint `areaflags.map` using `preview\loot_tiers_2048.png` as the guide for the Value layer (DayZ Tools economy editor).
- [ ] Print or share `preview\player_map_4096.jpg` with players.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Heightmap imports flat or tiny | Mapframe sizes don't match | Step 3: grid 4096, cell 6.25, size 25600; re-import |
| Satellite or objects shifted by 200 km | Easting not set | Step 3: easting 200000, northing 0 |
| Objects missing after import | Template not in a library, or the name is wrong | Step 6, then `tools\check_models.py` |
| Buildings float or sink | Imported before the heightmap, or heights set to absolute | Import the terrain first; keep objects relative (except lakes) |
| "Too many surfaces on tile" | Too many layers in one tile | Step 9 merges |
| Roads have no texture | Placeholder paths in `RoadsLib.cfg` | Step 8 |
| Macrons show as boxes on the map | Map font lacks the character | Remove macrons in `tools\towns.csv`, regenerate |
| Game crashes loading the world | Bad WRP or missing `data\layers` in the PBO | Re-run steps 9, 10 and 12; check the PBO contents |
| No loot | `mapgrouppos.xml` not copied, or old economy | Step 13 copy, then step 14 export |
