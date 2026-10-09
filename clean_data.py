from pathlib import Path
import pandas as pd
import geopandas as gpd

# ============================================================
# SIMPLE CLEANING PIPELINE FOR TIL6022
# Put this file in the SAME folder as the raw data.
# Cleaned CSVs are written automatically to ./cleaned_data/
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "raw_data"
OUT_DIR = BASE_DIR / "cleaned_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Exact filenames from your Windows folder
F_NETWORK = RAW_DIR / "inweva_verkeersbanen_2025DEC.csv"
F_TRAFFIC = RAW_DIR / "inweva_weekdag_2025DEC.csv"
F_ROADS = RAW_DIR / "wegvakken.txt"
F_ACCIDENTS = RAW_DIR / "ongevallen.txt"
F_INWEVA_SHP = RAW_DIR / "INWEVA2025.shp"

REQUIRED_FILES = [
    F_NETWORK,
    F_TRAFFIC,
    F_ROADS,
    F_ACCIDENTS,
    F_INWEVA_SHP,
    BASE_DIR / "INWEVA2025.dbf",
    BASE_DIR / "INWEVA2025.shx",
    BASE_DIR / "INWEVA2025.prj",
]

missing = [f.name for f in REQUIRED_FILES if not f.exists()]
if missing:
    raise FileNotFoundError(
        "The following required raw files are missing:\n- "
        + "\n- ".join(missing)
    )


def clean_string(series):
    return series.astype("string").str.strip()


def read_selected_road_sections(path, wanted_ids, chunksize=200_000):
    """Read only relevant rows from the very large wegvakken.txt file."""
    usecols = [
        "WVK_ID", "JTE_ID_BEG", "JTE_ID_END",
        "WEGNUMMER", "RIJRICHTNG", "GME_ID", "GME_NAAM"
    ]

    selected = []
    for chunk in pd.read_csv(
        path,
        dtype=str,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    ):
        chunk["WVK_ID"] = clean_string(chunk["WVK_ID"])
        keep = chunk[chunk["WVK_ID"].isin(wanted_ids)]
        if not keep.empty:
            selected.append(keep)

    if not selected:
        return pd.DataFrame(columns=usecols)

    return pd.concat(selected, ignore_index=True)


# ============================================================
# 1. SELECT SOUTH-HOLLAND A-ROADS
# ============================================================
print("1/6  Reading INWEVA network and selecting A-roads...")

network = pd.read_csv(F_NETWORK, sep=";", dtype=str, low_memory=False)
a_roads = network[
    network["VBN_OMS_TXT"].str.startswith("A", na=False)
].copy()

# Build VBN -> WVK links
links = a_roads[["VBN_ID", "NWB_IDS"]].copy()
links["WVK_ID"] = links["NWB_IDS"].str.split(",")
links = links.explode("WVK_ID")
links["WVK_ID"] = clean_string(links["WVK_ID"])
links = links.dropna(subset=["WVK_ID"]).drop_duplicates()
all_a_wvk_ids = set(links["WVK_ID"])

print("2/6  Determining which A-road sections are in South Holland...")

# Use BRON to obtain municipality IDs that belong to Zuid-Holland.
acc_municipalities = pd.read_csv(
    F_ACCIDENTS,
    dtype=str,
    usecols=["PVE_CODE", "GME_ID", "GME_NAAM"],
    low_memory=False,
)

zh_municipalities = (
    acc_municipalities.loc[
        acc_municipalities["PVE_CODE"].eq("ZH"),
        ["GME_ID", "GME_NAAM"]
    ]
    .dropna(subset=["GME_ID"])
    .drop_duplicates()
)
zh_ids = set(clean_string(zh_municipalities["GME_ID"]).dropna())

# Read only NWB road sections that belong to an INWEVA A-road.
roads = read_selected_road_sections(F_ROADS, all_a_wvk_ids)

link_with_location = links.merge(
    roads[["WVK_ID", "GME_ID", "GME_NAAM"]],
    on="WVK_ID",
    how="left",
)

selected_vbns = []
boundary_vbns = []
outside_vbns = []
unmapped_vbns = []

for vbn_id, group in link_with_location.groupby("VBN_ID", sort=False):
    municipality_ids = clean_string(group["GME_ID"]).dropna()

    if municipality_ids.empty:
        unmapped_vbns.append(vbn_id)
        continue

    in_zh = municipality_ids.isin(zh_ids)

    if in_zh.all():
        selected_vbns.append(vbn_id)
    elif in_zh.any():
        boundary_vbns.append(vbn_id)
    else:
        outside_vbns.append(vbn_id)

