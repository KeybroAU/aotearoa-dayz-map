// "Designed by Keybro" and Keybrogaming.com in the corner of the in-game map, on this world only.
modded class MapMenu
{
	protected Widget m_AotearoaWatermark;

	override Widget Init()
	{
		Widget root = super.Init();
		string worldName = "empty";
		g_Game.GetWorldName(worldName);
		worldName.ToLower();
		if (root && worldName == "aotearoa")
		{
			m_AotearoaWatermark = g_Game.GetWorkspace().CreateWidgets("maps/aotearoa/gui/layouts/aotearoa_map_watermark.layout", root);
			TextWidget credit = TextWidget.Cast(root.FindAnyWidget("AotearoaMapCredit"));
			if (credit)
				credit.SetOutline(1, 0xB4000000);
			TextWidget site = TextWidget.Cast(root.FindAnyWidget("AotearoaMapSite"));
			if (site)
				site.SetOutline(1, 0xB4000000);
		}
		return root;
	}
};
