# Custom models plan

Vanilla DayZ is Eastern European, so a few New Zealand things have no model. This is a brief for a 3D modeller. It lists what to build, in priority order, with sizes, the parts each model needs, and where the map already uses a stand-in so the new model drops straight in.

Sizes are in game metres. The map is about 60 times smaller than New Zealand, but buildings are kept at real size so players fit in them. Only very tall landmarks are scaled down.

## Priority list

| # | Model | Why | Stand-in now | Size (L x W x H) |
|---|---|---|---|---|
| 1 | Lake water plane | Lakes have no water surface without it | `aotearoa_water_50` (missing) | 50 x 50 x 0 |
| 2 | NZ road signs (set) | Instantly reads as New Zealand | placed, textures done; 2 simple models to make | 1 to 3 m tall |
| 3 | Kiwi bach | 14 bach clusters, holiday parks | `Land_House_1W0x` | 9 x 7 x 4.5 |
| 4 | Woolshed | 70 farms | `Land_Barn_Metal_Big`, `Land_Farm_CowshedA` | 30 x 14 x 7 |
| 5 | Corner dairy (shop) | Every town | `Land_City_Store` in some slots | 12 x 9 x 4.5 |
| 6 | DOC hut | 15 high-country huts | `Land_House_1W01` | 8 x 6 x 4 |
| 7 | Hobbit hole | Hobbiton | ring of `Land_House_1W0x` | 8 x 8 x 4 (mound) |
| 8 | Interislander ferry | Wellington terminal | none | 100 x 18 x 22 |
| 9 | Sky Tower | Auckland skyline | none | 8 x 8 x 120 (scaled) |
| 10 | Beehive | Wellington | none | 30 x 30 x 25 |
| 11 | Chateau Tongariro | Landmark | `Land_Tenement_Big` | 50 x 18 x 14 |

Items 1 and 2 matter most. Items 3 to 6 replace stand-ins used hundreds of times, so they change the feel of the whole map. Items 7 to 11 are single landmarks.

---

## What every building needs

