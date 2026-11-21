use axum::{
    body::Bytes,
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use ring::{
    digest,
    rand::{SecureRandom, SystemRandom},
    signature::{Ed25519KeyPair, KeyPair, UnparsedPublicKey, ED25519},
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::{postgres::PgPoolOptions, PgPool, Row};
use std::{
    env,
    net::SocketAddr,
    time::{SystemTime, UNIX_EPOCH},
};
use tower_http::{limit::RequestBodyLimitLayer, trace::TraceLayer};
use uuid::Uuid;

#[derive(Clone)]
struct AppState {
    db: PgPool,
    scheduler_pkcs8: std::sync::Arc<Vec<u8>>,
    scheduler_public_hex: String,
    admin_key: String,
}
#[derive(Deserialize)]
struct ChallengeRequest {
    node_id: String,
    public_key_hex: String,
}
#[derive(Deserialize)]
struct RegisterRequest {
    node_id: String,
    public_key_hex: String,
    challenge: String,
    signature_hex: String,
}
#[derive(Deserialize)]
struct WorkloadCreate {
    image: String,
    command: Vec<String>,
    max_memory_mb: u64,
    max_cpu_percent: u8,
    ttl_seconds: Option<u64>,
}
#[derive(Deserialize)]
struct InferenceCreate {
    model: String,
    prompt: String,
    max_tokens: u32,
}
#[derive(Deserialize)]
struct ContributionReview {
    evidence_reference: String,
    billable_units: u64,
}
#[derive(Serialize)]
struct ApiError {
    error: String,
}
fn now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64
}
fn err(status: StatusCode, message: impl Into<String>) -> (StatusCode, Json<ApiError>) {
    (
        status,
        Json(ApiError {
            error: message.into(),
        }),
    )
}
fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(digest::digest(&digest::SHA256, bytes).as_ref())
}
fn node_id_for_public_key(public_key: &[u8]) -> String {
    sha256_hex(public_key)
}
fn verify_ed25519(public_key: &[u8], message: &[u8], signature: &[u8]) -> bool {
    UnparsedPublicKey::new(&ED25519, public_key)
        .verify(message, signature)
        .is_ok()
}
fn random_hex(bytes: usize) -> Result<String, String> {
    let mut out = vec![0u8; bytes];
    SystemRandom::new()
        .fill(&mut out)
        .map_err(|_| "secure random generation failed".to_string())?;
    Ok(hex::encode(out))
}
fn scheduler_sign(state: &AppState, value: &Value) -> Result<String, String> {
    let bytes = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    let pair = Ed25519KeyPair::from_pkcs8(state.scheduler_pkcs8.as_slice())
        .map_err(|_| "scheduler signing key became invalid".to_string())?;
    Ok(hex::encode(pair.sign(&bytes).as_ref()))
}

