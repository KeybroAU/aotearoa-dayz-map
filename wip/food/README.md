# Food and drink: work in progress

A test copy of every New Zealand food and drink item, for trying real brand label artwork without touching the live items. `python tools/wip_food.py` builds it; `python tools/pack_mod.py --wip` packs it as `dist/@AotearoaFoodWIP`. Load that after `@Aotearoa` and spawn the `AotearoaWIP_*` classes with an admin tool. They aren't in the loot, and nothing here goes into a release.

`templates/<key>.png` is a blank label for each item at twice the size it is used: paint over it (the faint picture is the current artwork, the blue dashes are the safe area for text, and red hatching marks parts that are crimped, rimmed or covered) and save the result in `labels/`.

To try a label, put an image in `labels/` named after the item's key, such as `labels/lp.png` or `labels/marmite.jpg`, and run the script again. The image is cropped to the shape below and fitted onto every front of the pack, over the generated artwork. A flat, straight-on scan or photo of the label works best. `preview.png` shows the live texture next to the WIP one for every item that has a label.

Use artwork you have the right to use. `labels/`, `textures/` and `preview.png` are ignored by git, so brand images stay out of the public repo and the source zip. A finished label moves into the live mod by copying `textures/<key>.png` over `data/food/<key>.png`, but only if the artwork may be published on the Workshop.

Tins whose UV layout isn't published (the Whittaker's bars and the honey jar) repeat the label over the whole texture, as the live ones do.

| Item | Key (label file name) | WIP class | Label shape in pixels |
|---|---|---|---|
| L&P | `lp` | `AotearoaWIP_SodaCan_LP` | 313 x 492 (313:492) |
| Fresh Up Apple | `freshup` | `AotearoaWIP_SodaCan_FreshUp` | 313 x 492 (313:492) |
| Foxton Fizz Creaming Soda | `foxton_cream` | `AotearoaWIP_SodaCan_FoxtonCream` | 313 x 492 (313:492) |
| Foxton Fizz Raspberry | `foxton_rasp` | `AotearoaWIP_SodaCan_FoxtonRaspberry` | 313 x 492 (313:492) |
| Lift Plus | `liftplus` | `AotearoaWIP_SodaCan_LiftPlus` | 313 x 492 (313:492) |
| Bluebird Ready Salted | `bluebird_salted` | `AotearoaWIP_Chips_BluebirdReadySalted` | 1024 x 1024 (1:1) |
| Bluebird Salt & Vinegar | `bluebird_vinegar` | `AotearoaWIP_Chips_BluebirdSaltVinegar` | 1024 x 1024 (1:1) |
| Bluebird Chicken | `bluebird_chicken` | `AotearoaWIP_Chips_BluebirdChicken` | 1024 x 1024 (1:1) |
| Munchos Tomato | `munchos` | `AotearoaWIP_Chips_MunchosTomato` | 1024 x 1024 (1:1) |
| Griffin's Toffee Pops | `toffeepops` | `AotearoaWIP_Biscuits_ToffeePops` | 1024 x 1024 (1:1) |
| Griffin's Shrewsburys | `shrewsburys` | `AotearoaWIP_Biscuits_Shrewsburys` | 1024 x 1024 (1:1) |
| Griffin's Chocolate Thins | `chocthins` | `AotearoaWIP_Biscuits_ChocolateThins` | 1024 x 1024 (1:1) |
| Pascall Pineapple Lumps | `pineapplelumps` | `AotearoaWIP_Lollies_PineappleLumps` | 1024 x 1024 (1:1) |
| Whittaker's Creamy Milk | `whittakers_milk` | `AotearoaWIP_Whittakers_CreamyMilk` | 1024 x 256 (4:1) |
| Whittaker's Dark Ghana | `whittakers_dark` | `AotearoaWIP_Whittakers_DarkGhana` | 1024 x 256 (4:1) |
| Whittaker's Peanut Slab | `whittakers_peanut` | `AotearoaWIP_Whittakers_PeanutSlab` | 1024 x 256 (4:1) |
| Rice Risotto | `risotto` | `AotearoaWIP_RiceRisotto` | 512 x 461 (512:461) |
| Anchor Milk Powder | `anchor_milk` | `AotearoaWIP_Anchor_MilkPowder` | 1024 x 266 (512:133) |
| Airborne Mānuka Honey | `airborne_honey` | `AotearoaWIP_Airborne_Honey` | 512 x 256 (2:1) |
| Sanitarium Weet-Bix | `weetbix` | `AotearoaWIP_WeetBix` | 502 x 707 (502:707) |
| Wattie's Baked Beans | `watties_beans` | `AotearoaWIP_Watties_BakedBeans` | 369 x 412 (369:412) |
| Wattie's Spaghetti | `watties_spaghetti` | `AotearoaWIP_Watties_Spaghetti` | 369 x 412 (369:412) |
| Wattie's Peach Slices | `watties_peaches` | `AotearoaWIP_Watties_Peaches` | 369 x 412 (369:412) |
| Palm Corned Beef | `palm_cornedbeef` | `AotearoaWIP_Palm_CornedBeef` | 341 x 104 (341:104) |
| Marmite | `marmite` | `AotearoaWIP_Marmite` | 512 x 512 (1:1) |
| Hellers Bacon | `hellers_bacon` | `AotearoaWIP_Hellers_Bacon` | 369 x 412 (369:412) |
| Tux Dog Food | `tux_dogfood` | `AotearoaWIP_Tux_DogFood` | 341 x 104 (341:104) |
| Jellimeat | `jellimeat` | `AotearoaWIP_Jellimeat` | 341 x 104 (341:104) |
| Sealord Tuna | `sealord_tuna` | `AotearoaWIP_Sealord_Tuna` | 614 x 420 (307:210) |
| Pump Water Bottle | `pump_water` | `AotearoaWIP_Pump_Water` | 170 x 123 (170:123) |
| Pams Sardines | `pams_sardines` | `AotearoaWIP_Pams_Sardines` | 341 x 215 (341:215) |
