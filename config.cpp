// World config for the Aotearoa terrain. Pack P:\maps\aotearoa into aotearoa.pbo with the
// prefix maps\aotearoa (see README, "Packing the mod").

class CfgPatches
{
	class aotearoa
	{
		units[] = {"aotearoa"};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Structures", "DZ_Gear_Food", "DZ_Gear_Drinks", "DZ_Worlds_Chernarusplus_World"};
	};
};

// scripts/: the New Zealand climate (AotearoaData) and the hook that selects it for this world.
class CfgMods
{
	class aotearoa
	{
		dir = "Aotearoa";
		name = "Aotearoa";
		author = "KeybroAU";
		type = "mod";
		dependencies[] = {"World", "Mission"};
		class defs
		{
			class worldScriptModule
			{
				value = "";
				files[] = {"maps/aotearoa/scripts/4_World"};
			};
			class missionScriptModule
			{
				value = "";
				files[] = {"maps/aotearoa/scripts/5_Mission"};
			};
		};
	};
};

class CfgVehicles
{
	class HouseNoDestruct;
	#include "config\signs.hpp"
	#include "config\structures.hpp"
	#include "config\food.hpp"
};

class CfgWorldList
{
	class aotearoa {};
};

class CfgWorlds
{
	class CAWorld;
	class ChernarusPlus: CAWorld
	{
		class Grid;
	};

	// Inherits lighting, weather, sound maps and surface sounds from Chernarus Plus; everything
	// that depends on the land itself is set here.
	class aotearoa: ChernarusPlus
	{
		description = "Aotearoa";
		pictureMap = "maps\aotearoa\data\branding\map_picture_co.paa";
		pictureShot = "maps\aotearoa\data\branding\loading_1_co.paa";
		worldName = "maps\aotearoa\world\aotearoa.wrp";
		mapSize = 25600;
		centerPosition[] = {12800, 12800, 0};
		newRoadsShape = "\maps\aotearoa\data\roads\roads.shp";

		// The engine counts northern latitudes as negative, so a southern one is positive.
		latitude = 41.5;
		longitude = 172.6;
		// Southern summer.
		startDate = "15/01/2027";
		startTime = "10:00";

		// Vanilla ChernarusMap takes its name and textures from here (otherwise it shows Chernarus).
		// The AotearoaMap item in @AotearoaMap carries its own copies; see tools/build_map_item.py.
		mapDisplayNameKey = "Map of Aotearoa";
		mapDescriptionKey = "A folded road map of Aotearoa New Zealand with a 1 km grid and every town listed on the back.";
		mapTextureClosed = "maps\aotearoa\data\mapitem\aotearoa_map_closed_co.paa";
		mapTextureOpened = "maps\aotearoa\data\mapitem\aotearoa_map_opened_co.paa";
		mapTextureLegend = "maps\aotearoa\data\mapitem\aotearoa_map_legend_co.paa";
		// Chernarus's 2D map overlay would be drawn over this terrain.
		userMapPath = "";

		// Without this the world would load Chernarus's navmesh. The .nm file is made with
		// NavMeshGenerator once the world is built (docs/TERRAIN_BUILDER_GUIDE.md, step 15); until
		// then infected and animals stand still. Values are Bohemia's recommended ones, except that
		// isolated islands are kept: the filter keeps only land joined to the seed, which would drop
		// the South Island and Stewart Island.
		class Navmesh
		{
			navmeshName = "\maps\aotearoa\navmesh\aotearoa.nm";
			filterIsolatedIslandsOnLoad = 0;
			visualiseOffset = 0.0;
			class GenParams
			{
				tileWidth = 50.0;
				cellSize1 = 0.25;
				cellSize2 = 0.1;
				cellSize3 = 0.1;
				filterIsolatedIslands = 0;
				seedPosition[] = {17200, 0, 20200};  // central Auckland
				class Agent
				{
					diameter = 0.6;
					standHeight = 1.5;
					crouchHeight = 1.0;
					proneHeight = 0.5;
					maxStepHeight = 0.45;
					maxSlope = 60.0;
				};
				class Links
				{
					class ZedJump387_050
					{
						jumpLength = 1.50;
						jumpHeight = 0.50;
						minCenterHeight = 0.3;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump0";
						flags[] = {"jumpOver"};
						color = 0x66ff0000;
					};
					class ZedJump388_050
					{
						jumpLength = 1.50;
						jumpHeight = 0.50;
						minCenterHeight = -0.5;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump0";
						flags[] = {"jumpOver"};
						color = 0x66dd5500;
					};
					class ZedJump387_110
					{
						jumpLength = 3.90;
						jumpHeight = 1.1;
						minCenterHeight = 0.5;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump0";
						flags[] = {"jumpOver"};
						color = 0x66008000;
					};
					class ZedJump420_160
					{
						jumpLength = 4.0;
						jumpHeight = 1.6;
						minCenterHeight = 1.1;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump0";
						flags[] = {"jumpOver"};
						color = 0x660000ff;
					};
					class ZedJump265_210
					{
						jumpLength = 2.45;
						jumpHeight = 2.5;
						minCenterHeight = 1.8;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump0";
						flags[] = {"climb"};
						color = 0x669400d3;
					};
					class Fence50_110deer
					{
						typeId = 100;
						jumpLength = 8.0;
						jumpHeight = 1.1;
						minCenterHeight = 0.5;
						jumpDropdownMin = 1.0;
						jumpDropdownMax = -1.0;
						areaType = "jump2";
						flags[] = {"jumpOver"};
						color = 0x66aaaaFF;
					};
					class Fence110_160deer
					{
						typeId = 101;
						jumpLength = 8.0;
						jumpHeight = 1.6;
						minCenterHeight = 1.1;
						jumpDropdownMin = 1.0;
						jumpDropdownMax = -1.0;
						areaType = "jump3";
						flags[] = {"jumpOver"};
						color = 0x6624fff8;
					};
					class Fence50_110hen
					{
						typeId = 110;
						jumpLength = 4.0;
						jumpHeight = 1.1;
						minCenterHeight = 0.5;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump4";
						flags[] = {"jumpOver"};
						color = 0xFFFFAA00;
					};
					class Fence110_160hen
					{
						typeId = 111;
						jumpLength = 4.0;
						jumpHeight = 1.6;
						minCenterHeight = 1.1;
						jumpDropdownMin = 0.5;
						jumpDropdownMax = -0.5;
						areaType = "jump4";
						flags[] = {"jumpOver"};
						color = 0xFFFFAA00;
					};
				};
			};
		};

		class Grid: Grid
		{
			offsetX = 0;
			offsetY = 25600;
			class Zoom1
			{
				zoomMax = 0.15;
				format = "XY";
				formatX = "000";
				formatY = "000";
				stepX = 100;
				stepY = -100;
			};
			class Zoom2
			{
				zoomMax = 0.85;
				format = "XY";
				formatX = "00";
				formatY = "00";
				stepX = 1000;
				stepY = -1000;
			};
			class Zoom3
			{
				zoomMax = 1e+30;
				format = "XY";
				formatX = "0";
				formatY = "0";
				stepX = 10000;
				stepY = -10000;
			};
		};

		#include "config\names.hpp"
	};
};
