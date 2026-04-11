"""
Energia Tariff Configuration
Extracted from Energia bills for POLAR ICE LTD
"""

# Tariff: Industrial (LEU) - Main site MPRN 10000070022
# Contract ends: 31 Oct 2025
# Maximum Import Capacity: 290 kVA

INDUSTRIAL_LEU_TARIFF = {
    "name": "Industrial (LEU)",
    "contract_end": "2025-10-31",
    "max_import_capacity_kva": 290,

    # Energy charges (€/kWh)
    "energy_rate": 0.124178,  # Base energy charge

    # Distribution Use of System (DUoS) charges
    "duos_standing_charge_monthly": 401.41,  # Fixed monthly charge
    "duos_capacity_charge_per_kva": 2.8948,  # Per kVA of capacity
    "duos_peak_rate": 0.01513,  # €/kWh during peak (specific hours)
    "duos_day_rate": 0.01376,  # €/kWh during day (off-peak)
    "duos_night_rate": 0.00219,  # €/kWh during night

    # Transmission Use of System (TUoS) charges
    "demand_network_capacity_per_mwh": 7.3865,  # €/MWh
    "tuos_day_rate_per_mwh": 31.0312,  # €/MWh
    "tuos_night_rate_per_mwh": 31.0312,  # €/MWh

    # Supplier charges
    "supplier_capacity_charge_monthly": 826.62,  # Fixed monthly charge

    # Market charges (€/kWh)
    "capacity_socialisation_charge": -0.0003609,  # Credit
    "imperfections_charge": 0.01462,
    "market_operator_charge": 0.000641,
    "currency_adjustment_charge": 0.000015,

    # Levies and taxes
    "pso_levy_monthly": 455.30,  # Public Service Obligation - fixed monthly
    "eeos_charge": 0.0013,  # Energy Efficiency Obligation Scheme
    "eeos_credit": -0.0013,  # EEOS credit (net zero)
    "electricity_tax": 0.001,  # €/kWh
    "vat_rate": 0.09,  # 9%

    # Time-of-Use periods (Ireland)
    "peak_hours": [8, 9, 10, 17, 18, 19],  # Peak hours (example, verify from contract)
    "day_hours": list(range(8, 23)),  # 08:00 - 23:00
    "night_hours": list(range(0, 8)) + [23],  # 23:00 - 08:00
}


# Tariff: Wholesale Energy - General Purpose Night Saver
# Secondary site MPRN 10305074485
# Contract ends: 31 Mar 2026
# Maximum Import Capacity: 15 kVA

NIGHT_SAVER_TARIFF = {
    "name": "Wholesale Energy - General Purpose Night Saver",
    "contract_end": "2026-03-31",
    "max_import_capacity_kva": 15,

    # Standing charge
    "standing_charge_per_day": 0.354,  # €/day

    # Wholesale energy costs (€/kWh)
    "day_wholesale_energy": 0.1472059,
    "night_wholesale_energy": 0.1342857,

    # UoS and Market costs (€/kWh)
    "day_uos_market": 0.1261765,
    "night_uos_market": 0.0560714,

    # Supplier charges
    "supplier_capacity_charge_7am_11pm": 0.02123,  # €/kWh during 7am-11pm
    "capacity_socialisation_charge_7am_11pm": -0.0003609,  # Credit during 7am-11pm

    # Levies and taxes
    "pso_levy_monthly": 12.91,  # Fixed monthly charge
    "eeos_charge": 0.0013,
    "eeos_credit": -0.0013,
    "electricity_tax": 0.001,  # €/kWh
    "vat_rate": 0.09,  # 9%

    # Time periods
    "day_hours": list(range(8, 23)),  # 08:00 - 23:00
    "night_hours": list(range(0, 8)) + [23],  # 23:00 - 08:00
}


