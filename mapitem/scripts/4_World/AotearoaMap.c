// Vanilla ItemMap.InitMapState takes the name and textures from CfgWorlds of the loaded terrain,
// so every map item looks alike. This one keeps its own from CfgVehicles AotearoaMap.
class AotearoaMap extends ChernarusMap
{
	override void InitMapState()
	{
		super.InitMapState();

		m_DisplayName = ConfigGetString("displayName");
		m_Description = ConfigGetString("descriptionShort");
		m_TextureClosed = ConfigGetString("mapTextureClosed");
		m_TextureOpened = ConfigGetString("mapTextureOpened");
		m_TextureLegend = ConfigGetString("mapTextureLegend");

		SetObjectTexture(0, m_TextureClosed);
		SetObjectTexture(1, m_TextureOpened);
		SetObjectTexture(2, m_TextureLegend);
	}
}
