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

// Food stashes (tools/food_stashes.py): Countdown truck crashes, dairy stock rooms and bach
// pantries. Each is topped up when it runs low; delete aotearoa/food_stashes.json to turn them off.
class AotearoaStash
{
	string kind;
	string label;
	float x;
	float z;
	float r;
	int minItems;
	int maxItems;
	ref array<string> items;
}

class AotearoaStashFile
{
	int restockMinutes;
	ref array<ref AotearoaStash> stashes;
}

class AotearoaStashes
{
	ref AotearoaStashFile m_File;

	void AotearoaStashes()
	{
		string path = "$mission:aotearoa/food_stashes.json";
		if ( !FileExist( path ) )
			return;
		JsonFileLoader<AotearoaStashFile>.JsonLoadFile( path, m_File );
		if ( !m_File || !m_File.stashes )
			return;
		Restock();
		int minutes = m_File.restockMinutes;
		if ( minutes < 5 )
			minutes = 5;
		GetGame().GetCallQueue( CALL_CATEGORY_GAMEPLAY ).CallLater( Restock, minutes * 60000, true );
	}

	void Restock()
	{
		foreach ( AotearoaStash s : m_File.stashes )
		{
			if ( !s.items || s.items.Count() == 0 )
				continue;
			vector centre = Vector( s.x, GetGame().SurfaceY( s.x, s.z ), s.z );
			array<Object> near = new array<Object>;
			GetGame().GetObjectsAtPosition( centre, s.r + 2, near, null );
			int have = 0;
			foreach ( Object o : near )
			{
				if ( s.items.Find( o.GetType() ) != -1 )
					have++;
			}
			if ( have >= s.minItems )
				continue;
			int want = Math.RandomIntInclusive( s.minItems, s.maxItems ) - have;
			for ( int i = 0; i < want; i++ )
			{
				float a = Math.RandomFloat( 0, Math.PI2 );
				float d = Math.RandomFloat( 0, s.r );
				float px = s.x + Math.Cos( a ) * d;
				float pz = s.z + Math.Sin( a ) * d;
				GetGame().CreateObjectEx( s.items.GetRandomElement(), Vector( px, GetGame().SurfaceY( px, pz ), pz ), ECE_PLACE_ON_SURFACE );
			}
		}
	}
}

class CustomMission: MissionServer
{
	ref AotearoaStashes m_FoodStashes;

	override void OnInit()
	{
		super.OnInit();
		m_FoodStashes = new AotearoaStashes();
	}

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
