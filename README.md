# Accident Risk on National Highways in South Holland

TIL6022 Python Programming – Project Group 32

**Authors:** Erdem Aydin, Francisco de Meij, Floris Korthals Altes, Rosanna Kliffen, Thijs de Vegt

## Project summary
Busy motorway sections have many crashes simply because many vehicles use them. This project separates the *number* of crashes from the *crash rate* (crashes per million vehicle-kilometres) for all national-highway carriageway sections in South Holland in 2025, and investigates which road and traffic characteristics are associated with crash frequency.

**Main research question:** Which highway carriageway sections in South Holland have the highest crash rates in 2025, given how busy they are, and which traffic and carriageway characteristics are associated with differences in crash frequency?

**Sub-questions**
1. How does the ranking of carriageway sections by number of accidents differ from the ranking by risk (accidents per million vehicle-kilometres)?
2. Which carriageway and traffic characteristics are associated with higher crash frequency after controlling for traffic volume and section length?
3. Are the carriageway sections with the highest risk of injury and fatal accidents the same as those with the highest risk of all accidents?

## Repository contents
| File / folder | Description |
| --- | --- |
| `Final_Report_Group32.ipynb` | **Final report** (main deliverable) |
| `Final_Report_Group32.html` | HTML export of the final report |
| `clean_data.py` | Data pipeline: selects South Holland motorway sections, links accidents and traffic data, writes `cleaned_data/` |
| `analysis_subq1.ipynb` | Sub-question 1: crash counts vs. crash rates |
| `analysis_subq2.ipynb` | Sub-question 2: Negative Binomial regression on carriageway and traffic characteristics |
| `analysis_subq3.ipynb` | Sub-question 3: overall vs. injury/fatal crash rates |
| `figures/` | Figures produced by the analysis notebooks |
| `cleaned_data/` | Cleaned, analysis-ready data (output of `clean_data.py`) |
| `project_proposal_group32.ipynb` / `.html` | Project proposal |
| `requirements.txt` | Python packages needed |

## Data
All data are open data from Rijkswaterstaat (year 2025):

| Dataset | Files to download | Source |
| --- | --- | --- |
| BRON – registered accidents (incl. NWB road sections) | `ongevallen.txt`, `wegvakken.txt` | https://data.overheid.nl/dataset/9841-verkeersongevallen---bestand-geregistreerde-ongevallen-nederland |
| INWEVA 2025 – traffic intensities and network | `inweva_verkeersbanen_2025DEC.csv`, `inweva_weekdag_2025DEC.csv`, `INWEVA2025.shp/.dbf/.shx/.prj` | https://data.overheid.nl/dataset/84461-intensiteit-wegvakken--inweva- |

The raw files are too large for GitHub and are therefore not included. The cleaned data in `cleaned_data/` are included, so the analysis notebooks and the report can be run without downloading the raw data.

## How to reproduce the analysis
1. Clone the repository and create an environment (Python 3.11 or newer):
   ```bash
   git clone https://github.com/Rosanna1234/TIL-programming-group-project.git
   cd TIL-programming-group-project
   pip install -r requirements.txt
   ```
2. *(Optional, only to rebuild the cleaned data)* Download the raw files listed above, place them in a folder `raw_data/` in the project root with exactly these file names, and run:
   ```bash
   python clean_data.py
   ```
   This writes six CSV files to `cleaned_data/`, including `00_cleaning_report.csv` (number of sections and crashes kept or excluded at each step) and `05_analysis_ready_zh_motorways.csv` (one row per carriageway section).
3. Run the analysis notebooks `analysis_subq1.ipynb`, `analysis_subq2.ipynb` and `analysis_subq3.ipynb` (Kernel → Restart & Run All).
4. Open `Final_Report_Group32.ipynb` and run all cells.
