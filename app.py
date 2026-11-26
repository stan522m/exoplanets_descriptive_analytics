import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

import queries

st.set_page_config(
    page_title="NASA Exoplanet Explorer & Habitability Analytics",
    layout="wide",
)


def classify_radius_tier(rade: float | None) -> str:
    if pd.isna(rade) or rade <= 0:
        return "Unknown / Missing Radius"
    if rade < 1.25:
        return "Sub-Earth / Terrestrial (<1.25 R⊕)"
    if rade < 2.0:
        return "Super-Earth (1.25–2.0 R⊕)"
    if rade < 4.0:
        return "Sub-Neptune / Mini-Neptune (2.0–4.0 R⊕)"
    if rade < 10.0:
        return "Neptune-like / Ice Giant (4.0–10.0 R⊕)"
    return "Jovian / Gas Giant (≥10.0 R⊕)"


def get_filter_bounds() -> tuple[int, int, float]:
    sql = """
    SELECT
        COALESCE(MIN(disc_year), 1992)::INT,
        COALESCE(MAX(disc_year), 2026)::INT,
        COALESCE(MAX(sy_dist), 5000.0)::FLOAT
    FROM planets
    """
    with queries.get_connection() as con:
        min_yr, max_yr, max_dist = con.execute(sql).fetchone()
    return int(min_yr), int(max_yr), float(max_dist)


