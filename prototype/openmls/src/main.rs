//! Longband OpenMLS lifecycle research fixture.
//!
//! The two-phase commands deliberately keep Bob's endpoint state local:
//! phase one emits an opaque MLS application object plus disposable endpoint
//! state; phase two reloads that state and consumes the exact relay-returned
//! object with OpenMLS.

use openmls::prelude::{tls_codec::*, *};
use openmls_basic_credential::SignatureKeyPair;
use openmls_rust_crypto::OpenMlsRustCrypto;
use openmls_traits::OpenMlsProvider;
use std::{env, fs, io::{self, BufRead, Write}};

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


fn read_value(prefix: &str) -> String {
    let stdin = io::stdin();
    let mut line = String::new();
    stdin.lock().read_line(&mut line).expect("read endpoint command");
    let line = line.trim_end();
    line.strip_prefix(prefix).unwrap_or_else(|| panic!("expected command prefix {prefix}")).to_string()
}

fn emit_value(key: &str, value: &str) {
    println!("{key}={value}");
    io::stdout().flush().expect("flush endpoint response");
}

fn bob_endpoint() {
    let suite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;
    let provider = OpenMlsRustCrypto::default();
    let (bob_credential, bob_signer) = credential(b"bob", suite, &provider);
    let bob_key_package = KeyPackage::builder().build(suite, &provider, &bob_signer, bob_credential).expect("build Bob KeyPackage");
    emit_value("keypackage_hex", &hex(&bob_key_package.key_package().tls_serialize_detached().expect("serialize Bob KeyPackage")));

    let welcome_in = MlsMessageIn::tls_deserialize_exact(unhex(&read_value("welcome_hex="))).expect("deserialize Welcome");
    let welcome = match welcome_in.extract() { MlsMessageBodyIn::Welcome(w) => w, _ => panic!("expected Welcome") };
    let join_config = MlsGroupJoinConfig::builder().use_ratchet_tree_extension(true).build();
    let staged = StagedWelcome::new_from_welcome(&provider, &join_config, welcome, None).expect("stage Bob Welcome");
    let mut bob = staged.into_group(&provider).expect("join Bob to group");
    emit_value("ready", "1");

    let inbound = MlsMessageIn::tls_deserialize_exact(unhex(&read_value("message_hex="))).expect("deserialize relay MLS object");
    let processed = bob.process_message(&provider, inbound.try_into_protocol_message().expect("application protocol message")).expect("Bob failed to process relay-returned MLS object");
    match processed.into_content() {
        ProcessedMessageContent::ApplicationMessage(message) => emit_value("plaintext_hex", &hex(&message.into_bytes())),
        _ => panic!("expected application message"),
    }
}

fn alice_endpoint() {
    let suite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;
    let provider = OpenMlsRustCrypto::default();
    let (alice_credential, alice_signer) = credential(b"alice", suite, &provider);
    let create_config = MlsGroupCreateConfig::builder().ciphersuite(suite).use_ratchet_tree_extension(true).build();
    let mut alice = MlsGroup::new(&provider, &alice_signer, &create_config, alice_credential).expect("create Alice group");

    let keypackage_in = KeyPackageIn::tls_deserialize_exact(unhex(&read_value("keypackage_hex="))).expect("deserialize Bob KeyPackage");
    let bob_key_package = keypackage_in.validate(provider.crypto(), ProtocolVersion::Mls10).expect("validate Bob KeyPackage");
    let (_commit, welcome_out, _) = alice.add_members(&provider, &alice_signer, core::slice::from_ref(&bob_key_package)).expect("add Bob");
    alice.merge_pending_commit(&provider).expect("merge Alice add-member commit");
    emit_value("welcome_hex", &hex(&welcome_out.tls_serialize_detached().expect("serialize Welcome")));

    let plaintext = unhex(&read_value("plaintext_hex="));
    let message = alice.create_message(&provider, &alice_signer, &plaintext).expect("create Alice application message").tls_serialize_detached().expect("serialize Alice application message");
    assert!(!message.windows(plaintext.len()).any(|window| window == plaintext), "serialized MLS object exposed plaintext");
    emit_value("message_hex", &hex(&message));
}