def calculate_energy_cost(kwh, tariff, time_of_day="day", days_in_period=30):
    """
    Calculate total cost for energy consumption based on tariff.

    Args:
        kwh: Total kWh consumed
        tariff: Tariff dictionary (INDUSTRIAL_LEU_TARIFF or NIGHT_SAVER_TARIFF)
        time_of_day: "day", "night", or "peak"
        days_in_period: Number of days in billing period

    Returns:
        dict: Breakdown of costs
    """
    costs = {}

    if tariff["name"] == "Industrial (LEU)":
        # Energy charge
        costs["energy_charge"] = kwh * tariff["energy_rate"]

        # DUoS charges
        costs["duos_standing"] = tariff["duos_standing_charge_monthly"]
        costs["duos_capacity"] = tariff["max_import_capacity_kva"] * tariff["duos_capacity_charge_per_kva"]

        # DUoS energy charges (time-dependent)
        if time_of_day == "peak":
            costs["duos_energy"] = kwh * tariff["duos_peak_rate"]
        elif time_of_day == "day":
            costs["duos_energy"] = kwh * tariff["duos_day_rate"]
        else:  # night
            costs["duos_energy"] = kwh * tariff["duos_night_rate"]

        # TUoS charges (convert kWh to MWh)
        mwh = kwh / 1000
        costs["demand_network_capacity"] = mwh * tariff["demand_network_capacity_per_mwh"]

        if time_of_day == "night":
            costs["tuos_energy"] = mwh * tariff["tuos_night_rate_per_mwh"]
        else:
            costs["tuos_energy"] = mwh * tariff["tuos_day_rate_per_mwh"]

        # Supplier charges
        costs["supplier_capacity"] = tariff["supplier_capacity_charge_monthly"]

        # Market charges
        costs["capacity_socialisation"] = kwh * tariff["capacity_socialisation_charge"]
        costs["imperfections"] = kwh * tariff["imperfections_charge"]
        costs["market_operator"] = kwh * tariff["market_operator_charge"]
        costs["currency_adjustment"] = kwh * tariff["currency_adjustment_charge"]

        # Levies
        costs["pso_levy"] = tariff["pso_levy_monthly"]
        costs["eeos"] = kwh * (tariff["eeos_charge"] + tariff["eeos_credit"])  # Net zero typically

        # Tax
        costs["electricity_tax"] = kwh * tariff["electricity_tax"]

    else:  # Night Saver tariff
        # Standing charge
        costs["standing_charge"] = tariff["standing_charge_per_day"] * days_in_period

        # Wholesale energy
        if time_of_day == "night":
            costs["wholesale_energy"] = kwh * tariff["night_wholesale_energy"]
            costs["uos_market"] = kwh * tariff["night_uos_market"]
        else:
            costs["wholesale_energy"] = kwh * tariff["day_wholesale_energy"]
            costs["uos_market"] = kwh * tariff["day_uos_market"]

        # Supplier charges (only during 7am-11pm)
        if time_of_day != "night":
            costs["supplier_capacity"] = kwh * tariff["supplier_capacity_charge_7am_11pm"]
            costs["capacity_socialisation"] = kwh * tariff["capacity_socialisation_charge_7am_11pm"]
        else:
            costs["supplier_capacity"] = 0
            costs["capacity_socialisation"] = 0

        # Levies
        costs["pso_levy"] = tariff["pso_levy_monthly"]
        costs["eeos"] = kwh * (tariff["eeos_charge"] + tariff["eeos_credit"])

        # Tax
        costs["electricity_tax"] = kwh * tariff["electricity_tax"]

    # Calculate subtotal
    costs["subtotal"] = sum(costs.values())

    # Add VAT
    costs["vat"] = costs["subtotal"] * tariff["vat_rate"]
    costs["total"] = costs["subtotal"] + costs["vat"]

    return costs


def get_time_of_day_category(hour, tariff):
    """
    Determine if hour is peak, day, or night based on tariff.

    Args:
        hour: Hour of day (0-23)
        tariff: Tariff dictionary

    Returns:
        str: "peak", "day", or "night"
    """
    if "peak_hours" in tariff and hour in tariff["peak_hours"]:
        return "peak"
    elif hour in tariff["day_hours"]:
        return "day"
    else:
        return "night"


def calculate_detailed_cost_breakdown(df, tariff=INDUSTRIAL_LEU_TARIFF, days_in_period=30):
    """
    Calculate detailed cost breakdown from energy consumption DataFrame.

    Args:
        df: DataFrame with columns: timestamp, Total kW
        tariff: Tariff dictionary
        days_in_period: Number of days in billing period

    Returns:
        dict: Detailed cost breakdown
    """
    if "Total kW" not in df.columns or len(df) == 0:
        return None

    # Calculate time differences for energy calculation (kWh)
    df_cost = df.copy()
    df_cost["hour"] = df_cost["timestamp"].dt.hour
    df_cost["time_diff_hours"] = df_cost["timestamp"].diff().dt.total_seconds() / 3600
    df_cost.loc[df_cost["time_diff_hours"] < 0, "time_diff_hours"] = 0
    df_cost.loc[df_cost["time_diff_hours"] > 1, "time_diff_hours"] = 0
    df_cost["kWh"] = df_cost["Total kW"] * df_cost["time_diff_hours"]

    # Categorize by time of day
    df_cost["tod"] = df_cost["hour"].apply(lambda h: get_time_of_day_category(h, tariff))

    # Group by time of day
    kwh_by_tod = df_cost.groupby("tod")["kWh"].sum()

    # Calculate costs for each time period
    total_costs = {
        "peak": 0, "day": 0, "night": 0,
        "energy_charge": 0, "network_charges": 0, "supplier_charges": 0,
        "market_charges": 0, "levies": 0, "taxes": 0
    }

    breakdown = {}

    for tod, kwh in kwh_by_tod.items():
        if kwh > 0:
            costs = calculate_energy_cost(kwh, tariff, tod, days_in_period)
            breakdown[f"{tod}_costs"] = costs
            total_costs[tod] = costs["total"]

    # Calculate totals across all time periods
    breakdown["total_kwh"] = df_cost["kWh"].sum()
    breakdown["total_cost_exc_vat"] = sum([v.get("subtotal", 0) for v in breakdown.values() if isinstance(v, dict)])
    breakdown["total_vat"] = sum([v.get("vat", 0) for v in breakdown.values() if isinstance(v, dict)])
    breakdown["total_cost_inc_vat"] = breakdown["total_cost_exc_vat"] + breakdown["total_vat"]

    # Average cost per kWh
    if breakdown["total_kwh"] > 0:
        breakdown["avg_cost_per_kwh"] = breakdown["total_cost_inc_vat"] / breakdown["total_kwh"]

    return breakdown
