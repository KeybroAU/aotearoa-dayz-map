// Use Aotearoa's own world data (climate and weather) instead of the Chernarus fallback.
modded class MissionBase
{
	override void InitialiseWorldData()
	{
		string worldName = "empty";
		g_Game.GetWorldName(worldName);
		worldName.ToLower();
		if (worldName == "aotearoa")
		{
			m_WorldData = new AotearoaData();
			m_DynamicMusicPlayerRegistry = new DynamicMusicPlayerRegistry();
			return;
		}
		super.InitialiseWorldData();
	}
};