async fn health() -> Json<Value> {
    Json(json!({"status":"ok","service":"atlas-control-plane","api_version":"v1"}))
}
async fn scheduler_public_key(State(s): State<AppState>) -> Json<Value> {
    Json(
        json!({"algorithm":"Ed25519","public_key_hex":s.scheduler_public_hex,"key_id":sha256_hex(s.scheduler_public_hex.as_bytes())}),
    )
}
async fn network_status(State(s): State<AppState>) -> Json<Value> {
    let online: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM nodes WHERE revoked_at IS NULL AND enabled=TRUE AND last_seen > $1",
    )
    .bind(now() - 60)
    .fetch_one(&s.db)
    .await
    .unwrap_or(0);
    let queued: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workloads WHERE state='queued' AND expires_at > $1",
    )
    .bind(now())
    .fetch_one(&s.db)
    .await
    .unwrap_or(0);
    Json(
        json!({"available":true,"online_nodes":online,"queued_workloads":queued,"scheduler_public_key_hex":s.scheduler_public_hex,"distributed_inference":"queue API available; node-side inference worker is a separate rollout gate","settlement":"cryptographic receipt intake enabled; independent compute verification and payouts disabled"}),
    )
}
async fn node_challenge(
    State(s): State<AppState>,
    Json(req): Json<ChallengeRequest>,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    let pk = hex::decode(&req.public_key_hex)
        .map_err(|_| err(StatusCode::BAD_REQUEST, "public_key_hex must be valid hex"))?;
    if pk.len() != 32 || node_id_for_public_key(&pk) != req.node_id {
        return Err(err(
            StatusCode::BAD_REQUEST,
            "node_id must be SHA-256 of the Ed25519 public key",
        ));
    }
    let challenge = random_hex(32).map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    sqlx::query("INSERT INTO node_challenges(node_id,public_key_hex,challenge,expires_at) VALUES($1,$2,$3,$4) ON CONFLICT(node_id) DO UPDATE SET public_key_hex=EXCLUDED.public_key_hex, challenge=EXCLUDED.challenge, expires_at=EXCLUDED.expires_at")
        .bind(&req.node_id).bind(&req.public_key_hex).bind(&challenge).bind(now()+300).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    Ok(Json(
        json!({"challenge":challenge,"expires_in_seconds":300}),
    ))
}
async fn node_register(
    State(s): State<AppState>,
    Json(req): Json<RegisterRequest>,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    let row = sqlx::query(
        "SELECT public_key_hex,challenge,expires_at FROM node_challenges WHERE node_id=$1",
    )
    .bind(&req.node_id)
    .fetch_optional(&s.db)
    .await
    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .ok_or_else(|| err(StatusCode::UNAUTHORIZED, "challenge not found"))?;
    let pk_hex: String = row
        .try_get("public_key_hex")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let challenge: String = row
        .try_get("challenge")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let expires: i64 = row
        .try_get("expires_at")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    if expires < now() || challenge != req.challenge || pk_hex != req.public_key_hex {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "challenge expired or does not match",
        ));
    }
    let pk =
        hex::decode(&pk_hex).map_err(|_| err(StatusCode::BAD_REQUEST, "invalid public key"))?;
    let sig = hex::decode(&req.signature_hex)
        .map_err(|_| err(StatusCode::BAD_REQUEST, "invalid signature encoding"))?;
    if !verify_ed25519(&pk, challenge.as_bytes(), &sig) {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "node proof-of-possession failed",
        ));
    }
    if node_id_for_public_key(&pk) != req.node_id {
        return Err(err(StatusCode::BAD_REQUEST, "node identity mismatch"));
    }
    let token = random_hex(32).map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    sqlx::query("INSERT INTO nodes(node_id,public_key_hex,token_hash,created_at,last_seen) VALUES($1,$2,$3,$4,$4) ON CONFLICT(node_id) DO UPDATE SET public_key_hex=EXCLUDED.public_key_hex,token_hash=EXCLUDED.token_hash,last_seen=EXCLUDED.last_seen,revoked_at=NULL")
        .bind(&req.node_id).bind(&pk_hex).bind(sha256_hex(token.as_bytes())).bind(now()).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    sqlx::query("DELETE FROM node_challenges WHERE node_id=$1")
        .bind(&req.node_id)
        .execute(&s.db)
        .await
        .ok();
    Ok(Json(
        json!({"registered":true,"node_id":req.node_id,"node_token":token,"message":"Node registered. Owner consent and workload permissions remain off by default."}),
    ))
}

