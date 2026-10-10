# Salmon Lice Exceedance Prediction

## The Question
We investigate whether lagged sea temperature, temperature anomalies, delousing treatment history, and autoregressive lice counts can predict whether a farm's average adult female lice count exceeds statutory thresholds within the next 1–2 weeks in Norwegian fish farms.

## Data Sources
- [BarentsWatch Fish Health API](docs/sources.md) (Data levert av BarentsWatch og Mattilsynet)

## How to run it
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your API credentials.
4. Run the ingestion script: `python src/ingest.py`

## Repository Structure
- `data/raw/`: Landed data from APIs.
- `src/`: Python source code.
- `docs/`: Documentation and data source cards.

## Status
M1 — ingestion complete (WIP)

## Team
- Çağatay Oruk (GitHub: se-230717041)
- Mehmet Egemen Karagöz (GitHub: se-230717063)
