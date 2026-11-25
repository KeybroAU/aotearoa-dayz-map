// World config for the Aotearoa terrain. Pack P:\maps\aotearoa into aotearoa.pbo with the
// prefix maps\aotearoa (see README, "Packing the mod").

class CfgPatches
{
	class aotearoa
	{
		units[] = {"aotearoa"};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data", "DZ_Structures", "DZ_Worlds_Chernarusplus_World"};
	};
};

class CfgVehicles
{
	class HouseNoDestruct;
	#include "config\signs.hpp"
	#include "config\structures.hpp"
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
