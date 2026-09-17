use openmls::prelude::{tls_codec::*, *};
use openmls_basic_credential::SignatureKeyPair;
use openmls_rust_crypto::OpenMlsRustCrypto;
use openmls_traits::OpenMlsProvider;

fn credential(
    identity: &[u8],
    suite: Ciphersuite,
    provider: &impl OpenMlsProvider,
) -> (CredentialWithKey, SignatureKeyPair) {
    let credential = BasicCredential::new(identity.to_vec());
    let signer = SignatureKeyPair::new(suite.signature_algorithm()).unwrap();
    signer.store(provider.storage()).unwrap();
    (
        CredentialWithKey {
            credential: credential.into(),
            signature_key: signer.public().into(),
        },
        signer,
    )
}

#[derive(Default)]
struct OpaqueRelay {
    objects: Vec<Vec<u8>>,
}

impl OpaqueRelay {
    fn put(&mut self, bytes: Vec<u8>) -> usize {
        self.objects.push(bytes);
        self.objects.len() - 1
    }

    fn get(&self, index: usize) -> &[u8] {
        &self.objects[index]
    }
}

#[test]
fn two_party_message_crosses_ciphertext_only_relay() {
    let suite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;
    let alice_provider = OpenMlsRustCrypto::default();
    let bob_provider = OpenMlsRustCrypto::default();
    let (alice_credential, alice_signer) = credential(b"alice", suite, &alice_provider);
    let (bob_credential, bob_signer) = credential(b"bob", suite, &bob_provider);

    let bob_key_package = KeyPackage::builder()
        .build(suite, &bob_provider, &bob_signer, bob_credential)
        .unwrap();

    let mut alice = MlsGroup::new(
        &alice_provider,
        &alice_signer,
        &MlsGroupCreateConfig::default(),
        alice_credential,
    )
    .unwrap();

    let (_commit, welcome_out, _group_info) = alice
        .add_members(
            &alice_provider,
            &alice_signer,
            core::slice::from_ref(bob_key_package.key_package()),
        )
        .unwrap();
    alice.merge_pending_commit(&alice_provider).unwrap();

    let mut relay = OpaqueRelay::default();
    let welcome_slot = relay.put(welcome_out.tls_serialize_detached().unwrap());
    let welcome_in = MlsMessageIn::tls_deserialize_exact(relay.get(welcome_slot).to_vec()).unwrap();
    let welcome = match welcome_in.extract() {
        MlsMessageBodyIn::Welcome(welcome) => welcome,
        _ => panic!("relay object is not a Welcome"),
    };
    let staged = StagedWelcome::new_from_welcome(
        &bob_provider,
        &MlsGroupJoinConfig::default(),
        welcome,
        Some(alice.export_ratchet_tree().into()),
    )
    .unwrap();
    let mut bob = staged.into_group(&bob_provider).unwrap();

    let plaintext = b"longband relay must not see this plaintext";
    let outbound = alice
        .create_message(&alice_provider, &alice_signer, plaintext)
        .unwrap();
    let message_slot = relay.put(outbound.tls_serialize_detached().unwrap());

    assert!(!relay.get(message_slot).windows(plaintext.len()).any(|w| w == plaintext));

    let inbound = MlsMessageIn::tls_deserialize_exact(relay.get(message_slot).to_vec()).unwrap();
    let protocol = inbound.try_into_protocol_message().unwrap();
    let processed = bob.process_message(&bob_provider, protocol).unwrap();
    match processed.into_content() {
        ProcessedMessageContent::ApplicationMessage(message) => {
            assert_eq!(message.into_bytes(), plaintext)
        }
        _ => panic!("expected application message"),
    }
}
