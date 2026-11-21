CREATE TABLE IF NOT EXISTS nodes (
  node_id TEXT PRIMARY KEY,
  public_key_hex TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at BIGINT NOT NULL,
  last_seen BIGINT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  remote_workloads_allowed BOOLEAN NOT NULL DEFAULT FALSE,
  network_inference_allowed BOOLEAN NOT NULL DEFAULT FALSE,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  revoked_at BIGINT
);
CREATE TABLE IF NOT EXISTS node_challenges (
  node_id TEXT PRIMARY KEY,
  public_key_hex TEXT NOT NULL,
  challenge TEXT NOT NULL,
  expires_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS request_replays (
  fingerprint TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  seen_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS request_replays_seen_idx ON request_replays(seen_at);
CREATE TABLE IF NOT EXISTS workloads (
  workload_id TEXT PRIMARY KEY,
  node_id TEXT,
  image TEXT NOT NULL,
  command JSONB NOT NULL,
  max_memory_mb BIGINT NOT NULL,
  max_cpu_percent INTEGER NOT NULL,
  nonce TEXT NOT NULL UNIQUE,
  state TEXT NOT NULL DEFAULT 'queued',
  created_at BIGINT NOT NULL,
  expires_at BIGINT NOT NULL,
  claimed_at BIGINT,
  completed_at BIGINT,
  receipt JSONB
);
CREATE INDEX IF NOT EXISTS workloads_queue_idx ON workloads(state, created_at);
CREATE INDEX IF NOT EXISTS workloads_node_idx ON workloads(node_id, state);
CREATE TABLE IF NOT EXISTS contribution_receipts (
  receipt_id TEXT PRIMARY KEY,
  workload_id TEXT NOT NULL UNIQUE,
  node_id TEXT NOT NULL,
  receipt JSONB NOT NULL,
  node_signature_valid BOOLEAN NOT NULL,
  execution_success BOOLEAN NOT NULL,
  independently_verified BOOLEAN NOT NULL DEFAULT FALSE,
  billable_units BIGINT NOT NULL DEFAULT 0,
  evidence_reference TEXT,
  verified_at BIGINT,
  received_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS contribution_node_idx ON contribution_receipts(node_id, received_at);
CREATE TABLE IF NOT EXISTS inference_requests (
  request_id TEXT PRIMARY KEY,
  requester_node_id TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt TEXT NOT NULL,
  max_tokens INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued',
  assigned_node_id TEXT,
  response_text TEXT,
  created_at BIGINT NOT NULL,
  updated_at BIGINT NOT NULL
);