selected_vbns = set(selected_vbns)

network_cols = [
    "VBN_ID", "VBN_OMS_TXT", "VBN_LENGTE", "NWB_IDS",
    "BPSZIJDE_B", "BPSZIJDE_E",
    "BNSUBSRT_B", "BNSUBSRT_E"
]

network_clean = network.loc[
    network["VBN_ID"].isin(selected_vbns),
    network_cols
].copy()
network_clean["VBN_LENGTE"] = pd.to_numeric(
    network_clean["VBN_LENGTE"], errors="coerce"
)
network_clean.to_csv(
    OUT_DIR / "01_inweva_network_zh_motorways.csv",
    index=False
)

# Restrict VBN-WVK links and NWB road sections to the selected network.
vbn_wvk = links[links["VBN_ID"].isin(selected_vbns)].copy()
selected_wvk_ids = set(vbn_wvk["WVK_ID"])
roads_clean = roads[roads["WVK_ID"].isin(selected_wvk_ids)].copy()


# ============================================================
# 2. CLEAN TRAFFIC DATA
# ============================================================
print("3/6  Cleaning traffic data...")

traffic = pd.read_csv(F_TRAFFIC, sep=";", dtype=str, low_memory=False)
traffic_cols = [
    "VBN_ID",
    "AFST_MTW", "KWAL_AL", "KWAL_VC", "DK_E_WK",
    "AL_E_WK", "L1_E_WK", "L2_E_WK", "L3_E_WK",
    "VRPC_E_WK", "AL_N_WK"
]

traffic_clean = traffic.loc[
    traffic["VBN_ID"].isin(selected_vbns),
    traffic_cols
].copy()
traffic_clean.to_csv(
    OUT_DIR / "02_inweva_traffic_zh_motorways.csv",
    index=False
)


# ============================================================
# 3. LINK BRON ACCIDENTS
# ============================================================
print("4/6  Linking BRON accidents to the selected motorway sections...")

accident_cols = [
    "VKL_NUMMER", "AP3_CODE",
    "ANTL_DOD", "ANTL_GZH", "ANTL_SEH",
    "MAXSNELHD", "JTE_ID", "WVK_ID",
    "GME_ID", "GME_NAAM", "PVE_CODE", "PVE_NAAM"
]

accidents = pd.read_csv(
    F_ACCIDENTS,
    dtype=str,
    usecols=accident_cols,
    low_memory=False
)

wvk_to_vbn = (
    vbn_wvk.drop_duplicates("WVK_ID")
    .set_index("WVK_ID")["VBN_ID"]
    .to_dict()
)

# Direct assignment through WVK_ID
direct = accidents[
    accidents["WVK_ID"].isin(wvk_to_vbn)
].copy()
direct["VBN_ID"] = direct["WVK_ID"].map(wvk_to_vbn)
direct["ASSIGNMENT_METHOD"] = "WVK_DIRECT"

# Junction-located crashes: find selected carriageways that touch each junction.
road_vbn = roads_clean[
    ["WVK_ID", "JTE_ID_BEG", "JTE_ID_END"]
].merge(
    vbn_wvk[["VBN_ID", "WVK_ID"]],
    on="WVK_ID",
    how="inner"
)

junction_links = pd.concat(
    [
        road_vbn[["VBN_ID", "JTE_ID_BEG"]]
        .rename(columns={"JTE_ID_BEG": "JTE_ID"}),
        road_vbn[["VBN_ID", "JTE_ID_END"]]
        .rename(columns={"JTE_ID_END": "JTE_ID"}),
    ],
    ignore_index=True
).dropna().drop_duplicates()

jte_to_vbns = junction_links.groupby("JTE_ID")["VBN_ID"].agg(
    lambda x: sorted(set(x))
)

direct_ids = set(direct["VKL_NUMMER"])

junction_candidates = accidents[
    ~accidents["VKL_NUMMER"].isin(direct_ids)
    & accidents["JTE_ID"].isin(jte_to_vbns.index)
].copy()

junction_candidates["_OPTIONS"] = junction_candidates["JTE_ID"].map(jte_to_vbns)

unique_junction = junction_candidates[
    junction_candidates["_OPTIONS"].str.len().eq(1)
].copy()
unique_junction["VBN_ID"] = unique_junction["_OPTIONS"].str[0]
unique_junction["ASSIGNMENT_METHOD"] = "JTE_UNIQUE"

