import io
from pathlib import Path
import duckdb
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "exoplanets.duckdb"

QUERY = """
SELECT pl_name, hostname, sy_snum, sy_pnum, disc_year, discoverymethod,
       pl_orbper, pl_rade, pl_bmasse, pl_eqt, st_teff, sy_dist
FROM pscomppars
"""
TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


def main() -> None:
    response = requests.get(
        TAP_URL,
        params={"query": QUERY, "format": "csv"},
        timeout=60,
    )
    response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text))
    if df.empty:
        raise RuntimeError("TAP query returned zero rows.")

    con = duckdb.connect(str(DB_PATH))
    try:
        con.execute("CREATE OR REPLACE TABLE planets AS SELECT * FROM df")
        count = con.execute("SELECT COUNT(*) FROM planets").fetchone()[0]
    finally:
        con.close()

    print(f"Loaded {count:,} rows into {DB_PATH}")


if __name__ == "__main__":
    main()