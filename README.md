# Salmon Lice Exceedance Prediction

## The Question
We will investigate whether lagged sea temperature, temperature anomalies, delousing treatment history, and autoregressive lice counts can predict whether a farm's average adult female lice count exceeds statutory thresholds within the next 1–2 weeks. (Norwegian regulations define limits of 0.2 lice/fish during regional spring migration windows: Weeks 16–21 in south/central regions and Weeks 21–26 in the north, and 0.5 otherwise).

## Data Sources
- [BarentsWatch Fish Health API](docs/sources.md) (Data levert av BarentsWatch og Mattilsynet)

## How to run it
1. Clone the repository.
2. Create and activate a virtual environment: `python -m venv .venv` and activate it.
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your API credentials (`BW_CLIENT_ID` = email:client_name).
5. Generate the target cohort (optional, defaults provided): `python src/select_cohort.py`
6. Run the ingestion pipeline: `python src/ingest.py`

## Repository Structure
- `data/raw/`: Landed data from APIs. (Not committed to Git to strictly respect unverified redistribution terms).
- `src/`: Python source code (`api_client.py`, `select_cohort.py`, `ingest.py`).
- `config/`: Pipeline configuration (e.g., `cohort.txt`).
- `docs/`: Documentation and data source cards.

## Status
M1 — ingestion complete

## Team
- Çağatay Oruk (GitHub: 230717041)
- Mehmet Egemen Karagöz (GitHub: se-230717063)
