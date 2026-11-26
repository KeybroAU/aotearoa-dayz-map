// init.c for Aotearoa, based on vanilla dayzOffline.chernarusplus.
void main()
{
	Hive ce = CreateHive();
	if ( ce )
		ce.InitOffline();

	// Seasons. The date follows the server clock (serverTime = "SystemTime"), so the seasons are
	// New Zealand's: summer in January, snow storms and short days in July. To stay in one
	// season, set pin_month to a month (1 = January, mid-summer; 7 = July, mid-winter).
	int pin_month = 0;
	int year, month, day, hour, minute;
	GetGame().GetWorld().GetDate(year, month, day, hour, minute);
	if (pin_month > 0 && month != pin_month)
	{
		GetGame().GetWorld().SetDate(year, pin_month, 10, hour, minute);
	}

	// Loot positions: once the world is built, uncomment the next two lines, start the server
	// once, and copy storage_1/export/mapgrouppos.xml and the mapgroupcluster*.xml files (fruit
	// trees, mushrooms) into this mission folder. Then comment them out again.
	// GetCEApi().ExportProxyData(Vector(12800, 0, 12800), 25600);
	// GetCEApi().ExportClusterData();
}

class CustomMission: MissionServer
{
	void SetRandomHealth(EntityAI itemEnt)
	{
		if ( itemEnt )
		{
			float rndHlt = Math.RandomFloat( 0.45, 0.65 );
			itemEnt.SetHealth01( "", "", rndHlt );
		}
	}

	override PlayerBase CreateCharacter(PlayerIdentity identity, vector pos, ParamsReadContext ctx, string characterName)
	{
		Entity playerEnt;
		playerEnt = GetGame().CreatePlayer( identity, characterName, pos, 0, "NONE" );
		Class.CastTo( m_player, playerEnt );
		GetGame().SelectPlayer( identity, m_player );
		return m_player;
	}

	override void StartingEquipSetup(PlayerBase player, bool clothesChosen)
	{
		EntityAI itemClothing;
		EntityAI itemEnt;
		float rand;

		itemClothing = player.FindAttachmentBySlotName( "Body" );
		if ( itemClothing )
		{
			SetRandomHealth( itemClothing );
			itemEnt = itemClothing.GetInventory().CreateInInventory( "BandageDressing" );
			player.SetQuickBarEntityShortcut( itemEnt, 2 );

			string chemlightArray[] = { "Chemlight_White", "Chemlight_Yellow", "Chemlight_Green", "Chemlight_Red" };
			int rndIndex = Math.RandomInt( 0, 4 );
			itemEnt = itemClothing.GetInventory().CreateInInventory( chemlightArray[rndIndex] );
			SetRandomHealth( itemEnt );
			player.SetQuickBarEntityShortcut( itemEnt, 1 );

			rand = Math.RandomFloatInclusive( 0.0, 1.0 );
			if ( rand < 0.35 )
				itemEnt = player.GetInventory().CreateInInventory( "Apple" );
			else if ( rand > 0.65 )
				itemEnt = player.GetInventory().CreateInInventory( "Pear" );
			else
				itemEnt = player.GetInventory().CreateInInventory( "Plum" );
			player.SetQuickBarEntityShortcut( itemEnt, 3 );
			SetRandomHealth( itemEnt );
		}

		itemClothing = player.FindAttachmentBySlotName( "Legs" );
		if ( itemClothing )
			SetRandomHealth( itemClothing );

		itemClothing = player.FindAttachmentBySlotName( "Feet" );
	}
};

Mission CreateCustomMission(string path)
{
	return new CustomMission();
}
