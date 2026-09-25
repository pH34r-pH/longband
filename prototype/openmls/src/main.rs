//! Longband OpenMLS lifecycle research fixture.
//!
//! With `emit-fixture`, this binary emits endpoint-owned fixture material for
//! the cross-language Alpha integration test. The relay receives only the
//! serialized MLS objects; Bob's provider/group state remains in this process.

use openmls::prelude::{tls_codec::*, *};
use openmls_basic_credential::SignatureKeyPair;
use openmls_rust_crypto::OpenMlsRustCrypto;
use openmls_traits::OpenMlsProvider;
use std::{env, fs};

fn credential(identity: &[u8], suite: Ciphersuite, provider: &impl OpenMlsProvider)
    -> (CredentialWithKey, SignatureKeyPair) {
    let credential = BasicCredential::new(identity.to_vec());
    let signer = SignatureKeyPair::new(suite.signature_algorithm()).unwrap();
    signer.store(provider.storage()).unwrap();
    (CredentialWithKey { credential: credential.into(), signature_key: signer.public().into() }, signer)
}

fn hex(bytes: &[u8]) -> String { bytes.iter().map(|b| format!("{b:02x}")).collect() }
fn unhex(value: &str) -> Vec<u8> {
    assert!(value.len() % 2 == 0);
    (0..value.len()).step_by(2).map(|i| u8::from_str_radix(&value[i..i+2], 16).unwrap()).collect()
}

fn emit_fixture(path: &str) {
    let suite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;
    let alice_provider = OpenMlsRustCrypto::default();
    let bob_provider = OpenMlsRustCrypto::default();
    let (alice_credential, alice_signer) = credential(b"alice", suite, &alice_provider);
    let (bob_credential, bob_signer) = credential(b"bob", suite, &bob_provider);
    let bob_key_package = KeyPackage::builder().build(suite, &bob_provider, &bob_signer, bob_credential).unwrap();
    let mut alice = MlsGroup::new(&alice_provider, &alice_signer, &MlsGroupCreateConfig::default(), alice_credential).unwrap();
    let (_commit, welcome_out, _) = alice.add_members(&alice_provider, &alice_signer, core::slice::from_ref(bob_key_package.key_package())).unwrap();
    alice.merge_pending_commit(&alice_provider).unwrap();
    let welcome_bytes = welcome_out.tls_serialize_detached().unwrap();
    let welcome_in = MlsMessageIn::tls_deserialize_exact(welcome_bytes.clone()).unwrap();
    let welcome = match welcome_in.extract() { MlsMessageBodyIn::Welcome(w) => w, _ => panic!("expected Welcome") };
    let staged = StagedWelcome::new_from_welcome(&bob_provider, &MlsGroupJoinConfig::default(), welcome, Some(alice.export_ratchet_tree().into())).unwrap();
    let mut bob = staged.into_group(&bob_provider).unwrap();
    let plaintext = b"longband alpha real OpenMLS application object";
    let outbound = alice.create_message(&alice_provider, &alice_signer, plaintext).unwrap();
    let message = outbound.tls_serialize_detached().unwrap();
    assert!(!message.windows(plaintext.len()).any(|w| w == plaintext));
    let inbound = MlsMessageIn::tls_deserialize_exact(message.clone()).unwrap();
    let processed = bob.process_message(&bob_provider, inbound.try_into_protocol_message().unwrap()).unwrap();
    match processed.into_content() {
        ProcessedMessageContent::ApplicationMessage(m) => assert_eq!(m.into_bytes(), plaintext),
        _ => panic!("expected application message"),
    }
    fs::write(path, format!("welcome_hex={}\nmessage_hex={}\nplaintext_hex={}\n", hex(&welcome_bytes), hex(&message), hex(plaintext))).unwrap();
}

fn verify_message(path: &str) {
    let text = fs::read_to_string(path).unwrap();
    let mut message = None;
    let mut plaintext = None;
    for line in text.lines() {
        if let Some(v)=line.strip_prefix("message_hex=") { message=Some(unhex(v)); }
        if let Some(v)=line.strip_prefix("plaintext_hex=") { plaintext=Some(unhex(v)); }
    }
    let message=message.unwrap(); let plaintext=plaintext.unwrap();
    assert!(!message.windows(plaintext.len()).any(|w| w == plaintext));
    MlsMessageIn::tls_deserialize_exact(message).expect("relay bytes must remain a serialized MLS object");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("emit-fixture") => emit_fixture(args.get(2).expect("fixture output path required")),
        Some("verify-relay-object") => verify_message(args.get(2).expect("fixture path required")),
        _ => println!("longband-openmls-prototype: lifecycle fixture; not for production"),
    }
}
