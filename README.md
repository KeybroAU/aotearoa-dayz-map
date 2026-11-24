# Aotearoa (DayZ terrain)

A 20 km DayZ terrain based on New Zealand, for a new server. The coastline and the big landforms come from real elevation data, so you can pick out the Southern Alps, Fiordland, Canterbury Plains, Banks Peninsula, the central volcanic plateau, Taranaki and Stewart Island. Small detail is generated.

![Shaded relief](preview/relief_2048.png)

## Scale

| | |
|---|---|
| Terrain size | 20480 m x 20480 m |
| Heightmap grid | 4096 x 4096, 5 m cells |
| Real to game | 1 game metre is about 65 real metres |
| Land area | about 66 km2 (16% of the square) |
| Highest point | 475 m (Southern Alps) |
| Steepest slope | 40 degrees |
| Orientation | Turned 16 degrees clockwise so the country fits the diagonal |

New Zealand is about 1500 km long, so a 20 km map shrinks it a lot, and real heights would make every range a cliff. Heights are scaled down far more than distances, then capped at 40 degrees so players can still climb the hills.

## Files

| Path | What it is |
|---|---|
| `source/heightmap_4096.png` | 16-bit heightmap. Black is `png_black_m` and white is `png_white_m` in `heightmap.json`. |
| `source/heightmap.json` | Height range, grid, projection and source details |
| `source/mask_4096.png` | Surface mask. Its colours match `layers.cfg`. |
| `source/layers.cfg` | Surface layers and mask colours for Terrain Builder |
| `source/mapLegend.png` | Legend picture used by `layers.cfg` |
| `preview/` | Shaded relief, surface mask and slope (white is 50 degrees) |
| `tools/generate_terrain.py` | Builds everything above from real elevation data |
| `tools/png_to_asc.py` | Turns the PNG heightmap into the `.asc` file Terrain Builder imports |

The `.asc` heightmap is about 115 MB, so it is not committed. To make it:

```bash
pip install -r tools/requirements.txt
python tools/png_to_asc.py
```

That writes `source/heightmap_4096.asc`.

## Surfaces

| Layer | Colour | Where |
|---|---|---|
| beach | 255,230,140 | Low coast, and everything under the sea |
| pasture | 120,190,60 | Default lowland grass |
| farmland | 200,200,90 | Flat low ground, e.g. Canterbury and Waikato |
| bush | 20,90,30 | Steep hills and the wet West Coast |
| pine | 60,110,70 | Patches of plantation forest in the North Island hills |
| tussock | 190,160,80 | South Island high country east of the main divide |
| scree | 150,150,150 | High alpine ground |
| rock | 90,80,75 | Anything steeper than 36 degrees |
| volcanic | 120,60,50 | Central plateau around Ruapehu and Tongariro |

The material paths in `layers.cfg` point at vanilla `DZ\surfaces\data\terrain` files. Check that each one exists on your P: drive before you generate layers, and swap any that don't. Terrain Builder allows only a few surfaces per tile, so if layer generation reports too many surfaces on a tile, merge similar layers (for example, farmland into pasture).

## Terrain Builder setup

These steps assume DayZ Tools is installed and the P: drive is mounted with game data extracted.

1. Copy this folder to `P:\maps\aotearoa`, then run `tools/png_to_asc.py` to make `source\heightmap_4096.asc`.
2. In Terrain Builder, create a new project at `P:\maps\aotearoa\source`.
3. Open **Mapframe Properties** and set:
   - Location: easting **200000**, northing **0**
   - Samplers: grid size **4096 x 4096**, cell size **5 m**, terrain size **20480 m**
   - Satellite and surface mask image size: **20480 x 20480** (1 m per pixel)
   - Tile size **512**, desired overlap **16**
   - Output root: `P:\maps\aotearoa\data\layers`
4. **Import Terrain** and choose `source\heightmap_4096.asc`.
5. Make the mask at full size: run `python tools/generate_terrain.py --mask-size 20480`. This downloads the elevation tiles again (about 50 MB) and takes a few minutes. Import `source\mask_20480.png` as the surface mask.
6. Point the layers config at `source\layers.cfg`.
7. You still need a satellite image. Until there's a real one, a full-size copy of the mask works as a placeholder. Import it as the satellite image.
8. **Generate Layers**, then **Export WRP** to `P:\maps\aotearoa\world\aotearoa.wrp`.

Still to do: the world `config.cpp`, roads, towns, forests and other objects, a satellite texture, and the server mission files (`mapgrouppos.xml`, player spawns and economy files).

## Regenerating

`tools/generate_terrain.py` downloads [Terrarium elevation tiles](https://registry.opendata.aws/terrain-tiles/) from AWS Open Data (a mix of SRTM, GEBCO, LINZ and other sources) into `~/.cache/aotearoa-tiles`. The tuning values are at the top of the script:

- `ROTATION_DEG`: turn the country
- `MAX_HEIGHT`: height of the main ranges
- `MAX_SLOPE_DEG`: slope cap
- `MIDDLE_WEIGHT`: how much real valley and ridge detail is kept
- `COAST_RAMP_M`: how gently the land rises from the sea
- `SEED`: the generated detail

Run it with no arguments to rebuild the 4096 mask and the previews. Add `--mask-size 20480` for the full-size mask, or `--asc` to also write the `.asc` heightmap.
