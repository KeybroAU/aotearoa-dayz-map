// Map of Aotearoa: a paper map item for the Aotearoa terrain, packed as its own mod (@AotearoaMap,
// addons/aotearoa_map.pbo, prefix aotearoa_map). Built by tools/pack_mod.py; textures from
// tools/build_map_item.py.

class CfgPatches
{
	class Aotearoa_Map
	{
		units[] = {"AotearoaMap"};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Gear_Navigation"};
	};
};

class CfgMods
{
	class Aotearoa_Map
	{
		dir = "AotearoaMap";
		name = "Map of Aotearoa";
		author = "KeybroAU";
		type = "mod";
		dependencies[] = {"World"};
		class defs
		{
			class worldScriptModule
			{
				value = "";
				files[] = {"aotearoa_map/scripts/4_World"};
			};
		};
	};
};

class CfgVehicles
{
	class ChernarusMap;
	class AotearoaMap: ChernarusMap
	{
		scope = 2;
		displayName = "Map of Aotearoa";
		descriptionShort = "A folded road map of Aotearoa New Zealand with state highways, the main trunk railway, a 1 km grid, and every town and landmark listed on the back.";
		// Read by AotearoaMap.c instead of the world's mapTexture* values, so this map looks the same on any terrain.
		mapTextureClosed = "aotearoa_map\data\aotearoa_map_closed_co.paa";
		mapTextureOpened = "aotearoa_map\data\aotearoa_map_opened_co.paa";
		mapTextureLegend = "aotearoa_map\data\aotearoa_map_legend_co.paa";
		hiddenSelectionsTextures[] = {"aotearoa_map\data\aotearoa_map_closed_co.paa", "aotearoa_map\data\aotearoa_map_opened_co.paa", "aotearoa_map\data\aotearoa_map_legend_co.paa"};
	};
};