def main() -> None:
    st.title("NASA Exoplanet Explorer & Habitability Analytics")
    st.caption(
        "Powered by NASA Exoplanet Archive (`pscomppars`) + DuckDB + Plotly — "
        "examining confirmed exoplanet populations, orbital/size regimes, and observational completeness."
    )

    kpis = queries.get_summary_kpis()
    min_yr, max_yr, max_dist_catalog = get_filter_bounds()

    # Sidebar controls
    st.sidebar.header("Catalog Filters")
    with queries.get_connection() as con:
        all_methods = [
            r[0]
            for r in con.execute(
                "SELECT DISTINCT discoverymethod FROM planets WHERE discoverymethod IS NOT NULL ORDER BY 1"
            ).fetchall()
        ]

    selected_methods = st.sidebar.multiselect(
        "Discovery Method",
        options=all_methods,
        default=all_methods,
    )
    selected_years = st.sidebar.slider(
        "Discovery Year Range",
        min_value=min_yr,
        max_value=max_yr,
        value=(min_yr, max_yr),
    )
    dist_cap = max(100.0, round(max_dist_catalog, -1))
    max_dist = st.sidebar.slider(
        "Max System Distance (parsecs)",
        min_value=10.0,
        max_value=float(dist_cap),
        value=float(dist_cap),
        step=50.0,
    )
    host_query = st.sidebar.text_input("Host Star Search (`hostname`)", value="")
    color_by = st.sidebar.selectbox(
        "Scatter Color Encoding",
        options=["Size Regime", "Discovery Method", "Equilibrium Temp (K)"],
        index=0,
    )

    # Top-level catalog & completeness KPIs
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Confirmed Planets", f"{kpis['total_planets']:,}")
    c2.metric("Host Stars", f"{kpis['total_hosts']:,}")
    c3.metric("In Multi-Planet Systems", f"{kpis['planets_in_multi_systems']:,}")
    c4.metric("Radius Coverage", f"{kpis['pct_has_radius']}%")
    c5.metric("Mass Coverage", f"{kpis['pct_has_mass']}%")
    c6.metric("Eq. Temp Coverage", f"{kpis['pct_has_eqt']}%")

    df = queries.get_filtered_planets(
        methods=selected_methods if selected_methods else [],
        year_range=selected_years,
        max_dist_pc=max_dist,
        host_search=host_query,
    )

    if df.empty:
        st.warning("No exoplanets match the current filter combination. Widen filters in the sidebar.")
        return

    df = df.copy()
    df["size_regime"] = df["pl_rade"].apply(classify_radius_tier)

    st.divider()

    # Row 1: Discovery Evolution & Planetary Regimes Scatter
    left_col, right_col = st.columns([1.15, 1.35])

    with left_col:
        st.subheader("Discovery & Detection Evolution")
        trends_df = (
            df.dropna(subset=["disc_year", "discoverymethod"])
            .groupby(["disc_year", "discoverymethod"], as_index=False)
            .agg(planet_count=("pl_name", "count"))
        )
        fig_trend = px.bar(
            trends_df,
            x="disc_year",
            y="planet_count",
            color="discoverymethod",
            labels={
                "disc_year": "Discovery Year",
                "planet_count": "Confirmed Planets",
                "discoverymethod": "Discovery Method",
            },
        )
        fig_trend.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_trend, use_container_width=True)

    with right_col:
        st.subheader("Planet Radius vs. Orbital Period (Log Scale)")
        scatter_df = df[(df["pl_rade"] > 0) & (df["pl_orbper"] > 0)].copy()
        if scatter_df.empty:
            st.info("No rows with positive radius and orbital period in the current selection.")
        else:
            if color_by == "Size Regime":
                color_col = "size_regime"
            elif color_by == "Discovery Method":
                color_col = "discoverymethod"
            else:
                color_col = "pl_eqt"

            fig_scatter = px.scatter(
                scatter_df,
                x="pl_orbper",
                y="pl_rade",
                color=color_col,
                log_x=True,
                log_y=True,
                hover_data={
                    "pl_name": True,
                    "hostname": True,
                    "sy_pnum": True,
                    "pl_bmasse": ":.2f",
                    "pl_eqt": ":.0f",
                    "st_teff": ":.0f",
                    "sy_dist": ":.1f",
                    "disc_year": True,
                },
                labels={
                    "pl_orbper": "Orbital Period (days, log scale)",
                    "pl_rade": "Planet Radius (Earth radii R⊕, log scale)",
                    "size_regime": "Size Regime",
                    "discoverymethod": "Discovery Method",
                    "pl_eqt": "Eq. Temp (K)",
                    "pl_name": "Planet",
                    "hostname": "Host Star",
                    "sy_pnum": "Planets in System",
                    "pl_bmasse": "Mass (M⊕)",
                    "st_teff": "Star Temp (K)",
                    "sy_dist": "Distance (parsecs)",
                    "disc_year": "Year",
                },
            )
            fig_scatter.update_traces(marker=dict(size=6, opacity=0.75))
            fig_scatter.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_scatter, use_container_width=True)

    st.divider()

    # Row 2: Filtered System & Planet Catalogue + Data Hygiene Notes
    st.subheader(f"Filtered Catalogue Preview ({len(df):,} planets matching filters)")
    column_labels = {
        "pl_name": "Planet Name",
        "hostname": "Host Star",
        "sy_pnum": "Planets in System",
        "disc_year": "Discovery Year",
        "discoverymethod": "Discovery Method",
        "pl_orbper": "Orbital Period (days)",
        "pl_rade": "Radius (Earth Radii)",
        "pl_bmasse": "Mass (Earth Masses)",
        "pl_eqt": "Equilibrium Temp (K)",
        "st_teff": "Star Temp (K)",
        "sy_dist": "Distance (parsecs)",
        "size_regime": "Size Regime",
    }
    catalogue_df = df[list(column_labels.keys())].head(200).rename(columns=column_labels)
    st.dataframe(catalogue_df, use_container_width=True, hide_index=True)

    with st.expander("Methodology, Completeness & Observational Bias Notes"):
        st.markdown(
            """
            * **Single-row-per-planet catalog (`pscomppars`):** Uses NASA Exoplanet Archive's composite planetary parameters table so each confirmed planet appears once rather than once per published reference.
            * **High parameter completeness:** Over 99% of rows in this snapshot include both radius (`pl_rade`) and mass (`pl_bmasse`), and over 91% include equilibrium temperature (`pl_eqt`).
            * **Observational selection effects:** Transit surveys strongly favor short-period (close-in) orbits and larger radii, while radial velocity and direct imaging probe different mass/separation regimes. Empty regions on log-scale scatter plots often reflect detection thresholds rather than physical absence.
            """
        )


if __name__ == "__main__":
    main()