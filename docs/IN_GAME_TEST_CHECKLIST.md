# In-game test checklist

Work through this the first time you load Aotearoa in DayZ, and again after a big change. Tick each box, and for anything that fails, note what you saw and where (grid square from the map, or the town). A screenshot helps most.

## Before you start

- [ ] `pack.bat --key aotearoa` finished without errors and wrote `dist\@Aotearoa`, `dist\@AotearoaMap` and `dist\server`
- [ ] The server folder from `dist\server` is copied into your DayZ Server folder, and the server starts with `start_server.bat`
- [ ] The client starts with `-mod=@Aotearoa;@AotearoaMap` (or through the DayZ launcher with both mods loaded) and joins
- [ ] You have an admin tool to spawn items and teleport (VPP Admin Tools or Community Online Tools), or you're using `DayZDiag_x64.exe`, whose debug menu spawns items by class name

Keep the logs: the server's `profiles\` folder and the client's `%localappdata%\DayZ\` hold `script_*.log` and `*.RPT`. Search them for `Aotearoa`, `error` and `Cannot open file` after each session.

## Start-up

- [ ] No script errors on start-up (a script error shows a message box and stops the game)
- [ ] The server browser and the loading screen show Aotearoa with its picture
- [ ] You spawn on a New Zealand coast with the starting gear

## Terrain and world

- [ ] The ground looks right: satellite colours, grass, farmland, beaches, rock on the mountains, snow on the Alps
- [ ] Footsteps and vehicle sounds match the ground (grass, gravel, asphalt, sand)
- [ ] The sea level is right, with no floating or sunken coastline. Lakes sit at their own levels.
- [ ] Rivers run in their channels
- [ ] The roads join up and the bridges line up with them; drive a state highway for a few kilometres
- [ ] The railway and its stations are there (try the Main North Line out of Christchurch)
- [ ] Forests: native bush, pine plantations, no trees in the middle of roads or buildings
- [ ] The Southern Alps and Ruapehu can be climbed on foot (nothing steeper than about 40 degrees)

## Towns, signs and landmarks

- [ ] Towns have buildings you can enter, and loot spawns in them
- [ ] Town name signs stand at the edges of towns and show the right English and te reo Māori names (try Christchurch / Ōtautahi and Wellington / Te Whanganui-a-Tara)
- [ ] Road signs show their text, with no white, black or missing textures
- [ ] Landmarks: the Sky Tower and the Harbour Bridge in Auckland, the cathedral ruins in Christchurch, Parliament in Wellington, the Interislander wreck
- [ ] Military bases (Waiouru, Burnham, Linton, Ōhakea) have the extra barracks, tents and towers, military infected and tier 4 loot
- [ ] Baches, surf clubs, holiday parks and DOC huts are there and lootable

## Map screen and map item

- [ ] The map screen shows "Designed by Keybro" and Keybrogaming.com in the bottom-right corner, faint but readable
- [ ] Town, river, peak and sea names on the map screen sit in the right places and don't overlap badly
- [ ] The `AotearoaMap` item spawns in loot, shows its cover, and opens the map
- [ ] Markers can be placed on the map and stay after closing it

## Loot

- [ ] Hunting rifles and shotguns turn up on farms; NZDF Steyr AUGs, M4s and FALs only at the military bases
- [ ] Civilian towns don't have military loot in every house (check Palmerston North, Queenstown and Rakaia)
- [ ] Gumboots, raincoats, wool jumpers and beanies turn up in houses
- [ ] Food shelves hold the New Zealand food and drink, and no vanilla soda cans, Chips, Crackers, Zagorky bars, Crunchin cereal or the replaced tins (search about ten shops and houses)

## New Zealand food and drink

Spawn each one with your admin tool by its class name, or find it in loot. For each item check:

- [ ] Its name and description show in the inventory
- [ ] Its label shows on the model in the inventory preview, in your hands and dropped on the ground, with no white, black or stretched texture
- [ ] You can eat or drink it
- [ ] Tins: open it (knife, can opener or by hand, as in vanilla). The opened tin keeps the same label, and you can eat from it.

| Item | Class name | Built on | Opens |
|---|---|---|---|
| L&P | `Aotearoa_SodaCan_LP` | SodaCan_Cola |  |
| Fresh Up Apple | `Aotearoa_SodaCan_FreshUp` | SodaCan_Fronta |  |
| Foxton Fizz Creaming Soda | `Aotearoa_SodaCan_FoxtonCream` | SodaCan_Spite |  |
| Foxton Fizz Raspberry | `Aotearoa_SodaCan_FoxtonRaspberry` | SodaCan_Pipsi |  |
| Lift Plus | `Aotearoa_SodaCan_LiftPlus` | SodaCan_Kvass |  |
| Bluebird Ready Salted | `Aotearoa_Chips_BluebirdReadySalted` | Chips |  |
| Bluebird Salt & Vinegar | `Aotearoa_Chips_BluebirdSaltVinegar` | Chips |  |
| Bluebird Chicken | `Aotearoa_Chips_BluebirdChicken` | Chips |  |
| Munchos Tomato | `Aotearoa_Chips_MunchosTomato` | Chips |  |
| Griffin's Toffee Pops | `Aotearoa_Biscuits_ToffeePops` | Crackers |  |
| Griffin's Shrewsburys | `Aotearoa_Biscuits_Shrewsburys` | Crackers |  |
| Griffin's Chocolate Thins | `Aotearoa_Biscuits_ChocolateThins` | Crackers |  |
| Pascall Pineapple Lumps | `Aotearoa_Lollies_PineappleLumps` | Crackers |  |
| Whittaker's Creamy Milk | `Aotearoa_Whittakers_CreamyMilk` | Zagorky |  |
| Whittaker's Dark Ghana | `Aotearoa_Whittakers_DarkGhana` | ZagorkyChocolate |  |
| Whittaker's Peanut Slab | `Aotearoa_Whittakers_PeanutSlab` | ZagorkyPeanuts |  |
| Sanitarium Weet-Bix | `Aotearoa_WeetBix` | BoxCerealCrunchin |  |
| Rice Risotto | `Aotearoa_RiceRisotto` | Rice |  |
| Anchor Milk Powder | `Aotearoa_Anchor_MilkPowder` | PowderedMilk |  |
| Airborne Mānuka Honey | `Aotearoa_Airborne_Honey` | Honey |  |
| Pump Water Bottle | `Aotearoa_Pump_Water` | WaterBottle |  |
| Wattie's Baked Beans | `Aotearoa_Watties_BakedBeans` | BakedBeansCan | yes |
| Wattie's Spaghetti | `Aotearoa_Watties_Spaghetti` | SpaghettiCan | yes |
| Wattie's Peach Slices | `Aotearoa_Watties_Peaches` | PeachesCan | yes |
| Palm Corned Beef | `Aotearoa_Palm_CornedBeef` | PorkCan | yes |
| Tux Dog Food | `Aotearoa_Tux_DogFood` | DogFoodCan | yes |
| Jellimeat | `Aotearoa_Jellimeat` | CatFoodCan | yes |
| Hellers Bacon | `Aotearoa_Hellers_Bacon` | TacticalBaconCan | yes |
| Marmite | `Aotearoa_Marmite` | BrisketSpread | yes |
| Sealord Tuna | `Aotearoa_Sealord_Tuna` | TunaCan | yes |
| Pams Sardines | `Aotearoa_Pams_Sardines` | SardinesCan | yes |

Things to look at closely, because their texture layouts are guessed or approximate:

- [ ] **Whittaker's bars:** the wrapper is a repeating pattern because the vanilla bar's layout isn't published. Check the brand reads the right way up on the bar.
- [ ] **Sealord Tuna:** the label is printed on the lid, with the ring pull at one end. Check the ring sits over the model's pull tab.
- [ ] **Pams Sardines, Palm Corned Beef and Marmite:** the label should wrap the side of the tin, and the lid should look like plain metal.
- [ ] **Weet-Bix:** the front of the box should show the bowl and the wordmark.
- [ ] **Rice Risotto:** vanilla rice doesn't retexture its bag, so check the packet shows the green band and the "Rice Risotto" label rather than the plain vanilla bag or a missing texture.
- [ ] **Anchor Milk Powder, Airborne Honey and Pump Water Bottle:** these also use the model's `zbytek` selection. The milk label runs down the bag, the honey jar repeats its label all over (its layout isn't published), and the Pump label should wrap the bottle with the blue cap on top. Also fill, drink from and empty the bottle to check it still works as a water bottle.

If a texture is sideways, mirrored or in the wrong place, take a screenshot. For a fix, convert the vanilla texture to PNG with DayZ Tools' ImageToPAA (for example `P:\DZ\gear\food\data\zagorky_milk_ca.paa`) and send it; the labels can then be lined up exactly with the vanilla layout.

## Weather, seasons and wildlife

- [ ] The weather changes: westerly rain, clear spells and wind
- [ ] The date and season match the server date (southern seasons: January is summer)
- [ ] It's colder up in the Alps than on the coast
- [ ] Sheep and cattle on the farms, red deer in the back country, goats on steep ground, wild pigs. No wolves or bears.

## Vehicles, infected and events

- [ ] Vehicles spawn (farm utes in the countryside) and can be repaired and driven
- [ ] Infected spawn in towns and at the bases, and walk around buildings properly (no running through walls)
- [ ] Helicopter crashes and other events turn up

## Performance

- [ ] Client FPS is acceptable in the biggest towns (Auckland, Christchurch, Wellington) and in thick forest
- [ ] The server FPS stays steady with a few players on (check the server console)
- [ ] No long freezes when driving fast along a highway

## Report

For each failure, write down:

1. What you expected and what you saw
2. Where: town or grid square, and which way you were facing
3. A screenshot, plus any matching lines from `script_*.log` or the `.RPT`
