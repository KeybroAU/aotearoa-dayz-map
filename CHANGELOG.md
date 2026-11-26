# Changelog

Versions follow `MAJOR.MINOR.PATCH`. `VERSION` holds the current one, and `mod/mod.cpp` must match it (the map checks enforce this). To release, note changes under `## Unreleased` and run `python tools/release.py --push`; GitHub builds the release. Old releases are never replaced (see "Releases" in the README).

## Unreleased

### Added

- V Energy (`Aotearoa_SodaCan_V`), a 500 ml can of the Kiwi guarana energy drink, in shops, schools, offices and the food stashes
- A custom model for it: a tall 500 ml can (`tools/drink_models.py` writes three LODs, the Geometry, the texture, the material and a render, and docs/CUSTOM_MODELS.md item 12 has the Object Builder steps). V uses the new can as soon as `structures/food/v_can/v_can.p3d` is committed, and a V-labelled vanilla can until then

## 0.6.8 - 2026-11-26

### Changed

- README setup refreshed for the food and drink, the food stashes, the work-in-progress food mod, releases and backups (Quick start, Files, Packing, Server setup and Regenerating)
- `build_all.bat` now checks the food textures and builds the work-in-progress food copy, and releases bump the work-in-progress mod's version too

## 0.6.7 - 2026-11-26

### Added

