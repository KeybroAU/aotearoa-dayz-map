# Changelog

Versions follow `MAJOR.MINOR.PATCH`. `VERSION` holds the current one, and `mod/mod.cpp` must match it (the map checks enforce this). To release, add a section here, bump both files, and push a tag `vX.Y.Z`; GitHub builds the release.

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
