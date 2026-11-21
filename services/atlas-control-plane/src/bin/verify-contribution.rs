// Deliberately not a standalone verifier. Contribution verification is an operator workflow
// performed through the authenticated control-plane API after inspecting independent evidence.
fn main() {
    eprintln!("Use POST /v1/operator/contributions/:receipt_id/verify with an evidence reference after independent review.");
}