ambiguous_junction = junction_candidates[
    junction_candidates["_OPTIONS"].str.len().gt(1)
].copy()
ambiguous_junction["VBN_ID"] = pd.NA
ambiguous_junction["ASSIGNMENT_METHOD"] = "JTE_AMBIGUOUS"

unique_junction = unique_junction.drop(columns="_OPTIONS")
ambiguous_junction = ambiguous_junction.drop(columns="_OPTIONS")

accidents_clean = pd.concat(
    [direct, unique_junction, ambiguous_junction],
    ignore_index=True
)
accidents_clean = accidents_clean.sort_values("VKL_NUMMER").reset_index(drop=True)
accidents_clean.to_csv(
    OUT_DIR / "03_bron_accidents_zh_motorways.csv",
    index=False
)


# ============================================================
# 4. EXPORT INWEVA GEOMETRY
# ============================================================
print("5/6  Reading motorway geometry...")

geo = gpd.read_file(F_INWEVA_SHP)
geo["VBN_ID"] = geo["VBN_ID"].astype(str)
geo_clean = geo[geo["VBN_ID"].isin(selected_vbns)].copy()

geometry_csv = pd.DataFrame({
    "VBN_ID": geo_clean["VBN_ID"],
    "GEOMETRY_WKT": geo_clean.geometry.map(
        lambda g: g.wkt if g is not None else pd.NA
    )
})
geometry_csv.to_csv(
    OUT_DIR / "04_inweva_geometry_zh_motorways.csv",
    index=False
)


# ============================================================
# 5. BUILD FINAL ANALYSIS-READY DATASET
# ============================================================
print("6/6  Building final analysis-ready dataset...")

analysis = network_clean.merge(
    traffic_clean,
    on="VBN_ID",
    how="left"
)

numeric_cols = [
    "VBN_LENGTE", "AL_E_WK", "L1_E_WK",
    "L2_E_WK", "L3_E_WK", "AL_N_WK", "DK_E_WK"
]
for col in numeric_cols:
    analysis[col] = pd.to_numeric(analysis[col], errors="coerce")

analysis["HAS_TRAFFIC_DATA"] = analysis["AL_E_WK"].notna().astype(int)

analysis["ANNUAL_VEHICLE_KM"] = (
    analysis["AL_E_WK"]
    * 365
    * (analysis["VBN_LENGTE"] / 1000)
)

analysis["HGV_SHARE_PCT"] = (
    (analysis["L2_E_WK"] + analysis["L3_E_WK"])
    / analysis["AL_E_WK"]
    * 100
).where(analysis["AL_E_WK"] > 0)

analysis["NIGHT_TRAFFIC_SHARE_PCT"] = (
    analysis["AL_N_WK"]
    / analysis["AL_E_WK"]
    * 100
).where(analysis["AL_E_WK"] > 0)

assigned = accidents_clean[
    accidents_clean["VBN_ID"].notna()
].copy()

crash_summary = assigned.groupby("VBN_ID").agg(
    TOTAL_CRASHES=("VKL_NUMMER", "size"),
    MATERIAL_DAMAGE_CRASHES=("AP3_CODE", lambda x: x.eq("UMS").sum()),
    INJURY_CRASHES=("AP3_CODE", lambda x: x.eq("LET").sum()),
    FATAL_CRASHES=("AP3_CODE", lambda x: x.eq("DOD").sum()),
).reset_index()

crash_summary["INJURY_FATAL_CRASHES"] = (
    crash_summary["INJURY_CRASHES"]
    + crash_summary["FATAL_CRASHES"]
)

analysis = analysis.merge(
    crash_summary,
    on="VBN_ID",
    how="left"
)

count_cols = [
    "TOTAL_CRASHES", "MATERIAL_DAMAGE_CRASHES",
    "INJURY_CRASHES", "FATAL_CRASHES",
    "INJURY_FATAL_CRASHES"
]
analysis[count_cols] = analysis[count_cols].fillna(0).astype(int)

analysis["CRASH_RATE_PER_100M_VKM"] = (
    analysis["TOTAL_CRASHES"]
    / analysis["ANNUAL_VEHICLE_KM"]
    * 100_000_000
).where(analysis["ANNUAL_VEHICLE_KM"] > 0)

