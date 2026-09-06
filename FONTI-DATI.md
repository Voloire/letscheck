# Data sources

The bundled SQLite catalog is built offline from versioned snapshots:

- [OpenNGC](https://github.com/mattiaverga/OpenNGC), CC BY-SA 4.0, for NGC/IC records and Messier links;
- [VizieR VII/20](https://cdsarc.cds.unistra.fr/viz-bin/Cat?VII/20), Sharpless 1959;
- [VizieR VII/7A](https://cdsarc.cds.unistra.fr/viz-bin/Cat?VII/7A), Lynds 1962;
- [VizieR VII/21](https://cdsarc.cds.unistra.fr/viz-bin/Cat?VII/21) and [J/A+A/399/141](https://cdsarc.cds.unistra.fr/viz-bin/Cat?J/A+A/399/141), van den Bergh records and coordinates;
- `wikidata-crosswalk.json`, a reviewed cross-catalog name map derived from Wikidata structured data (CC0-1.0) plus a small project supplement.

The crosswalk is supplemental metadata. It groups identifiers only when a local identifier matches a Wikidata catalog code, and it does not replace the coordinates or measurements from the primary catalog snapshots. The raw snapshots remain in `data/raw/`; runtime code reads only the generated `data/catalog.sqlite3`.
