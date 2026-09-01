# Synthetic data contract

OpenSteamOpt v0.1 downloads no data and needs no API key. `synthetic_day()` produces 24
hourly records with these columns:

| Column | Unit | Meaning |
|---|---|---|
| `hour` | integer | Consecutive zero-based hour |
| `hp_demand_tph` | t/h | HP process steam demand |
| `mp_demand_tph` | t/h | MP process steam demand |
| `electric_demand_mw` | MW | Site electrical demand |
| `electricity_price_eur_per_mwh` | €/MWh | Import reference price |
| `natural_gas_price_eur_per_mwh_fuel` | €/MWh fuel | Boiler 1 fuel price |
| `biofuel_price_eur_per_mwh_fuel` | €/MWh fuel | Boiler 2 fuel price |
| `carbon_price_eur_per_tco2` | €/tCO₂ | Direct-emissions price |

All fixtures are project-authored and deterministic. They do not reproduce ABB, plant,
market, Copernicus, Elexon or other third-party datasets. The RTO rejects missing,
non-finite, negative or misnamed values under the v0.1 contract.

Future observed-data adapters must document source, licence, retrieval time, units,
transformations and redistribution constraints. Credentials and raw restricted data must
never be committed.