Follow the DayZ Samples on the P: drive (`P:\DZ\samples\` or the DayZ Tools "Samples" download) for the exact setup.

**LODs in Object Builder:**
- Resolution LODs 0, 1, 2, 4 (or similar), each about half the triangles of the last. Target 3,000 to 15,000 triangles for LOD 0 on a house.
- **Geometry:** closed convex components, with mass set (houses usually 10,000+) and the `class=house` property.
- **Fire Geometry:** so bullets hit walls. It can match Geometry, plus thin walls and floors.
- **View Geometry:** so AI and infected can't see through walls.
- **Roadway:** every floor, stair and roof players walk on.
- **Memory:** door axes and positions (`door1_axis`, `door1_trigger` and so on), light points, and the bounding centre.
- **Paths:** AI walk paths through doors, for infected.
- **Land Contact:** points where the model touches the ground, so Terrain Builder seats it.

**Textures:** `_co` (colour), `_nohq` (normal), `_smdi` (specular) and `_as` (ambient shadow) `.paa` files at 1024 or 2048, each with an `.rvmat`. Reuse vanilla rvmats and textures where you can (weatherboard, corrugated iron) to save memory.

**Config** (`config.cpp` in the model's folder):
- `class Land_Aotearoa_<Name>: HouseNoDestruct` (or `House` for buildings with doors), with `model = "\maps\aotearoa\structures\<name>\<name>.p3d";`
- doors: `class AnimationSources` and `class Doors` entries copied from a vanilla house with the same door count.
- loot: after the model is in, add loot points with the DayZ Tools economy editor, or copy a similar vanilla building's entry in `mapgroupproto.xml` and move the points.

**Folders:** put each model in `P:\maps\aotearoa\structures\<name>\`. It is packed into the same PBO; `pack.bat` already packs `structures\`.

---

## 1. Lake water plane

- A flat 50 x 50 m square, origin at the **centre of the top surface**. The map places tiles at the lake's water level using that origin.
- One resolution LOD with a water material (copy the vanilla pond or sea water rvmat), with no Geometry or Roadway, so players walk through it to the lake bed.
- Edges can be transparent or slightly feathered; tiles overlap the shore by half a tile.
- **Engine limit:** DayZ only lets players swim at sea level, so inland lakes are wading depth (the lake beds are dug only a few metres deep). Look at how community maps such as Deer Isle or Namalsk do drinkable ponds before deciding whether lakes should be drinkable.
- **Swap in:** set `"water"` in `OBJECTS` in `tools/details.py` to the new model name, then regenerate or edit `source/objects/lakes_tb.txt`.

## 2. NZ road signs

**Done apart from two simple models.** `tools/signs.py`, which `build_mission.py` runs, already draws every texture, writes the config classes and places the signs:

| Sign | Look | Where | Count |
|---|---|---|---|
| Place name | Green board, white town name, Māori name below | Every highway, gravel road and track into a named town, 20 m outside it | 136 over all 51 towns |
| State Highway shield | Red shield, white number | Every 2 km along each highway, facing alternate ways, and just past each town for drivers leaving | 149 |
| 50 km/h | White circle, red ring | Town edge, for drivers coming in | 117 |
| 100 km/h | White circle, red ring | Town edge, for drivers leaving | 116 |
| Give Way | White triangle, red border | Every side road where it meets a highway | 235 |
| One Lane Bridge | Yellow diamond | Both ends of every back-road bridge and of the bridges on rural South Island highways (SH6, 7, 8, 63, 65, 73, 83, 94) | 37 |

Every sign stands on the left verge (New Zealand drives on the left), faces the traffic it is for, and keeps clear of roads and buildings. `preview/signs_sheet.png` shows every face.

Files:
- `data/signs/sign_<Town>.png`: the place-name textures (1024 x 1024, face in the top half, grey back below).
- `data/signs/post_<Sign>.png`: the other textures (512 x 1024 with alpha, face in the top half, the grey back with the same outline below).
- `config/signs.hpp`: classes `Land_Aotearoa_Sign_<Town>` and `Land_Aotearoa_SignPost_<Sign>`, each setting `hiddenSelectionsTextures`.
- `mission/dayzOffline.aotearoa/aotearoa/signs_spawner.json` and `roadsigns_spawner.json`: the positions.

The signs are loaded with the object spawner, not placed in Terrain Builder, because a world object can't change its texture per copy. `pack.bat` converts the textures (`_co.paa` for the place names, `_ca.paa` with alpha for the rest). It adds each spawner to `cfggameplay.json` once its model exists, and until then prints a note and leaves those signs out.

**Making the two models.** `tools/make_models.py` writes the OBJ files.

| Model | OBJ | Save as |
|---|---|---|
| Place-name board, 2.4 x 1.2 m on two posts | `docs/models/sign_town.obj` | `P:\maps\aotearoa\structures\sign_town\sign_town.p3d` |
| 1 m square cut-out sign on one post | `docs/models/sign_post.obj` | `P:\maps\aotearoa\structures\sign_post\sign_post.p3d` |

For each one:

1. In Object Builder, use **File → Import → Wavefront OBJ** to import the OBJ into LOD 0 (resolution). Units are metres and y is up.
2. Select the faces of the `camo` group and name the selection **`camo`**. For the place-name board, the `back` and `posts` faces use the same texture.
3. Give the faces any texture of the right kind. For the board use `maps\aotearoa\data\signs\sign_Wellington_co.paa`. For the post sign use `maps\aotearoa\data\signs\post_SH1_ca.paa`, with an alpha-tested material (copy a vanilla fence or foliage rvmat) so the shield, circle, triangle and diamond outlines are cut out. The config swaps the texture per sign, and the UVs are already set.
4. Import `docs/models/<name>_geometry.obj` into a new **Geometry** LOD. Each group is one convex component, so name them `Component01`, `Component02` and so on. Give the LOD a mass (about 40 kg).
5. Copy the Geometry LOD to a **Fire Geometry** LOD.
6. Save to the path in the table.
7. Check the facing. With yaw 0 the face should look north, which is +z in Object Builder's top view. If a test sign shows its back to the traffic, rotate the model 180°. If the text reads backwards, mirror the face UVs. No other file needs changing.

## 3. Kiwi bach

- A small 1960s holiday home: weatherboard or fibrolite walls, a low-pitched corrugated iron roof, a deck across the front with a ranch slider (sliding door), and a separate long-drop toilet out the back as an optional second model.
- 2 rooms plus a bathroom, 2 doors.
- Colours: faded pastel paint (mint, cream, sky blue), rusty roof.
- **Swap in:** in `tools/pois.py`, `place_baches` picks from `towns_mod.HOUSES`; use `Land_Aotearoa_Bach` there, and also in the holiday parks.
- **Starting model:** `docs/models/bach.obj` (with `_geometry.obj` and `_roadway.obj`) is a ready blockout with open doorways, at the size above. Import it as in [Building models from the OBJ files](#building-models-from-the-obj-files), then add detail. Class: `Land_Aotearoa_Bach`. Render: `preview/models_bach.png`.

## 4. Woolshed

- A raised timber shed on piles, corrugated iron roof and walls, a long low gable, a covered sheep yard against one side, and a loading ramp.
- Inside: a slatted shearing board, holding pens and a wool press (props can be simple boxes).
- 2 to 3 big doors.
- **Swap in:** in `tools/pois.py`, `place_farms` chooses between barn and cowshed; add the woolshed as a third choice, more common in the South Island.
- **Starting model:** `docs/models/woolshed.obj` (with `_geometry.obj` and `_roadway.obj`) is a ready blockout with open doorways, at the size above. Import it as in [Building models from the OBJ files](#building-models-from-the-obj-files), then add detail. Class: `Land_Aotearoa_Woolshed`. Render: `preview/models_woolshed.png`.

## 5. Corner dairy

- A small single-storey shop with a flat roof and a parapet, a big front window, a striped awning, an ice-cream sign board out front, and a flat behind.
- Inside: shelves and a counter. This is a good food and drink loot spot.
- **Swap in:** add to `SPECIALS` for `town` and `village` in `tools/towns.py`.
- **Starting model:** `docs/models/dairy.obj` (with `_geometry.obj` and `_roadway.obj`) is a ready blockout with open doorways, at the size above. Import it as in [Building models from the OBJ files](#building-models-from-the-obj-files), then add detail. Class: `Land_Aotearoa_Dairy`. Render: `preview/models_dairy.png`.

## 6. DOC hut

- A tramping hut: corrugated iron, painted orange or green, with a small veranda, a water tank on a stand, and an intentions book box by the door.
- Inside: bunks for 6 and a wood stove (the chimney gives off smoke if you add a particle effect).
- **Swap in:** in `tools/pois.py`, `place_huts` uses `HOUSES[0]`; change it to the hut.
- **Starting model:** `docs/models/doc_hut.obj` (with `_geometry.obj` and `_roadway.obj`) is a ready blockout with open doorways, at the size above. Import it as in [Building models from the OBJ files](#building-models-from-the-obj-files), then add detail. Class: `Land_Aotearoa_DocHut`. Render: `preview/models_doc_hut.png`.

## 7. Hobbit hole

- A grassy mound with a round green door in a round frame, a small round window each side, a picket fence and a gate, and a chimney poking out of the top.
- Inside: 2 or 3 small rooms dug into the hill.
- Two or three door colours as texture variants (green, yellow, red).
- **Swap in:** in the Hobbiton block in `tools/pois.py`, replace the cottages in the ring with the hobbit hole, keeping the pub as the Green Dragon (or model the Green Dragon too).

## 8. Interislander ferry

- A static, enterable ship, docked or listing slightly at the terminal pier:
  - a car deck with an open stern ramp;
  - one passenger deck with seating and a café;
  - a bridge.
- Scaled to about 100 m so it fits the terminal pad. Treat it as a building, not a vehicle: Geometry, Roadway on every deck, and stairs.
- Livery: white hull with a blue-and-red Interislander stripe.
- **Swap in:** add it to the ferry terminal layout in `tools/pois.py` (the `FERRIES` block), placed in the water off the pad. The pad's sea-side edge is the long side away from land.

## 9. Sky Tower

- A slender concrete shaft, three pods near the top with an observation deck and a mast.
- Scaled down to about 120 m so it doesn't dominate a 25.6 km map.
- Make the base and the observation deck enterable, joined by a lift shaft with ladders (DayZ has no working lifts). It's a sniper's dream, so keep loot modest.
- **Swap in:** add it to Auckland's specials in `tools/towns.py` so it sits near the centre, and give it a footprint in `FOOTPRINTS` in `tools/pois.py`.

## 10. Beehive

- A round, tiered, beehive-shaped building, 10 storeys scaled to about 25 m, on a plinth.
- Enterable ground and first floors at least.
- **Swap in:** add it to Wellington's specials in `tools/towns.py`.

## 11. Chateau Tongariro

- A grand 1920s hotel: long three-storey neo-Georgian front, a central portico, a red roof, and Ruapehu behind it.
- **Swap in:** in `LANDMARK_LAYOUTS["hotel"]` in `tools/pois.py`, replace `Land_Tenement_Big`.

---

## Building models from the OBJ files

`tools/make_models.py` writes blockout models for the bach, DOC hut, woolshed and corner dairy. Each is a complete, enterable building with open doorways (no doors, so it needs no `model.cfg` or memory points), textured with tiling textures it also generates in `data/models/`. They are simple, a few hundred triangles each. You can use them as they are to get New Zealand buildings in game, or as a correctly sized base to model over.

For each building:

1. **LOD 0 (resolution):** import `docs/models/<name>.obj`. The groups (walls, roof, floor, deck and so on) become named selections. Faces carry their texture from the `.mtl` file. If Object Builder drops the textures, set them from the group names: `maps\aotearoa\data\models\<texture>_co.paa`.
2. **Geometry:** import `<name>_geometry.obj` into a new Geometry LOD. Each group is one closed convex box. Name them `Component01` and up, set the mass (10,000 for a house), and add the named property `class` = `house`.
3. **Fire Geometry** and **View Geometry:** copies of the Geometry LOD.
4. **Roadway:** import `<name>_roadway.obj`, which holds the floors, deck, veranda, steps, bunks and ramp.
5. **Land Contact:** one point at each corner of the footprint at y = 0.
6. Save as `P:\maps\aotearoa\structures\<name>\<name>.p3d`. `config/structures.hpp` (included in `config.cpp`) already has its class, `Land_Aotearoa_<Name>`, and `pack.bat` packs `structures\` and converts the textures.
7. Add the model to your Terrain Builder template library. Then swap it in using the **Swap in** note under the building above, and regenerate.

Run `python tools/make_models.py` again after changing a model in the script. It rewrites the OBJ files, textures, config and renders.

## Cultural note

Leave Māori carvings, wharenui (meeting houses) and pou whenua out of the map unless you work with mana whenua (the local iwi) on them. They are taonga (treasures) with specific meaning to particular iwi, and a survival game is a sensitive setting for them. The bilingual place names are a respectful way to reflect te reo Māori already. If you do want marae or carvings, approach the relevant iwi first.

## Checklist for each model

- [ ] Model in `P:\maps\aotearoa\structures\<name>\`, with all LODs above
- [ ] Textures and rvmats, with no missing-texture warnings in Object Builder
- [ ] `config.cpp` with a `Land_Aotearoa_<Name>` class
- [ ] Opens and works in Buldozer (doors, walking on floors, can't see through walls)
- [ ] Added to a Terrain Builder library
- [ ] The stand-in name replaced in `tools/` as described above, and the map regenerated
- [ ] Loot points added in the economy editor
- [ ] `python tools/check_models.py models.txt` (with a fresh listing) reports it as found