- Food stashes: eight crashed Countdown trucks on the state highways, the stock room behind every dairy and the pantry at each bach, holding New Zealand food and topped up every 45 minutes (`tools/food_stashes.py`, run by the server's `init.c`)
- Label templates for the work-in-progress food (`wip/food/templates/`): each pack's label at twice its size, with the hidden areas and a safe area marked, to draw real label artwork on

### Changed

- Food labels styled closer to the real packs: L&P's "World Famous in New Zealand" lozenge, Foxton's windmill, "Kiwi kids are Weet-Bix kids", Whittaker's gold rules and dog and cat paws on the pet food
- New Zealand food spawns where you'd expect it: snacks and fizzy in shops, schools and offices, milk powder and honey on farms, tinned fish on the coast, pet food on farms

## 0.6.6 - 2026-11-26

### Added

- `wip/food/`: a work-in-progress copy of the food and drink as a separate test mod (`@AotearoaFoodWIP`, `AotearoaWIP_*` classes, not in the loot), built by `tools/wip_food.py` and packed with `pack_mod.py --wip`. Label images dropped into `wip/food/labels/` (ignored by git) are fitted onto each pack's fronts

## 0.6.5 - 2026-11-26

### Added

- More New Zealand food and drink, replacing their vanilla items in the loot: Anchor Milk Powder, Airborne Mānuka Honey, Pump Water Bottle, Hellers Bacon, Tux Dog Food and Jellimeat (31 items in all)
- Release backups: every version's files are copied into a `release-archive` release after each release and weekly, and optionally mirrored to a second repo (`BACKUP_REPO` variable and `BACKUP_TOKEN` secret)
- Pre-release check: `tools/release.py` runs `nz_food.py --verify` first, and `preview/nz_food_layouts.png` shows every food texture with its vanilla layout outlined

## 0.6.4 - 2026-11-26

### Changed

- The rice packet is now Rice Risotto (`Aotearoa_RiceRisotto`), with arborio rice on the label. It replaces vanilla rice in the loot

### Added

- `tools/release.py` cuts a release from the Unreleased changelog notes, and `--revert-to vX.Y.Z` re-releases an older version's files as a new version
- `tools/backup_releases.py` backs up every release's files, notes and checksums outside GitHub
- The release workflow refuses to replace an existing release and publishes a `SHA256SUMS` file

## 0.6.3 - 2026-11-26

### Added
- Nine Steam Workshop screenshots (`workshop/screenshots/`, `tools/make_workshop_shots.py`), including a shop shelf of the New Zealand food, and a Discord release post (`workshop/discord_post.md`)
- New Zealand food and drink (`tools/nz_food.py`), 24 retextured vanilla items that replace the vanilla ones in the loot: L&P, Fresh Up Apple, Foxton Fizz Creaming Soda and Raspberry and Lift Plus cans; Bluebird Ready Salted, Salt & Vinegar and Chicken chips and Munchos Tomato; Griffin's Toffee Pops, Shrewsburys and Chocolate Thins and Pascall Pineapple Lumps; Whittaker's Creamy Milk, Dark Ghana and Peanut Slab; Sanitarium Weet-Bix; Wattie's Baked Beans, Spaghetti and Peach Slices; Sealord Tuna; Pams Sardines; Palm Corned Beef; Marmite. Tins keep their label once opened
- In-game test checklist (`docs/IN_GAME_TEST_CHECKLIST.md`)
- New Zealand loot pass, 75 items: NZDF Steyr AUGs, M4s and FALs at the bases; police Glocks; more hunting rifles, shotguns and farm ammo; mānuka honey and milk powder; fishing, fencing and tramping gear; gumboots, raincoats, wool jumpers and beanies. Handguns, the Desert Eagle and the AKM are rarer

### Changed
- Loot changes are built on the vanilla entries (`tools/vanilla_types.xml`, `tools/refresh_vanilla_types.py`), keeping vanilla lifetimes, quantities and shelf tags
- Civilian towns are tier 3 or lower and military areas reach 150 m past the bases (was 400 m): Palmerston North, Queenstown, Rakaia, Twizel, Lyttelton and Rakaia Huts are no longer tier 4

### Fixed
- Map labels no longer overlap on the player map, the map item and the towns preview (`tools/labelplace.py`): each name moves round its town or site until it's clear, crowded river and lake names are left off, and the map item uses NZ abbreviations (SLSC, Holiday Pk)
- The old loot changes spawned every New Zealand weapon fully loaded and every ammo box full, and dropped vanilla's shelf tags

## 0.6.2 - 2026-11-26

### Added
- "Designed by Keybro" and Keybrogaming.com in the corner of the in-game map screen on Aotearoa (`scripts/5_Mission/AotearoaMapMenu.c`, `gui/layouts/aotearoa_map_watermark.layout`)
- Steam Workshop preview image and description (`workshop/`), with the Discord link and the no-repack notice
- GitHub banner with "Designed by Keybro" and Keybrogaming.com (`.github/banner.png`), in the README and for the repo's social preview
- Commits, pull requests and releases post to Discord (`.github/workflows/discord.yml`, secret `DISCORD_WEBHOOK`)
- The map checks make sure every spawner class, Terrain Builder template and starting gear item exists in DayZ, using lists from Sam's DayZ Object Finder (`tools/dayz_classes.txt`, `tools/dayz_models.txt`; refresh with `tools/refresh_object_list.py`)
- The world's own navmesh settings, keeping the South and Stewart Islands (`filterIsolatedIslands = 0`)
- Takistan pines and cycads, and Livonia buildings, from the DLC data; the Terrain Builder guide lists the DLC template libraries

### Fixed
- `config/names.hpp` was missing a closing brace, which stopped the config from building
- Buildings and props with class names DayZ does not have, so they never spawned: warehouses (now `Land_Factory_Small`), power poles, churches, tanks, the transformer and the trader fences
- About 125,000 trees, rocks, guardrails, rail bridges and props used Terrain Builder templates that do not exist
- The Interislander wreck's lifeboat used the wrong model name
- The terrain inherited the Chernarus 2D map overlay (`userMapPath`) and navmesh
- Chernarus-only mission files (area flags, dirt and fruit clusters, underground triggers) were merged into the server mission; `cfgEffectArea.json` is now named as DayZ expects, so Linux servers no longer load the Chernarus gas zones
- Sakhal surface materials Terrain Builder could not open (`sa_volcanic_red.rvmat` and others) replaced with Chernarus ones
- Artillery sounds played over land; they now come from offshore

## 0.6.1 - 2026-11-25

### Added
- "Designed by Keybro" and Keybrogaming.com watermarks on the loading screens, map picture, player map and map item (`tools/watermark.py`), and the credit in both mods' descriptions

## 0.6.0 - 2026-11-25

### Added
- New Zealand weather and seasons from the mod's world scripts: months follow the server date, with NZ monthly temperatures, short winter and long summer days, 4 degrees colder per 100 m, westerly rain, a changeable spring and light snow in winter storms. Mild sea, lake and river temperatures
- Event groups (`cfgeventgroups.xml`): five military convoys round each base, police roadblocks on the highway into every city and town, 34 pile-ups on State Highway 1 and the other highways, and twelve derailed trains on the main lines (three military)
- Set pieces from vanilla objects (`tools/setpieces.py`): the Sky Tower, a Harbour Bridge, Parliament Buildings, ChristChurch Cathedral in ruins, the Interislander wreck off Wellington and a Hercules crash near Ōhakea. On the 2D map, the player map and the map item
- Bigger military bases at Waiouru, Burnham, Linton and Ōhakea, and the Waiouru Ammunition Area: bunkers inside a static gas zone with hard army infected
- Dynamic gas zones at the bases, airfields, industrial sites and ports, and in the back country
- Police, medic, firefighter and priest infected at police stations, hospitals, fire stations and churches
- Motorbikes in towns and at baches, holiday parks, surf clubs and huts; plank piles at farms, industrial sites, huts, stations and ports
- `pack.bat --setpieces-in-wrp` for once the set pieces are built into the world

### Changed
- Wildlife: no wolves, bears, roe deer or foxes. More sheep, red deer, goats, cattle and wild pigs; red deer mostly in the high bush and goats on steep country
- More heli crashes, convoys, police situations and trains, and the vanilla police car wrecks switched on
- Chateau Tongariro is vanilla's grand hotel

### Fixed
- Military convoys spawned nothing (their positions had no group)
- Military infected used a zone name DayZ does not have, so no soldiers spawned at the bases
- Building rotations in the generated `mapgrouppos.xml` were mirrored, so loot could spawn outside the walls

## 0.5.0 - 2026-11-25

### Added
- In-game map item: a new mod, `@AotearoaMap`, with the class `AotearoaMap` (built on `ChernarusMap`). It has its own cover, a labelled sheet with the 1 km grid, and a legend listing every town and named place with its grid square. It takes over the vanilla map's loot spawns. `pack.bat` packs, signs and loads it; pass `--no-map-item` to leave it out
- Every starting gear preset carries the map, and each trading post has a navigation stall selling it, plus compasses, binoculars, chemlights and torches (Expansion market and trader files, TraderPlus price snippet)
- 2D map labels for 24 rivers, 16 peaks and ranges, 15 lakes, 13 seas, bays and harbours, and the 19 railway stations (`tools/labels.py`). They also appear on the player map and the map item
- Rakaia township on SH1 and the Main North Line, on the north bank of the Rakaia River
- Rakaia Huts, the fishing settlement at the Rakaia river mouth, with baches, sheds and a gravel lane
- Sign model hand-off: `docs/models/SIGNS_BRIEF.md`, the two sign materials and a dimensioned reference sheet (`tools/sign_handoff.py`)
- A map item zip on each release; the models zip now has the sign reference sheet

### Changed
- Loot is scaled to the map's loot points (52% of Chernarus's), so each building holds about as much as on Chernarus. `pack.bat --vanilla-loot` keeps vanilla amounts
- Farm utes fill any land more than 1 km from a vehicle (worst gap 1.7 km, now 1.06 km)
- The world sets its own map name and textures, so a vanilla `ChernarusMap` shows Aotearoa too
- Map labels use the location types DayZ's map styles (`Capital`, `City`, `Village`, `Local`)

