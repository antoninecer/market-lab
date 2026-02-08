PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  asof_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  universe TEXT NOT NULL,         -- JSON string: ["SPY","QQQ",...]
  source_dir TEXT NOT NULL,       -- např. data/processed_sanitized
  notes TEXT
);

CREATE TABLE IF NOT EXISTS market_daily (
  asof_date TEXT NOT NULL,
  asset TEXT NOT NULL,
  close REAL NOT NULL,
  ret_1d REAL,                    -- může být NULL pro první den
  PRIMARY KEY (asof_date, asset)
);

CREATE TABLE IF NOT EXISTS baseline_equity (
  asof_date TEXT PRIMARY KEY,
  equity REAL NOT NULL,
  cash REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS baseline_positions (
  asof_date TEXT NOT NULL,
  asset TEXT NOT NULL,
  qty REAL NOT NULL,
  value REAL NOT NULL,
  PRIMARY KEY (asof_date, asset)
);

CREATE TABLE IF NOT EXISTS baseline_trades (
  asof_date TEXT NOT NULL,
  asset TEXT NOT NULL,
  side TEXT NOT NULL,             -- BUY/SELL
  qty REAL NOT NULL,
  price REAL NOT NULL,
  notional REAL NOT NULL,
  fee_total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_state (
  asof_date TEXT NOT NULL,
  asset TEXT NOT NULL,
  state TEXT NOT NULL,            -- NORMAL/ARMED/EXIT
  reason TEXT,
  score REAL,                     -- pro ML později
  PRIMARY KEY (asof_date, asset)
);

-- Pro LM Studio export / učení:
CREATE TABLE IF NOT EXISTS learning_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  asset TEXT NOT NULL,
  event_type TEXT NOT NULL,       -- ENTRY/EXIT/ARMED/NOTE/RESULT
  payload TEXT NOT NULL           -- JSON string
);

