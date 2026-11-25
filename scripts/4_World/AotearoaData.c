// New Zealand climate for the Aotearoa terrain: southern seasons, a real alpine lapse rate,
// changeable maritime weather, and snow storms in mid-winter. Picked by the modded
// MissionBase in 5_Mission when the world is "aotearoa".
class AotearoaData : ChernarusPlusData
{
	// The terrain is about seven times flatter than the real country (Aoraki is 533 m here), so
	// 0.04 C per game metre is the real 0.65 C per 100 m: the main divide is about 20 C colder
	// than the coast.
	static const float LAPSE_PER_M = 0.04;

	// Chance (out of 100) that the next overcast change is clear, and the roll above which it is
	// bad weather, by month. Winter brings more fronts; spring changes fastest.
	protected static const ref array<int> CLEAR_CHANCE = {38, 38, 34, 30, 26, 22, 20, 22, 26, 28, 32, 36};
	protected static const ref array<int> BAD_ROLL = {84, 84, 80, 76, 72, 68, 65, 68, 70, 72, 78, 82};

	// Distant artillery is heard from these points. Chernarus's list has two inside this map, so
	// fire from out at sea past the map edges instead.
	protected static const ref array<vector> AOTEAROA_ARTY_STRIKE_POS =
	{
		"-500.00 150.00 12000.00",
		"-500.00 150.00 20000.00",
		"26100.00 150.00 9000.00",
		"26100.00 150.00 18000.00",
		"12000.00 150.00 -500.00"
	};

	override void Init()
	{
		super.Init();
		m_FiringPos = AOTEAROA_ARTY_STRIKE_POS;

		// Long days in January, short in July (Christchurch).
		m_Sunrise_Jan = 6.1;
		m_Sunset_Jan = 21.0;
		m_Sunrise_Jul = 8.0;
		m_Sunset_Jul = 17.1;

		array<float> minTemps = CfgGameplayHandler.GetEnvironmentMinTemps();
		if (!minTemps || minTemps.Count() != 12)
			m_MinTemps = {12, 12, 10, 7, 4, 2, 1, 2, 4, 6, 8, 11};
		array<float> maxTemps = CfgGameplayHandler.GetEnvironmentMaxTemps();
		if (!maxTemps || maxTemps.Count() != 12)
			m_MaxTemps = {23, 22, 20, 17, 14, 11, 10, 12, 14, 17, 19, 21};

		m_TemperaturePerHeightReductionModifier = LAPSE_PER_M;
		m_WorldWindCoef = 0.55;
		m_CloudsTemperatureEffectModifier = 2.5;
	}

	override void SetupLiquidTemperatures()
	{
		super.SetupLiquidTemperatures();
		m_LiquidSettings.m_Temperatures[LIQUID_SALTWATER] = 15.0;
		m_LiquidSettings.m_Temperatures[LIQUID_WATER] = 12.0;
		m_LiquidSettings.m_Temperatures[LIQUID_STILLWATER] = 13.0;
		m_LiquidSettings.m_Temperatures[LIQUID_RIVERWATER] = 9.0;
		m_LiquidSettings.m_Temperatures[LIQUID_FRESHWATER] = 9.0;
		m_LiquidSettings.m_Temperatures[LIQUID_CLEANWATER] = 8.0;
	}

	static bool IsMidWinter(int month)
	{
		return month >= 6 && month <= 8;
	}

	static bool IsSpring(int month)
	{
		return month >= 9 && month <= 11;
	}

	override bool WeatherOnBeforeChange(EWeatherPhenomenon type, float actual, float change, float time)
	{
		int year, month, day, hour, minute;
		g_Game.GetWorld().GetDate(year, month, day, hour, minute);
		int m = month - 1;
		if (m < 0 || m > 11)
			m = 0;

		if (type == EWeatherPhenomenon.OVERCAST)
		{
			m_WeatherDefaultSettings.m_ClearWeatherChance = CLEAR_CHANCE.Get(m);
			m_WeatherDefaultSettings.m_BadWeatherChance = BAD_ROLL.Get(m);
			m_ClearWeatherChance = CLEAR_CHANCE.Get(m);
			m_BadWeatherChance = BAD_ROLL.Get(m);
			// Four seasons in one day: spring fronts arrive and clear twice as fast.
			if (IsSpring(month))
			{
				m_WeatherDefaultSettings.m_OvercastMinTime = 300;
				m_WeatherDefaultSettings.m_OvercastMaxTime = 600;
				m_WeatherDefaultSettings.m_OvercastMinLength = 300;
				m_WeatherDefaultSettings.m_OvercastMaxLength = 600;
			}
			else
			{
				m_WeatherDefaultSettings.m_OvercastMinTime = 600;
				m_WeatherDefaultSettings.m_OvercastMaxTime = 900;
				m_WeatherDefaultSettings.m_OvercastMinLength = 600;
				m_WeatherDefaultSettings.m_OvercastMaxLength = 900;
			}
		}

		bool handled = super.WeatherOnBeforeChange(type, actual, change, time);

		// Chernarus turns snow off on every change. In June to August a southerly storm (heavy
		// overcast) can bring light snow instead.
		if (IsMidWinter(month))
		{
			m_Weather.GetSnowfall().SetLimits(0, 0.5);
			m_Weather.SetSnowfallThresholds(0.85, 1.0, 120);
		}
		return handled;
	}
};
