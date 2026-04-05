-- AgentTrade SQLite Schema
-- All timestamps in UTC. No hardcoded IDs — use UUIDs or generated keys.

-- Agents table: procurement agent and supplier agents
CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    agent_type  TEXT NOT NULL CHECK (agent_type IN ('procurement', 'supplier')),
    name        TEXT NOT NULL,
    wallet_addr TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('utcnow')),
    metadata    TEXT -- JSON blob for extra agent metadata
);

-- Suppliers table: supplier agent profiles with ratings and categories
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,
    wallet_addr  TEXT NOT NULL UNIQUE,
    rating       REAL NOT NULL DEFAULT 0.0 CHECK (rating >= 0.0 AND rating <= 5.0),
    min_price    REAL NOT NULL,  -- minimum acceptable unit price
    base_cost    REAL NOT NULL,  -- base cost per unit
    margin_pct   REAL NOT NULL,  -- margin as percentage (e.g. 15.0 = 15%)
    lead_days    INTEGER NOT NULL DEFAULT 7,  -- default lead time in days
    warranty_yrs REAL NOT NULL DEFAULT 1.0,
    created_at   TEXT NOT NULL DEFAULT (datetime('utcnow')),
    metadata     TEXT  -- JSON blob for extra supplier metadata
);

-- RFQs table: Request for Quote records
CREATE TABLE IF NOT EXISTS rfqs (
    rfq_id       TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL REFERENCES agents(agent_id),
    item         TEXT NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    budget       REAL NOT NULL CHECK (budget >= 0),
    deadline     TEXT NOT NULL,  -- ISO 8601 date string
    category     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'quotes_received', 'negotiating', 'closed', 'cancelled')),
    created_at   TEXT NOT NULL DEFAULT (datetime('utcnow')),
    closed_at    TEXT
);

-- Quotes table: supplier responses to RFQs
CREATE TABLE IF NOT EXISTS quotes (
    quote_id       TEXT PRIMARY KEY,
    rfq_id         TEXT NOT NULL REFERENCES rfqs(rfq_id),
    supplier_id    TEXT NOT NULL REFERENCES suppliers(supplier_id),
    unit_price     REAL NOT NULL CHECK (unit_price > 0),
    total_price    REAL NOT NULL CHECK (total_price >= 0),
    delivery_days  INTEGER NOT NULL CHECK (delivery_days >= 0),
    warranty_yrs   REAL NOT NULL DEFAULT 1.0,
    valid_until    TEXT NOT NULL,  -- ISO 8601 datetime
    status         TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'accepted', 'countered', 'rejected', 'expired')),
    created_at     TEXT NOT NULL DEFAULT (datetime('utcnow')),
    metadata       TEXT  -- JSON blob for negotiation history
);

-- Deals table: agreed transactions after negotiation
CREATE TABLE IF NOT EXISTS deals (
    deal_id        TEXT PRIMARY KEY,
    rfq_id         TEXT NOT NULL UNIQUE REFERENCES rfqs(rfq_id),
    buyer_id       TEXT NOT NULL REFERENCES agents(agent_id),
    supplier_id    TEXT NOT NULL REFERENCES suppliers(supplier_id),
    unit_price     REAL NOT NULL CHECK (unit_price > 0),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    total_amount   REAL NOT NULL CHECK (total_amount >= 0),
    deal_hash      TEXT NOT NULL,  -- SHA-256 hash anchored on-chain
    escrow_app_id  TEXT,            -- Algorand escrow contract app ID
    escrow_address  TEXT,           -- Escrow contract address
    deadline       TEXT NOT NULL,  -- ISO 8601 date for delivery
    status         TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'locked', 'delivered', 'completed', 'refunded', 'disputed')),
    created_at     TEXT NOT NULL DEFAULT (datetime('utcnow')),
    locked_at      TEXT,
    delivered_at   TEXT,
    completed_at   TEXT
);

-- Inventory table: per-supplier product inventory
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id TEXT PRIMARY KEY,
    supplier_id  TEXT NOT NULL REFERENCES suppliers(supplier_id),
    item         TEXT NOT NULL,
    category     TEXT NOT NULL,
    stock_qty    INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    reserved_qty INTEGER NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    unit_cost    REAL NOT NULL CHECK (unit_cost >= 0),
    created_at   TEXT NOT NULL DEFAULT (datetime('utcnow')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('utcnow')),
    UNIQUE(supplier_id, item)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_suppliers_category ON suppliers(category);
CREATE INDEX IF NOT EXISTS idx_suppliers_rating ON suppliers(rating DESC);
CREATE INDEX IF NOT EXISTS idx_rfqs_status ON rfqs(status);
CREATE INDEX IF NOT EXISTS idx_rfqs_agent ON rfqs(agent_id);
CREATE INDEX IF NOT EXISTS idx_quotes_rfq ON quotes(rfq_id);
CREATE INDEX IF NOT EXISTS idx_quotes_supplier ON quotes(supplier_id);
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);
CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id);
CREATE INDEX IF NOT EXISTS idx_inventory_supplier ON inventory(supplier_id);
CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category);
