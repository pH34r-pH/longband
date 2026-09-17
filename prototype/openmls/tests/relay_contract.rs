use openmls::prelude::{tls_codec::*, *};
use openmls_basic_credential::SignatureKeyPair;
use openmls_rust_crypto::OpenMlsRustCrypto;
use openmls_traits::OpenMlsProvider;

fn credential(identity: &[u8], suite: Ciphersuite, provider: &impl OpenMlsProvider) -> (CredentialWithKey, SignatureKeyPair) {
    let credential = BasicCredential::new(identity.to_vec());
    let signer = SignatureKeyPair::new(suite.signature_algorithm()).unwrap();
    signer.store(provider.storage()).unwrap();
    (CredentialWithKey { credential: credential.into(), signature_key: signer.public().into() }, signer)
}

/// Mirrors the public relay's only cryptographic contract: bytes in, identical
/// bytes out. This fixture intentionally has no decrypt method or MLS state.
#[derive(Default)]
struct RelayBoundary { objects: Vec<Vec<u8>> }
impl RelayBoundary {
    fn append(&mut self, payload: Vec<u8>) -> usize { self.objects.push(payload); self.objects.len() - 1 }
    fn read(&self, slot: usize) -> Vec<u8> { self.objects[slot].clone() }
}

#[test]
fn serialized_openmls_application_crosses_opaque_boundary_and_decrypts_only_at_endpoint() {
    let suite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;
    let alice_provider = OpenMlsRustCrypto::default();
    let bob_provider = OpenMlsRustCrypto::default();
    let (alice_credential, alice_signer) = credential(b"alpha-alice", suite, &alice_provider);
    let (bob_credential, bob_signer) = credential(b"alpha-bob", suite, &bob_provider);
    let bob_key_package = KeyPackage::builder().build(suite, &bob_provider, &bob_signer, bob_credential).unwrap();
    let mut alice = MlsGroup::new(&alice_provider, &alice_signer, &MlsGroupCreateConfig::default(), alice_credential).unwrap();
    let (_commit, welcome_out, _group_info) = alice.add_members(&alice_provider, &alice_signer, core::slice::from_ref(bob_key_package.key_package())).unwrap();
    alice.merge_pending_commit(&alice_provider).unwrap();

    let mut relay = RelayBoundary::default();
    let welcome_bytes = welcome_out.tls_serialize_detached().unwrap();
    let welcome_slot = relay.append(welcome_bytes.clone());
    assert_eq!(relay.read(welcome_slot), welcome_bytes);
    let welcome_in = MlsMessageIn::tls_deserialize_exact(relay.read(welcome_slot)).unwrap();
    let welcome = match welcome_in.extract() { MlsMessageBodyIn::Welcome(w) => w, _ => panic!("expected Welcome") };
    let staged = StagedWelcome::new_from_welcome(&bob_provider, &MlsGroupJoinConfig::default(), welcome, Some(alice.export_ratchet_tree().into())).unwrap();
    let mut bob = staged.into_group(&bob_provider).unwrap();

    let plaintext = b"longband alpha operator cannot read this";
    let outbound = alice.create_message(&alice_provider, &alice_signer, plaintext).unwrap();
    let serialized = outbound.tls_serialize_detached().unwrap();
    let slot = relay.append(serialized.clone());
    let captured = relay.read(slot);
    assert_eq!(captured, serialized);
    assert!(!captured.windows(plaintext.len()).any(|w| w == plaintext));

    let inbound = MlsMessageIn::tls_deserialize_exact(captured).unwrap().try_into_protocol_message().unwrap();
    let processed = bob.process_message(&bob_provider, inbound).unwrap();
    match processed.into_content() {
        ProcessedMessageContent::ApplicationMessage(message) => assert_eq!(message.into_bytes(), plaintext),
        _ => panic!("expected application message"),
    }
}