fn make_fixture() -> (OpenMlsRustCrypto, MlsGroup, Vec<u8>, Vec<u8>, Vec<u8>) {
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
    let bob = staged.into_group(&bob_provider).unwrap();
    let plaintext = b"longband alpha real OpenMLS application object".to_vec();
    let outbound = alice.create_message(&alice_provider, &alice_signer, &plaintext).unwrap();
    let message = outbound.tls_serialize_detached().unwrap();
    assert!(!message.windows(plaintext.len()).any(|w| w == plaintext));
    (bob_provider, bob, welcome_bytes, message, plaintext)
}

fn emit_fixture(path: &str) {
    let (_provider, _bob, welcome, message, plaintext) = make_fixture();
    fs::write(path, format!("welcome_hex={}\nmessage_hex={}\nplaintext_hex={}\n", hex(&welcome), hex(&message), hex(&plaintext))).unwrap();
}

fn emit_two_phase(state_path: &str, message_path: &str) {
    let (provider, bob, _welcome, message, plaintext) = make_fixture();
    let mut lines = vec![
        format!("group_id_hex={}", hex(bob.group_id().as_slice())),
        format!("plaintext_hex={}", hex(&plaintext)),
    ];
    let values = provider.storage().values.read().unwrap();
    let mut entries: Vec<_> = values.iter().collect();
    entries.sort_by(|(ka,_),(kb,_)| ka.cmp(kb));
    for (key, value) in entries {
        lines.push(format!("storage_hex={}={}", hex(key), hex(value)));
    }
    drop(values);
    fs::write(state_path, lines.join("\n") + "\n").unwrap();
    fs::write(message_path, hex(&message) + "\n").unwrap();
}

fn consume_two_phase(state_path: &str, message_path: &str) {
    let state = fs::read_to_string(state_path).unwrap();
    let mut group_id = None;
    let mut plaintext = None;
    let provider = OpenMlsRustCrypto::default();
    {
        let mut values = provider.storage().values.write().unwrap();
        for line in state.lines() {
            if let Some(v)=line.strip_prefix("group_id_hex=") { group_id=Some(unhex(v)); }
            else if let Some(v)=line.strip_prefix("plaintext_hex=") { plaintext=Some(unhex(v)); }
            else if let Some(v)=line.strip_prefix("storage_hex=") {
                let (k,val)=v.split_once('=').expect("storage snapshot entry");
                values.insert(unhex(k), unhex(val));
            }
        }
    }
    let group_id = GroupId::from_slice(&group_id.expect("group id"));
    let plaintext = plaintext.expect("plaintext");
    let mut bob = MlsGroup::load(provider.storage(), &group_id).unwrap().expect("Bob group state");
    let message = unhex(fs::read_to_string(message_path).unwrap().trim());
    assert!(!message.windows(plaintext.len()).any(|w| w == plaintext));
    let inbound = MlsMessageIn::tls_deserialize_exact(message).expect("returned bytes must be serialized MLS");
    let processed = bob.process_message(&provider, inbound.try_into_protocol_message().unwrap()).unwrap();
    match processed.into_content() {
        ProcessedMessageContent::ApplicationMessage(m) => assert_eq!(m.into_bytes(), plaintext),
        _ => panic!("expected application message"),
    }
    println!("two-phase OpenMLS endpoint validation passed");
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
        Some("bob-endpoint") => bob_endpoint(),
        Some("alice-endpoint") => alice_endpoint(),
        Some("emit-fixture") => emit_fixture(args.get(2).expect("fixture output path required")),
        Some("verify-relay-object") => verify_message(args.get(2).expect("fixture path required")),
        Some("emit-two-phase") => emit_two_phase(
            args.get(2).expect("endpoint state path required"),
            args.get(3).expect("message output path required"),
        ),
        Some("consume-two-phase") => consume_two_phase(
            args.get(2).expect("endpoint state path required"),
            args.get(3).expect("returned message path required"),
        ),
        _ => println!("longband-openmls-prototype: lifecycle fixture; modes include alice-endpoint and bob-endpoint"),
    }
}