async fn authenticate(
    s: &AppState,
    headers: &HeaderMap,
    path: &str,
    body: &[u8],
) -> Result<String, (StatusCode, Json<ApiError>)> {
    let node_id = headers
        .get("x-atlas-node-id")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let ts = headers
        .get("x-atlas-timestamp")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.parse::<i64>().ok())
        .ok_or_else(|| {
            err(
                StatusCode::UNAUTHORIZED,
                "missing or invalid request timestamp",
            )
        })?;
    let signature = headers
        .get("x-atlas-signature")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let bearer = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .unwrap_or("");
    if node_id.is_empty() || bearer.len() < 32 || signature.is_empty() {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "node authentication headers are required",
        ));
    }
    if (now() - ts).abs() > 90 {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "signed request timestamp outside allowed clock skew",
        ));
    }
    let row =
        sqlx::query("SELECT public_key_hex,token_hash,revoked_at FROM nodes WHERE node_id=$1")
            .bind(node_id)
            .fetch_optional(&s.db)
            .await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
            .ok_or_else(|| err(StatusCode::UNAUTHORIZED, "unknown node"))?;
    let pk_hex: String = row
        .try_get("public_key_hex")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let token_hash: String = row
        .try_get("token_hash")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let revoked: Option<i64> = row
        .try_get("revoked_at")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    if revoked.is_some() || sha256_hex(bearer.as_bytes()) != token_hash {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "node credential invalid or revoked",
        ));
    }
    let body_hash = sha256_hex(body);
    let message = format!("{ts}.POST.{path}.{body_hash}");
    let pk = hex::decode(pk_hex).map_err(|_| {
        err(
            StatusCode::INTERNAL_SERVER_ERROR,
            "stored node key malformed",
        )
    })?;
    let sig = hex::decode(signature)
        .map_err(|_| err(StatusCode::UNAUTHORIZED, "signature encoding invalid"))?;
    if !verify_ed25519(&pk, message.as_bytes(), &sig) {
        return Err(err(StatusCode::UNAUTHORIZED, "request signature invalid"));
    }
    let fingerprint = sha256_hex(format!("{node_id}:{ts}:{signature}").as_bytes());
    sqlx::query("INSERT INTO request_replays(fingerprint,node_id,seen_at) VALUES($1,$2,$3)")
        .bind(fingerprint)
        .bind(node_id)
        .bind(now())
        .execute(&s.db)
        .await
        .map_err(|e| {
            err(
                StatusCode::CONFLICT,
                format!("request replay rejected: {e}"),
            )
        })?;
    Ok(node_id.to_string())
}
async fn node_heartbeat(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<impl IntoResponse, (StatusCode, Json<ApiError>)> {
    let node_id = authenticate(&s, &headers, "/v1/nodes/heartbeat", &body).await?;
    let v: Value = serde_json::from_slice(&body)
        .map_err(|_| err(StatusCode::BAD_REQUEST, "invalid JSON body"))?;
    let enabled = v.get("enabled").and_then(Value::as_bool).unwrap_or(false);
    let remote = v
        .get("remote_workloads_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let inference = v
        .get("network_inference_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    sqlx::query("UPDATE nodes SET last_seen=$2,enabled=$3,remote_workloads_allowed=$4,network_inference_allowed=$5,metrics=$6 WHERE node_id=$1")
        .bind(&node_id).bind(now()).bind(enabled).bind(enabled&&remote).bind(enabled&&inference).bind(v).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    Ok((StatusCode::NO_CONTENT, ()))
}
async fn claim_workload(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<impl IntoResponse, (StatusCode, Json<ApiError>)> {
    let node_id = authenticate(&s, &headers, "/v1/workloads/claim", &body).await?;
    let mut tx =
        s.db.begin()
            .await
            .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let eligible:bool=sqlx::query_scalar("SELECT enabled AND remote_workloads_allowed AND revoked_at IS NULL AND last_seen > $2 FROM nodes WHERE node_id=$1").bind(&node_id).bind(now()-60).fetch_one(&mut *tx).await.unwrap_or(false);
    if !eligible {
        tx.rollback().await.ok();
        return Err(err(
            StatusCode::FORBIDDEN,
            "node is not currently eligible for remote workloads",
        ));
    }
    let row=sqlx::query("SELECT workload_id,image,command,max_memory_mb,max_cpu_percent,expires_at,nonce FROM workloads WHERE state='queued' AND expires_at>$1 ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1").bind(now()).fetch_optional(&mut *tx).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    let Some(row) = row else {
        tx.rollback().await.ok();
        return Ok(StatusCode::NO_CONTENT.into_response());
    };
    let id: String = row
        .try_get("workload_id")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let image: String = row
        .try_get("image")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let command: Value = row
        .try_get("command")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let memory: i64 = row
        .try_get("max_memory_mb")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let cpu: i32 = row
        .try_get("max_cpu_percent")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let expires: i64 = row
        .try_get("expires_at")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let nonce: String = row
        .try_get("nonce")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let canonical = json!({"workload_id":id,"image":image,"command":command,"max_memory_mb":memory as u64,"max_cpu_percent":cpu as u8,"expires_at_unix":expires as u64,"nonce":nonce});
    let sig =
        scheduler_sign(&s, &canonical).map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let mut envelope = canonical;
    envelope["signature_hex"] = json!(sig);
    sqlx::query(
        "UPDATE workloads SET state='claimed',node_id=$2,claimed_at=$3 WHERE workload_id=$1",
    )
    .bind(&id)
    .bind(&node_id)
    .bind(now())
    .execute(&mut *tx)
    .await
    .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    tx.commit()
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(json!({"workload":envelope})).into_response())
}
async fn complete_workload(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    let node_id = authenticate(&s, &headers, "/v1/workloads/complete", &body).await?;
    let v: Value =
        serde_json::from_slice(&body).map_err(|_| err(StatusCode::BAD_REQUEST, "invalid JSON"))?;
    let mut receipt = v
        .get("receipt")
        .cloned()
        .ok_or_else(|| err(StatusCode::BAD_REQUEST, "receipt required"))?;
    if receipt.get("node_id").and_then(Value::as_str) != Some(&node_id) {
        return Err(err(
            StatusCode::FORBIDDEN,
            "receipt node does not match authenticated node",
        ));
    }
    let sig_hex = receipt
        .get("node_signature_hex")
        .and_then(Value::as_str)
        .ok_or_else(|| err(StatusCode::BAD_REQUEST, "node receipt signature missing"))?
        .to_string();
    receipt
        .as_object_mut()
        .unwrap()
        .remove("node_signature_hex");
    let row = sqlx::query("SELECT public_key_hex FROM nodes WHERE node_id=$1")
        .bind(&node_id)
        .fetch_one(&s.db)
        .await
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let pk_hex: String = row
        .try_get("public_key_hex")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let pk = hex::decode(pk_hex).map_err(|_| {
        err(
            StatusCode::INTERNAL_SERVER_ERROR,
            "stored public key invalid",
        )
    })?;
    let sig = hex::decode(sig_hex)
        .map_err(|_| err(StatusCode::BAD_REQUEST, "receipt signature malformed"))?;
    let canonical =
        serde_json::to_vec(&receipt).map_err(|e| err(StatusCode::BAD_REQUEST, e.to_string()))?;
    if !verify_ed25519(&pk, &canonical, &sig) {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "node receipt signature invalid",
        ));
    }
    let workload_id = receipt
        .get("workload_id")
        .and_then(Value::as_str)
        .ok_or_else(|| err(StatusCode::BAD_REQUEST, "workload_id missing"))?;
    let success = receipt.get("state").and_then(Value::as_str) == Some("executed_unverified")
        && receipt.get("exit_code").and_then(Value::as_i64) == Some(0);
    let updated=sqlx::query("UPDATE workloads SET state=$3,completed_at=$4,receipt=$5 WHERE workload_id=$1 AND node_id=$2 AND state='claimed'")
        .bind(workload_id).bind(&node_id).bind(if success{"completed_unverified"}else{"failed"}).bind(now()).bind(&receipt).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    if updated.rows_affected() != 1 {
        return Err(err(
            StatusCode::CONFLICT,
            "workload is not assigned to this node or already completed",
        ));
    }
    sqlx::query("INSERT INTO contribution_receipts(receipt_id,workload_id,node_id,receipt,node_signature_valid,execution_success,independently_verified,billable_units,received_at) VALUES($1,$2,$3,$4,TRUE,$5,FALSE,0,$6)")
        .bind(Uuid::new_v4().to_string()).bind(workload_id).bind(&node_id).bind(&receipt).bind(success).bind(now()).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    Ok(Json(
        json!({"accepted":true,"node_signature_valid":true,"execution_success":success,"independently_verified":false,"billable_units":0,"settlement":"not payable until independent verification is implemented"}),
    ))
}
async fn create_workload(
    State(s): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<WorkloadCreate>,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    if headers
        .get("x-atlas-admin-key")
        .and_then(|v| v.to_str().ok())
        != Some(s.admin_key.as_str())
    {
        return Err(err(StatusCode::UNAUTHORIZED, "operator key required"));
    }
    if !req.image.contains("@sha256:")
        || req.image.contains(":latest")
        || req.command.is_empty()
        || req.command.len() > 64
        || req.max_memory_mb < 256
        || req.max_cpu_percent == 0
        || req.max_cpu_percent > 100
    {
        return Err(err(
            StatusCode::BAD_REQUEST,
            "workload violates immutable-image, command or resource policy",
        ));
    }
    let id = Uuid::new_v4().to_string();
    let nonce = random_hex(24).map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let ttl = req.ttl_seconds.unwrap_or(900).clamp(30, 3600) as i64;
    sqlx::query("INSERT INTO workloads(workload_id,image,command,max_memory_mb,max_cpu_percent,nonce,created_at,expires_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8)")
        .bind(&id).bind(&req.image).bind(json!(req.command)).bind(req.max_memory_mb as i64).bind(req.max_cpu_percent as i32).bind(&nonce).bind(now()).bind(now()+ttl).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    Ok(Json(
        json!({"workload_id":id,"state":"queued","expires_in_seconds":ttl,"note":"Node must independently allow this exact image digest and workload execution."}),
    ))
}
async fn create_inference(
    State(s): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    let node_id = authenticate(&s, &headers, "/v1/inference", &body).await?;
    let req: InferenceCreate = serde_json::from_slice(&body)
        .map_err(|_| err(StatusCode::BAD_REQUEST, "invalid inference request"))?;
    if req.model.trim().is_empty() || req.prompt.trim().is_empty() || req.prompt.len() > 100_000 {
        return Err(err(
            StatusCode::BAD_REQUEST,
            "model and prompt are required; prompt limit is 100KB",
        ));
    }
    let eligible:bool=sqlx::query_scalar("SELECT enabled AND network_inference_allowed AND revoked_at IS NULL FROM nodes WHERE node_id=$1").bind(&node_id).fetch_one(&s.db).await.unwrap_or(false);
    if !eligible {
        return Err(err(
            StatusCode::FORBIDDEN,
            "network inference is not enabled for this node identity",
        ));
    }
    let id = Uuid::new_v4().to_string();
    sqlx::query("INSERT INTO inference_requests(request_id,requester_node_id,model,prompt,max_tokens,created_at,updated_at) VALUES($1,$2,$3,$4,$5,$6,$6)")
        .bind(&id).bind(&node_id).bind(req.model).bind(req.prompt).bind(req.max_tokens.clamp(1,8192) as i32).bind(now()).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    Ok(Json(
        json!({"request_id":id,"state":"queued","message":"Inference request accepted into the network queue. Worker dispatch and response streaming are not enabled in this control-plane release."}),
    ))
}
async fn workload_status(
    State(s): State<AppState>,
    Path(id): Path<String>,
    headers: HeaderMap,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    if headers
        .get("x-atlas-admin-key")
        .and_then(|v| v.to_str().ok())
        != Some(s.admin_key.as_str())
    {
        return Err(err(StatusCode::UNAUTHORIZED, "operator key required"));
    }
    let row=sqlx::query("SELECT workload_id,state,node_id,created_at,expires_at,completed_at FROM workloads WHERE workload_id=$1").bind(id).fetch_optional(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?.ok_or_else(||err(StatusCode::NOT_FOUND,"workload not found"))?;
    Ok(Json(
        json!({"workload_id":row.try_get::<String,_>("workload_id").unwrap_or_default(),"state":row.try_get::<String,_>("state").unwrap_or_default(),"node_id":row.try_get::<Option<String>,_>("node_id").unwrap_or(None),"created_at":row.try_get::<i64,_>("created_at").unwrap_or_default(),"expires_at":row.try_get::<i64,_>("expires_at").unwrap_or_default(),"completed_at":row.try_get::<Option<i64>,_>("completed_at").unwrap_or(None)}),
    ))
}
async fn operator_nodes(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    if headers
        .get("x-atlas-admin-key")
        .and_then(|v| v.to_str().ok())
        != Some(s.admin_key.as_str())
    {
        return Err(err(StatusCode::UNAUTHORIZED, "operator key required"));
    }
    let rows=sqlx::query("SELECT node_id,created_at,last_seen,enabled,remote_workloads_allowed,network_inference_allowed,metrics,revoked_at FROM nodes ORDER BY last_seen DESC LIMIT 500").fetch_all(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    let nodes:Vec<Value>=rows.into_iter().map(|r|json!({"node_id":r.try_get::<String,_>("node_id").unwrap_or_default(),"created_at":r.try_get::<i64,_>("created_at").unwrap_or_default(),"last_seen":r.try_get::<i64,_>("last_seen").unwrap_or_default(),"enabled":r.try_get::<bool,_>("enabled").unwrap_or(false),"remote_workloads_allowed":r.try_get::<bool,_>("remote_workloads_allowed").unwrap_or(false),"network_inference_allowed":r.try_get::<bool,_>("network_inference_allowed").unwrap_or(false),"metrics":r.try_get::<Value,_>("metrics").unwrap_or(json!({})),"revoked":r.try_get::<Option<i64>,_>("revoked_at").unwrap_or(None).is_some()})).collect();
    Ok(Json(json!({"nodes":nodes})))
}

async fn operator_contributions(
    State(s): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    if headers
        .get("x-atlas-admin-key")
        .and_then(|v| v.to_str().ok())
        != Some(s.admin_key.as_str())
    {
        return Err(err(StatusCode::UNAUTHORIZED, "operator key required"));
    }
    let rows=sqlx::query("SELECT receipt_id,workload_id,node_id,receipt,node_signature_valid,execution_success,independently_verified,billable_units,received_at FROM contribution_receipts ORDER BY received_at DESC LIMIT 1000").fetch_all(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    let receipts:Vec<Value>=rows.into_iter().map(|r|json!({"receipt_id":r.try_get::<String,_>("receipt_id").unwrap_or_default(),"workload_id":r.try_get::<String,_>("workload_id").unwrap_or_default(),"node_id":r.try_get::<String,_>("node_id").unwrap_or_default(),"receipt":r.try_get::<Value,_>("receipt").unwrap_or(json!({})),"node_signature_valid":r.try_get::<bool,_>("node_signature_valid").unwrap_or(false),"execution_success":r.try_get::<bool,_>("execution_success").unwrap_or(false),"independently_verified":r.try_get::<bool,_>("independently_verified").unwrap_or(false),"billable_units":r.try_get::<i64,_>("billable_units").unwrap_or(0),"received_at":r.try_get::<i64,_>("received_at").unwrap_or_default()})).collect();
    Ok(Json(
        json!({"receipts":receipts,"warning":"Node signatures prove receipt origin, not physical compute. Only independently reviewed evidence may be marked verified."}),
    ))
}
async fn operator_verify_contribution(
    State(s): State<AppState>,
    Path(receipt_id): Path<String>,
    headers: HeaderMap,
    Json(review): Json<ContributionReview>,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    if headers
        .get("x-atlas-admin-key")
        .and_then(|v| v.to_str().ok())
        != Some(s.admin_key.as_str())
    {
        return Err(err(StatusCode::UNAUTHORIZED, "operator key required"));
    }
    if review.evidence_reference.trim().is_empty()
        || review.evidence_reference.len() > 2048
        || review.billable_units == 0
        || review.billable_units > 10_000_000
    {
        return Err(err(
            StatusCode::BAD_REQUEST,
            "a bounded evidence reference and positive bounded billable_units are required",
        ));
    }
    let row=sqlx::query("SELECT execution_success,node_signature_valid FROM contribution_receipts WHERE receipt_id=$1").bind(&receipt_id).fetch_optional(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?.ok_or_else(||err(StatusCode::NOT_FOUND,"contribution receipt not found"))?;
    let success: bool = row
        .try_get("execution_success")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let signature_valid: bool = row
        .try_get("node_signature_valid")
        .map_err(|e| err(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    if !success || !signature_valid {
        return Err(err(
            StatusCode::CONFLICT,
            "failed or unauthenticated execution cannot be verified",
        ));
    }
    sqlx::query("UPDATE contribution_receipts SET independently_verified=TRUE,billable_units=$2,evidence_reference=$3,verified_at=$4 WHERE receipt_id=$1").bind(&receipt_id).bind(review.billable_units as i64).bind(&review.evidence_reference).bind(now()).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    tracing::warn!(%receipt_id,evidence=%review.evidence_reference,"operator marked contribution independently verified; external evidence retention is the operator's responsibility");
    Ok(Json(
        json!({"receipt_id":receipt_id,"independently_verified":true,"billable_units":review.billable_units,"payment_status":"not_paid; settlement and payment integration are not implemented"}),
    ))
}
async fn operator_revoke_node(
    State(s): State<AppState>,
    Path(node_id): Path<String>,
    headers: HeaderMap,
) -> Result<Json<Value>, (StatusCode, Json<ApiError>)> {
    if headers
        .get("x-atlas-admin-key")
        .and_then(|v| v.to_str().ok())
        != Some(s.admin_key.as_str())
    {
        return Err(err(StatusCode::UNAUTHORIZED, "operator key required"));
    }
    let result=sqlx::query("UPDATE nodes SET revoked_at=$2,enabled=FALSE,remote_workloads_allowed=FALSE,network_inference_allowed=FALSE WHERE node_id=$1 AND revoked_at IS NULL").bind(&node_id).bind(now()).execute(&s.db).await.map_err(|e|err(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()))?;
    if result.rows_affected() != 1 {
        return Err(err(StatusCode::NOT_FOUND, "active node not found"));
    }
    Ok(Json(json!({"node_id":node_id,"revoked":true})))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            env::var("RUST_LOG")
                .unwrap_or_else(|_| "atlas_control_plane=info,tower_http=info".into()),
        )
        .init();
    let database_url = env::var("DATABASE_URL")?;
    let admin_key = env::var("ATLAS_ADMIN_KEY")?;
    if admin_key.len() < 32 {
        return Err("ATLAS_ADMIN_KEY must be at least 32 characters".into());
    }
    let pkcs8 = hex::decode(env::var("ATLAS_SCHEDULER_PKCS8_HEX")?)?;
    let scheduler = Ed25519KeyPair::from_pkcs8(&pkcs8)
        .map_err(|_| "ATLAS_SCHEDULER_PKCS8_HEX is not a valid Ed25519 PKCS#8 key")?;
    let scheduler_public_hex = hex::encode(scheduler.public_key().as_ref());
    let scheduler_pkcs8 = std::sync::Arc::new(pkcs8);
    let db = PgPoolOptions::new()
        .max_connections(20)
        .connect(&database_url)
        .await?;
    sqlx::migrate!().run(&db).await?;
    let state = AppState {
        db,
        scheduler_pkcs8,
        scheduler_public_hex,
        admin_key,
    };
    let app = Router::new()
        .route("/healthz", get(health))
        .route("/v1/scheduler/public-key", get(scheduler_public_key))
        .route("/v1/network/status", get(network_status))
        .route("/v1/nodes/challenge", post(node_challenge))
        .route("/v1/nodes/register", post(node_register))
        .route("/v1/nodes/heartbeat", post(node_heartbeat))
        .route("/v1/workloads/claim", post(claim_workload))
        .route("/v1/workloads/complete", post(complete_workload))
        .route("/v1/operator/workloads", post(create_workload))
        .route("/v1/operator/workloads/:id", get(workload_status))
        .route("/v1/operator/nodes", get(operator_nodes))
        .route(
            "/v1/operator/nodes/:node_id/revoke",
            post(operator_revoke_node),
        )
        .route("/v1/operator/contributions", get(operator_contributions))
        .route(
            "/v1/operator/contributions/:receipt_id/verify",
            post(operator_verify_contribution),
        )
        .route("/v1/inference", post(create_inference))
        .with_state(state)
        .layer(RequestBodyLimitLayer::new(128 * 1024))
        .layer(TraceLayer::new_for_http());
    let addr: SocketAddr = env::var("ATLAS_BIND")
        .unwrap_or_else(|_| "127.0.0.1:8181".into())
        .parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(%addr,"Atlas Control Plane listening");
    axum::serve(listener, app).await?;
    Ok(())
}
