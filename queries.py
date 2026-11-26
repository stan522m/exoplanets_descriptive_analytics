from pathlib import Path
import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "data" / "exoplanets.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def get_summary_kpis() -> dict:
    sql = """
    SELECT
        COUNT(*) AS total_planets,
        COUNT(DISTINCT hostname) AS total_hosts,
        COUNT(*) FILTER (WHERE sy_pnum > 1) AS planets_in_multi_systems,
        ROUND(100.0 * COUNT(pl_rade) / COUNT(*), 1) AS pct_has_radius,
        ROUND(100.0 * COUNT(pl_bmasse) / COUNT(*), 1) AS pct_has_mass,
        ROUND(100.0 * COUNT(pl_eqt) / COUNT(*), 1) AS pct_has_eqt
    FROM planets
    """
    with get_connection() as con:
        row = con.execute(sql).fetchone()
    cols = [
        "total_planets",
        "total_hosts",
        "planets_in_multi_systems",
        "pct_has_radius",
        "pct_has_mass",
        "pct_has_eqt",
    ]
    return dict(zip(cols, row))


def get_discovery_trends() -> pd.DataFrame:
    sql = """
    SELECT
        disc_year,
        discoverymethod,
        COUNT(*) AS planet_count
    FROM planets
    WHERE disc_year IS NOT NULL
    GROUP BY disc_year, discoverymethod
    ORDER BY disc_year, planet_count DESC
    """
    with get_connection() as con:
        return con.execute(sql).df()


def get_filtered_planets(
    methods: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    max_dist_pc: float | None = None,
    host_search: str = "",
) -> pd.DataFrame:
    clauses = ["1=1"]
    params: list = []

    if methods:
        placeholders = ", ".join(["?"] * len(methods))
        clauses.append(f"discoverymethod IN ({placeholders})")
        params.extend(methods)

    if year_range:
        clauses.append("disc_year BETWEEN ? AND ?")
        params.extend([year_range[0], year_range[1]])

    if max_dist_pc is not None:
        clauses.append("(sy_dist IS NULL OR sy_dist <= ?)")
        params.append(max_dist_pc)

    if host_search.strip():
        clauses.append("LOWER(hostname) LIKE ?")
        params.append(f"%{host_search.strip().lower()}%")

    sql = f"""
    SELECT
        pl_name,
        hostname,
        sy_snum,
        sy_pnum,
        disc_year,
        discoverymethod,
        pl_orbper,
        pl_rade,
        pl_bmasse,
        pl_eqt,
        st_teff,
        sy_dist
    FROM planets
    WHERE {" AND ".join(clauses)}
    """
    with get_connection() as con:
        return con.execute(sql, params).df()