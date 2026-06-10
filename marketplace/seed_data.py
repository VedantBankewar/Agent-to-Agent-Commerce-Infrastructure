"""
Seed 3 sample suppliers into the marketplace SQLite registry.
Run once during setup: python marketplace/seed_data.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from pathlib import Path

# Add project root to path so we can import marketplace.registry
sys.path.insert(0, str(Path(__file__).parent.parent))

from marketplace.registry import create_supplier


# ---------------------------------------------------------------------------
# Sample suppliers
# ---------------------------------------------------------------------------

SUPPLIERS = [
    {
        "name": "FurniCo",
        "category": "furniture",
        "rating": 4.7,
        "min_price": 1.25,
        "base_cost": 1.00,
        "margin_pct": 20.0,
        "lead_days": 14,
        "warranty_yrs": 3.0,
        "metadata": {
            "description": "Premium ergonomic furniture manufacturer",
            "products": ["ergonomic chairs", "standing desks", "cabinets"],
        },
    },
    {
        "name": "ChairHub",
        "category": "furniture",
        "rating": 4.2,
        "min_price": 1.00,
        "base_cost": 0.90,
        "margin_pct": 18.0,
        "lead_days": 7,
        "warranty_yrs": 2.0,
        "metadata": {
            "description": "Budget-friendly seating specialist",
            "products": ["office chairs", "stacking chairs", "folding tables"],
        },
    },
    {
        "name": "EgoStyle",
        "category": "furniture",
        "rating": 4.9,
        "min_price": 1.50,
        "base_cost": 1.25,
        "margin_pct": 22.0,
        "lead_days": 10,
        "warranty_yrs": 5.0,
        "metadata": {
            "description": "High-end luxury furniture design",
            "products": ["executive chairs", "bespoke desks", "meeting tables"],
        },
    },
    {
        "name": "OfficePro",
        "category": "office_supplies",
        "rating": 4.5,
        "min_price": 0.25,
        "base_cost": 0.15,
        "margin_pct": 25.0,
        "lead_days": 3,
        "warranty_yrs": 1.0,
        "metadata": {
            "description": "Fast delivery office supplies and stationery",
            "products": ["paper", "pens", "binders", "desk organizers"],
        },
    },
    {
        "name": "TechSource",
        "category": "electronics",
        "rating": 4.6,
        "min_price": 1.60,
        "base_cost": 1.80,
        "margin_pct": 12.0,
        "lead_days": 5,
        "warranty_yrs": 2.0,
        "metadata": {
            "description": "Reliable electronics and peripherals distributor",
            "products": ["wireless mice", "keyboards", "webcams", "USB hubs"],
        },
    },
    {
        "name": "GadgetWorks",
        "category": "electronics",
        "rating": 4.4,
        "min_price": 1.80,
        "base_cost": 2.00,
        "margin_pct": 15.0,
        "lead_days": 7,
        "warranty_yrs": 1.5,
        "metadata": {
            "description": "Wide range of consumer electronics and accessories",
            "products": ["mice", "mechanical keyboards", "monitors", "headsets"],
        },
    },
    {
        "name": "CircuitDeals",
        "category": "electronics",
        "rating": 4.8,
        "min_price": 1.40,
        "base_cost": 1.50,
        "margin_pct": 10.0,
        "lead_days": 10,
        "warranty_yrs": 3.0,
        "metadata": {
            "description": "Bulk electronics at competitive prices with extended warranty",
            "products": ["mice", "keyboards", "monitors", "docking stations"],
        },
    },
    # General-purpose suppliers — guarantee the "general" category always has
    # at least two bidders so discovery never returns empty for any category
    # the procurement form can submit. They quote arbitrary free-text items via
    # base_cost (no inventory row needed), so any product name works.
    {
        "name": "OmniSupply",
        "category": "general",
        "rating": 4.6,
        "min_price": 0.55,
        "base_cost": 0.65,
        "margin_pct": 15.0,
        "lead_days": 4,
        "warranty_yrs": 2.0,
        "metadata": {
            "description": "Broad-catalog general supplier with fast fulfillment",
            "products": ["assorted goods", "office & facility supplies"],
        },
    },
    {
        "name": "GeneralGoods",
        "category": "general",
        "rating": 4.3,
        "min_price": 0.50,
        "base_cost": 0.60,
        "margin_pct": 18.0,
        "lead_days": 6,
        "warranty_yrs": 1.0,
        "metadata": {
            "description": "General-purpose B2B goods and miscellaneous supplies",
            "products": ["assorted goods", "misc supplies"],
        },
    },
]


# ---------------------------------------------------------------------------
# Per-item inventory: { supplier_name: [ (item, category, unit_cost, stock) ] }
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-item inventory pricing (scaled for testnet demo — 20 USDC budget)
# Prices are low to allow full escrow testing with limited funds.
# ---------------------------------------------------------------------------

INVENTORY = {
    # Furniture suppliers
    "FurniCo": [
        ("Ergonomic Office Chair", "furniture", 1.80, 200),
        ("Standing Desk", "furniture", 2.20, 100),
        ("Filing Cabinet", "furniture", 1.20, 150),
        ("Conference Table", "furniture", 2.50, 30),
        ("Office Chair", "furniture", 1.50, 300),
    ],
    "ChairHub": [
        ("Ergonomic Office Chair", "furniture", 1.60, 500),
        ("Office Chair", "furniture", 1.10, 800),
        ("Stacking Chair", "furniture", 0.60, 1000),
        ("Folding Table", "furniture", 0.90, 200),
        ("Standing Desk", "furniture", 2.00, 50),
    ],
    "EgoStyle": [
        ("Ergonomic Office Chair", "furniture", 2.20, 50),
        ("Executive Chair", "furniture", 2.50, 30),
        ("Bespoke Desk", "furniture", 2.40, 20),
        ("Meeting Table", "furniture", 2.50, 10),
        ("Standing Desk", "furniture", 2.30, 40),
    ],
    # Office supplies
    "OfficePro": [
        ("Ballpoint Pen", "office_supplies", 0.10, 10000),
        ("Notebook", "office_supplies", 0.40, 5000),
        ("Binder", "office_supplies", 0.50, 3000),
        ("Desk Organizer", "office_supplies", 1.20, 500),
        ("Paper Ream", "office_supplies", 0.60, 8000),
        ("Stapler", "office_supplies", 0.80, 2000),
    ],
    # Electronics suppliers
    "TechSource": [
        ("Wireless Mouse", "electronics", 1.80, 500),
        ("Keyboard", "electronics", 2.20, 400),
        ("Webcam", "electronics", 2.50, 200),
        ("USB Hub", "electronics", 1.40, 300),
        ("Headset", "electronics", 2.30, 250),
        ("Monitor", "electronics", 2.50, 80),
        ("Laptop", "electronics", 2.50, 40),
    ],
    "GadgetWorks": [
        ("Wireless Mouse", "electronics", 2.00, 300),
        ("Mechanical Keyboard", "electronics", 2.40, 150),
        ("Monitor", "electronics", 2.50, 60),
        ("Headset", "electronics", 2.30, 200),
        ("Keyboard", "electronics", 2.20, 350),
        ("Webcam", "electronics", 2.50, 100),
        ("Laptop", "electronics", 2.50, 25),
    ],
    "CircuitDeals": [
        ("Wireless Mouse", "electronics", 1.50, 800),
        ("Keyboard", "electronics", 1.80, 600),
        ("Monitor", "electronics", 2.40, 120),
        ("Docking Station", "electronics", 2.10, 100),
        ("Headset", "electronics", 1.90, 400),
        ("Webcam", "electronics", 2.00, 150),
        ("Laptop", "electronics", 2.50, 50),
    ],
}


def seed() -> list[dict]:
    """Insert all sample suppliers and return their records."""
    from utils.wallet import Wallet, save_wallet, fund_wallet_from_faucet

    results = []
    name_to_id = {}
    for data in SUPPLIERS:
        try:
            # Generate a new wallet for the supplier
            wallet = Wallet.generate()
            data["wallet_addr"] = wallet.address

            from marketplace.registry import SupplierCreate
            record = create_supplier(SupplierCreate(**data))

            # Save the wallet dynamically
            supplier_id = record['supplier_id']
            save_wallet(supplier_id, wallet)
            name_to_id[record['name']] = supplier_id

            results.append(record)
            print(f"  Seeded: {record['name']} ({record['supplier_id'][:8]}...) with wallet {wallet.address[:8]}...")
        except Exception as e:
            print(f"  Warning: {data['name']} skipped — {e}", file=sys.stderr)

    # Seed inventory
    _seed_inventory(name_to_id)
    return results


def _seed_inventory(name_to_id: dict[str, str]) -> None:
    """Populate the inventory table with per-item pricing."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(os.getenv("DATABASE_PATH", "db/hackathon.db"))
    cursor = conn.cursor()
    count = 0
    for supplier_name, items in INVENTORY.items():
        supplier_id = name_to_id.get(supplier_name)
        if not supplier_id:
            continue
        for item, category, unit_cost, stock_qty in items:
            try:
                cursor.execute(
                    "INSERT INTO inventory (inventory_id, supplier_id, item, category, stock_qty, reserved_qty, unit_cost, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
                    (str(uuid.uuid4()), supplier_id, item, category, stock_qty, unit_cost, now, now),
                )
                count += 1
            except Exception as e:
                print(f"    Inventory skip: {supplier_name}/{item} — {e}", file=sys.stderr)
    conn.commit()
    conn.close()
    print(f"  Seeded: {count} inventory items across {len(name_to_id)} suppliers")


if __name__ == "__main__":
    print("Seeding marketplace suppliers...")
    seeded = seed()
    print(f"\nDone — {len(seeded)}/{len(SUPPLIERS)} suppliers seeded.")
    for s in seeded:
        print(f"  [{s['category']}] {s['name']} — rating {s['rating']}, base_cost {s['base_cost']}")
