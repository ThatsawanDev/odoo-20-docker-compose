"""Convert Odoo 19 ACL CSV files to Odoo 20 ir.access CSV files."""

import csv
import re
from pathlib import Path


ADDONS = Path(__file__).resolve().parents[1] / "addons"
MODULES = (
    "thai_address_master",
    "thai_sales_stock_easy",
    "sale_shopee",
    "sale_lazada",
    "smart_sale_tiktok",
    "thai_sales_stock_hub",
)

for module in MODULES:
    root = ADDONS / module
    source = root / "security" / "ir.model.access.csv"
    if not source.exists():
        continue
    models = {}
    for path in root.rglob("*.py"):
        for name in re.findall(r'^\s*_name\s*=\s*[\'\"]([^\'\"]+)', path.read_text(encoding="utf-8"), re.M):
            models[f"model_{name.replace('.', '_')}"] = name
    with source.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    target = source.with_name("ir.access.csv")
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("id", "name", "model_id", "group_id/id", "operation", "domain"))
        for row in rows:
            model = models.get(row["model_id:id"])
            if not model:
                raise ValueError(f"{module}: unknown model {row['model_id:id']}")
            operation = "".join(letter for field, letter in (
                ("perm_create", "c"), ("perm_read", "r"),
                ("perm_write", "u"), ("perm_unlink", "d"),
            ) if row[field] == "1")
            writer.writerow((row["id"], row["name"], model, row["group_id:id"], operation, ""))
    manifest = root / "__manifest__.py"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("security/ir.model.access.csv", "security/ir.access.csv"), encoding="utf-8")
    source.unlink()
    print(f"{module}: {len(rows)} access rules")
