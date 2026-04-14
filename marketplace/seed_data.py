"""
Seed 3 sample suppliers into the marketplace SQLite registry.
Run once during setup: python marketplace/seed_data.py
"""

from __future__ import annotations

import sys
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
        "min_price": 0.025,
        "base_cost": 0.020,
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
        "min_price": 0.020,
        "base_cost": 0.018,
        "margin_pct": 18.0,
        "lead_days": 7,
        "warranty_yrs": 2.0,
        "metadata": {
            "description": "Budget-friendly seating specialist",
            "products": ["office chairs", "stacking chairs", "folding tables"],
        },
    },
    {
        "name": "OfficePro",
        "category": "office_supplies",
        "rating": 4.5,
        "min_price": 0.005,
        "base_cost": 0.003,
        "margin_pct": 25.0,
        "lead_days": 3,
        "warranty_yrs": 1.0,
        "metadata": {
            "description": "Fast delivery office supplies and stationery",
            "products": ["paper", "pens", "binders", "desk organizers"],
        },
    },
]


def seed() -> list[dict]:
    """Insert all sample suppliers and return their records."""
    from utils.wallet import Wallet, save_wallet, fund_wallet_from_faucet
    
    results = []
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
            
            results.append(record)
            print(f"  Seeded: {record['name']} ({record['supplier_id'][:8]}...) with wallet {wallet.address[:8]}...")
        except Exception as e:
            print(f"  Warning: {data['name']} skipped — {e}", file=sys.stderr)
    return results


if __name__ == "__main__":
    print("Seeding marketplace suppliers...")
    seeded = seed()
    print(f"\nDone — {len(seeded)}/{len(SUPPLIERS)} suppliers seeded.")
    for s in seeded:
        print(f"  [{s['category']}] {s['name']} — rating {s['rating']}, base_cost {s['base_cost']}")
