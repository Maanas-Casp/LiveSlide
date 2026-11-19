# Data source register

Status: inventory of candidate sources as checked on 2026-11-12. The study region and date range are not confirmed, so no source has been downloaded and no real-data result can be produced yet. Recheck collection version, dates, license and regional coverage immediately before ingestion. Raw files stay under `data/raw/` and must not be committed.

| Source | Candidate product / version | Resolution and coverage | Access and license | Current decision / known gap |
|---|---|---|---|---|
| Rainfall | GPM IMERG Final daily, `GPM_3IMERGDF_07`, V07 | 0.1° daily; global | NASA GES DISC / Earthdata; NASA government data terms. Cite product metadata and access date in each run. | Candidate. Current reader samples the nearest source pixel at each 1 km cell centroid. This repeats coarse rainfall values across cells; do not imply 1 km rainfall detail. |
| Soil moisture | SMAP L4 Geophysical Data, `SPL4SMGP`, Version 8 | 3-hourly, 9 km EASE-Grid 2.0; global | NSIDC DAAC; Earthdata account required. Cite DOI `10.5067/T5RUATAQREF8`. | Candidate. Current reader uses the nearest 9 km pixel and averages available 3-hourly values by UTC day. Check missingness and latency. |
| Terrain | NASA SRTM Global 1 arc-second, `SRTMGL1`, Version 003 | 1 arc-second; global | USGS LP DAAC / Earthdata; check current product terms and attribution before redistribution. | Candidate. Derive elevation, slope, curvature and TWI after reprojection. Record algorithms, neighborhood and output CRS. |
| Event inventory | NASA Cooperative Open Online Landslide Repository (COOLR), point/event layers; includes Global Landslide Catalog records and other contributed inventories | Event-dependent spatial accuracy and date range | NASA Earthdata GIS service and downloads. COOLR asks users to cite each event inventory using its `citation` attribute. Review each record's provenance and terms. | Candidate. Deduplicate exact records, retain event source and reported location accuracy. Do not assume all reports have the same validation or license. |
| Roads and settlements | OpenStreetMap data | Region- and extract-date-dependent | ODbL. Attribute © OpenStreetMap contributors and link to the copyright/license page. | Candidate. Record extract timestamp/provider; preserve attribution. Confirm compatibility before distributing derived database exports. |
| LHASA baseline | `Global_Landslide_Nowcast`, Version 1.1 (collection `Global_Landslide_Nowcast_1.1`) | Daily, 1 km; archive 2000-06-14 through 2020-12-31, latitude 60°S–60°N | NASA GES DISC / Earthdata; DOI `10.5067/0D23ALHMHHT5`; public NASA data. | Prompt candidate verified. Its archive ends in 2020, so it cannot benchmark later dates. Check the newer Version 2 collection before locking a study period; if no temporal overlap exists, report LHASA unavailable. |

## Access and reproducibility

Earthdata credentials belong only in the developer's ignored local `.env`; never print or commit them. The pipeline will record collection short name, version, access date, date range, license/attribution, processing method, file hash and code commit in each output manifest. Region selection must be justified from available event counts, location accuracy, source coverage and the project scope before any source data are downloaded.

## References checked

- [IMERG Final daily V07 product page](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGDF_07/summary)
- [NSIDC SMAP L4 SPL4SMGP Version 8](https://nsidc.org/data/spl4smgp/versions/8)
- [USGS LP DAAC SRTM Collection User Guide](https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf)
- [NASA COOLR events service and per-event citation guidance](https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Events_Polygons/MapServer)
- [OpenStreetMap attribution and ODbL guidance](https://www.openstreetmap.org/copyright)
- [NASA LHASA Version 1.1 catalog metadata](https://access.earthdata.nasa.gov/collections/C2036912694-GES_DISC)