### Fixed
- Trader site grid squares in `mission/mods/README.md` now count from the north, like the in-game map

## 0.4.0 - 2026-11-25

### Added
- Road signs: green place-name signs on every road into a town (with Māori names), State Highway shields, 50 and 100 km/h signs, Give Way and One Lane Bridge signs. That's 790 signs, generated with their textures and config; the two simple sign models are made from `docs/models/`
- Ready-to-import blockout models for a Kiwi bach, DOC hut, woolshed and corner dairy (`tools/make_models.py`), with tiling textures and config classes
- Trader sites for server mods: Waikato, Central Plateau and Rakaia trading posts with safe zones, and a Mackenzie black market. Fenced compounds of vanilla objects, DayZ Expansion trader NPCs, trader zones, safe zone and spawn region snippets, and TraderPlus snippets; `pack.bat --traders`, `--expansion` and `--traderplus`
- Balance and performance report (`tools/balance_report.py`, `docs/BALANCE_REPORT.md`)
- A models zip on each release (sign and building OBJ files and textures)

### Changed
- Farm utes and trucks on the back roads and farm tracks; no land is more than 1.5 km from a vehicle spawn (was 2.6 km)
- No vehicle spawns inside a safe zone

## 0.3.0 - 2026-11-25

### Added
- North Island Main Trunk and Main North Line railways with 18 stations
- 45 hamlets joined by gravel back roads
- Interislander ferry terminals at Wellington and Picton, 16 boat ramps, surf clubs, holiday parks, baches and DOC huts
- Landmarks: Milford Sound, Aoraki / Mount Cook Village, Chateau Tongariro, Waitomo Caves, Huka Falls, Church of the Good Shepherd, Moeraki Boulders and Stirling Point
- Town detail (street lamps, bus stops, back fences, garden trees) and abandoned cars
- New Zealand starting gear, server messages and rules, launch scripts, ban and whitelist files, BattlEye RCon config
- `pack.bat`: one-click packing, signing and a ready server folder, with easy / normal / hard difficulty
- Logo, icons, loading screens and map picture; printable player map
- Map checks on GitHub, a P: drive model checker, a Terrain Builder walkthrough and plans for custom models

### Fixed
- The building spawner files are no longer loaded by default; the buildings are already in the world, so they appeared twice

## 0.2.0 - 2026-11-25

### Added
- Terrain grown to 25.6 km, with raised volcanic cones for Ruapehu, Ngauruhoe, Tongariro and Taranaki
- Taranaki and Waikato towns, Linton Army Camp, Hamilton as a major city, Eltham
- Industrial plants (Fonterra Whareroa and Eltham, Marsden Point, Huntly, Glenbrook, Kinleith, Tiwai Point), Devonport Naval Base, Cape Reinga lighthouse
- World detail: bridges, lake water planes, power lines, guardrails, farm fences, hedgerows and rocks
- Loot positions and tiers, New Zealand loot changes, animal herds and weather

### Changed
- New Zealand back in its true north-up shape, stretched 1.4 times east-west

## 0.1.0 - 2026-11-24

### Added
- 20 km terrain from real New Zealand elevation data, surface mask and satellite texture
- 42 towns and bases with bilingual labels
- Lakes and rivers, state highways and town streets, points of interest and forests
- World config, mod files, server mission generator and Windows build scripts
