"""Import historical UCI advertisements, never current availability."""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DATASET = "https://doi.org/10.24432/C5X623"


def convert(row):
    if row["currency"] != "USD" or row["price_type"] != "Monthly":
        return None
    identifier = "uci-" + row["id"]
    source_id = identifier + "-ad"
    date = datetime.fromtimestamp(int(row["time"]), timezone.utc).date().isoformat()
    # 'None' and 'null' are not interpreted as explicit pet prohibitions.
    cats = True if "Cats" in row["pets_allowed"].split(",") else None
    bedrooms = None if row["bedrooms"] in {"", "null", "None"} else float(row["bedrooms"])
    return {"id": identifier, "name": row["title"], "synthetic": False,
            "historical": True, "domain": "rental", "city": row["cityname"],
            "attributes": {"bedrooms": bedrooms, "cats_allowed": cats},
            "attribute_sources": {"bedrooms": source_id, "cats_allowed": source_id},
            "monthly_costs": {"complete": False, "items": [
                {"label": "advertised_rent", "amount_cents": int(Decimal(row["price"]) * 100), "source_id": source_id},
                {"label": "unverified_monthly_fees", "amount_cents": None, "source_id": source_id}]},
            "sources": {source_id: {"text": row["body"], "date": date,
                "type": "historical_advertisement", "dataset": DATASET,
                "original_source": row["source"], "license": "CC BY 4.0",
                "fields": {key: row[key] for key in ["bedrooms", "pets_allowed", "price", "fee", "amenities"]}}},
            "evidence": []}


def import_file(path, city):
    with Path(path).open(encoding="cp1252", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    selected = [row for row in rows if row["cityname"].casefold() == city.casefold()]
    candidates = [candidate for row in selected if (candidate := convert(row)) is not None]
    ids = [c["id"] for c in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate listing IDs")
    return candidates, {"dataset": DATASET, "license": "CC BY 4.0", "city": city,
                        "input_rows": len(rows), "selected_rows": len(selected),
                        "imported_rows": len(candidates), "historical": True,
                        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                        "dates": sorted({s["date"] for c in candidates for s in c["sources"].values()})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--city", default="Chicago")
    parser.add_argument("--output", default="data/private/chicago.json")
    args = parser.parse_args()
    candidates, manifest = import_file(args.csv_path, args.city)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps({"manifest": manifest, "candidates": candidates}, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, indent=2))
