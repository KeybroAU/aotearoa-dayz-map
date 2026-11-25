# Custom models plan

Vanilla DayZ is Eastern European, so a few New Zealand things have no model. This is a brief for a 3D modeller. It lists what to build, in priority order, with sizes, the parts each model needs, and where the map already uses a stand-in so the new model drops straight in.

Sizes are in game metres. The map is about 60 times smaller than New Zealand, but buildings are kept at real size so players fit in them. Only very tall landmarks are scaled down.

## Priority list

| # | Model | Why | Stand-in now | Size (L x W x H) |
|---|---|---|---|---|
| 1 | Lake water plane | Lakes have no water surface without it | `aotearoa_water_50` (missing) | 50 x 50 x 0 |
| 2 | NZ road signs (set) | Instantly reads as New Zealand | none | 1 to 3 m tall |
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

**Folders:** put each model in `P:\maps\aotearoa\structures\<name>\`. It is packed into the same PBO; `pack.bat` picks it up because it's under the map folder. Add `structures` to `PACKED` in `tools/pack_mod.py`.

---

## 1. Lake water plane

- A flat 50 x 50 m square, origin at the **centre of the top surface**. The map places tiles at the lake's water level using that origin.
- One resolution LOD with a water material (copy the vanilla pond or sea water rvmat), with no Geometry or Roadway, so players walk through it to the lake bed.
- Edges can be transparent or slightly feathered; tiles overlap the shore by half a tile.
- **Engine limit:** DayZ only lets players swim at sea level, so inland lakes are wading depth (the lake beds are dug only a few metres deep). Look at how community maps such as Deer Isle or Namalsk do drinkable ponds before deciding whether lakes should be drinkable.
- **Swap in:** set `"water"` in `OBJECTS` in `tools/details.py` to the new model name, then regenerate or edit `source/objects/lakes_tb.txt`.

## 2. NZ road signs

A small set of simple models, each a post with a sign face. Each needs Geometry and Fire Geometry, but no Roadway.

| Sign | Look |
|---|---|
| State Highway shield | Red shield, white border, white number. One model with a texture per number (1, 2, 3, 4, 5, 6, 7, 8, 27, 45, 57, 73, 83, 94) or a number decal. |
| Place name | Green rectangle, white text: town name, plus the Māori name below where there is one. One texture per town, or a generic blank. |
| Give Way | White inverted triangle with a red border |
| 100 km/h and 50 km/h | White circle with a red ring |
| Rural fire danger | Half-dial "Fire Danger Today", needle on high |
| One Lane Bridge | Red-and-white rectangular sign |

- **Placement (to add once they exist):** shields every 2 km on highways, place names where a highway enters a town (the town radius), Give Way at each street-to-highway join, One Lane Bridge at each bridge. `source/roads.json` has everything needed. A new function in `tools/details.py`, like `power_lines`, would write `roadsigns_tb.txt`.

## 3. Kiwi bach

- A small 1960s holiday home: weatherboard or fibrolite walls, a low-pitched corrugated iron roof, a deck across the front with a ranch slider (sliding door), and a separate long-drop toilet out the back as an optional second model.
- 2 rooms plus a bathroom, 2 doors.
- Colours: faded pastel paint (mint, cream, sky blue), rusty roof.
- **Swap in:** in `tools/pois.py`, `place_baches` picks from `towns_mod.HOUSES`; use `Land_Aotearoa_Bach` there, and also in the holiday parks.

## 4. Woolshed

- A raised timber shed on piles, corrugated iron roof and walls, a long low gable, a covered sheep yard against one side, and a loading ramp.
- Inside: a slatted shearing board, holding pens and a wool press (props can be simple boxes).
- 2 to 3 big doors.
- **Swap in:** in `tools/pois.py`, `place_farms` chooses between barn and cowshed; add the woolshed as a third choice, more common in the South Island.

## 5. Corner dairy

- A small single-storey shop with a flat roof and a parapet, a big front window, a striped awning, an ice-cream sign board out front, and a flat behind.
- Inside: shelves and a counter. This is a good food and drink loot spot.
- **Swap in:** add to `SPECIALS` for `town` and `village` in `tools/towns.py`.

## 6. DOC hut

- A tramping hut: corrugated iron, painted orange or green, with a small veranda, a water tank on a stand, and an intentions book box by the door.
- Inside: bunks for 6 and a wood stove (the chimney gives off smoke if you add a particle effect).
- **Swap in:** in `tools/pois.py`, `place_huts` uses `HOUSES[0]`; change it to the hut.

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