analysis["INJURY_FATAL_RATE_PER_100M_VKM"] = (
    analysis["INJURY_FATAL_CRASHES"]
    / analysis["ANNUAL_VEHICLE_KM"]
    * 100_000_000
).where(analysis["ANNUAL_VEHICLE_KM"] > 0)

analysis["ROAD_NUMBER"] = analysis["VBN_OMS_TXT"].str.extract(
    r"^(A\d+)",
    expand=False
)

analysis = analysis.merge(
    geometry_csv,
    on="VBN_ID",
    how="left"
)

final = pd.DataFrame({
    "VBN_ID": analysis["VBN_ID"],
    "ROAD_DESCRIPTION": analysis["VBN_OMS_TXT"],
    "ROAD_NUMBER": analysis["ROAD_NUMBER"],
    "ROAD_LENGTH_M": analysis["VBN_LENGTE"],
    "DIRECTION_BEGIN": analysis["BPSZIJDE_B"],
    "DIRECTION_END": analysis["BPSZIJDE_E"],
    "CARRIAGEWAY_TYPE_BEGIN": analysis["BNSUBSRT_B"],
    "CARRIAGEWAY_TYPE_END": analysis["BNSUBSRT_E"],
    "HAS_TRAFFIC_DATA": analysis["HAS_TRAFFIC_DATA"],
    "AVG_DAILY_TRAFFIC": analysis["AL_E_WK"],
    "PASSENGER_CARS": analysis["L1_E_WK"],
    "MEDIUM_HEAVY_VEHICLES": analysis["L2_E_WK"],
    "HEAVY_VEHICLES": analysis["L3_E_WK"],
    "HGV_SHARE_PCT": analysis["HGV_SHARE_PCT"],
    "NIGHT_TRAFFIC": analysis["AL_N_WK"],
    "NIGHT_TRAFFIC_SHARE_PCT": analysis["NIGHT_TRAFFIC_SHARE_PCT"],
    "TRAFFIC_QUALITY_ALL": analysis["KWAL_AL"],
    "TRAFFIC_QUALITY_VEHICLE_CLASS": analysis["KWAL_VC"],
    "TRAFFIC_COVERAGE_PCT": analysis["DK_E_WK"],
    "ANNUAL_VEHICLE_KM": analysis["ANNUAL_VEHICLE_KM"],
    "TOTAL_CRASHES": analysis["TOTAL_CRASHES"],
    "MATERIAL_DAMAGE_CRASHES": analysis["MATERIAL_DAMAGE_CRASHES"],
    "INJURY_CRASHES": analysis["INJURY_CRASHES"],
    "FATAL_CRASHES": analysis["FATAL_CRASHES"],
    "INJURY_FATAL_CRASHES": analysis["INJURY_FATAL_CRASHES"],
    "CRASH_RATE_PER_100M_VKM": analysis["CRASH_RATE_PER_100M_VKM"],
    "INJURY_FATAL_RATE_PER_100M_VKM": analysis["INJURY_FATAL_RATE_PER_100M_VKM"],
    "GEOMETRY_WKT": analysis["GEOMETRY_WKT"],
})

final.to_csv(
    OUT_DIR / "05_analysis_ready_zh_motorways.csv",
    index=False
)

# Small reproducibility report.
report = pd.DataFrame([
    ["All INWEVA carriageways", len(network)],
    ["A-road carriageways", len(a_roads)],
    ["Selected South Holland A-road carriageways", len(selected_vbns)],
    ["Boundary-crossing carriageways excluded", len(boundary_vbns)],
    ["Outside South Holland excluded", len(outside_vbns)],
    ["No usable municipality mapping excluded", len(unmapped_vbns)],
    ["Selected sections with traffic data", int(analysis["HAS_TRAFFIC_DATA"].sum())],
    ["Directly assigned crashes", int((accidents_clean["ASSIGNMENT_METHOD"] == "WVK_DIRECT").sum())],
    ["Uniquely assigned junction crashes", int((accidents_clean["ASSIGNMENT_METHOD"] == "JTE_UNIQUE").sum())],
    ["Ambiguous junction crashes", int((accidents_clean["ASSIGNMENT_METHOD"] == "JTE_AMBIGUOUS").sum())],
    ["Rows in final analysis dataset", len(final)],
], columns=["CHECK", "VALUE"])

report.to_csv(
    OUT_DIR / "00_cleaning_report.csv",
    index=False
)

print()
print("DONE")
print(f"Cleaned files are in: {OUT_DIR}")
print("Main file: 05_analysis_ready_zh_motorways.csv")
