use ring::{
    rand::SystemRandom,
    signature::{Ed25519KeyPair, KeyPair},
};
fn main() {
    let doc = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new())
        .expect("OS secure random generator unavailable");
    let pair = Ed25519KeyPair::from_pkcs8(doc.as_ref()).expect("generated key must parse");
    println!("ATLAS_SCHEDULER_PKCS8_HEX={}", hex::encode(doc.as_ref()));
    println!(
        "ATLAS_SCHEDULER_PUBLIC_KEY_HEX={}",
        hex::encode(pair.public_key().as_ref())
    );
    eprintln!("Keep the PKCS#8 private key secret. Put only the public key in node configuration.");
}
