use openmls::prelude::{tls_codec::*, *};
use openmls_basic_credential::SignatureKeyPair;
use openmls_rust_crypto::OpenMlsRustCrypto;
use openmls_traits::OpenMlsProvider;
use serde_json::Value;

const CORPUS: &str = include_str!("../../../protocol/vectors/state-v1.json");
const SUITE: Ciphersuite = Ciphersuite::MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519;

fn corpus() -> Value {
    serde_json::from_str(CORPUS).expect("versioned protocol corpus")
}

fn assert_vector(id: &str, observed: &[&str]) {
    let vectors = corpus();
    let case = vectors["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|case| case["id"] == id)
        .unwrap_or_else(|| panic!("missing protocol case {id}"));
    assert!(case["owner"] == "openmls" || case["owner"] == "shared");
    assert_eq!(case["expect"], serde_json::json!(observed), "{id}");
}

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

struct GroupPair {
    alice_provider: OpenMlsRustCrypto,
    bob_provider: OpenMlsRustCrypto,
    alice_signer: SignatureKeyPair,
    bob_signer: SignatureKeyPair,
    alice: MlsGroup,
    bob: MlsGroup,
    relay: OpaqueRelay,
}

fn joined_pair() -> GroupPair {
    let alice_provider = OpenMlsRustCrypto::default();
    let bob_provider = OpenMlsRustCrypto::default();
    let (alice_credential, alice_signer) = credential(b"alice", SUITE, &alice_provider);
    let (bob_credential, bob_signer) = credential(b"bob", SUITE, &bob_provider);

    let bob_key_package = KeyPackage::builder()
        .build(SUITE, &bob_provider, &bob_signer, bob_credential)
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
    let bob = staged.into_group(&bob_provider).unwrap();
    GroupPair {
        alice_provider,
        bob_provider,
        alice_signer,
        bob_signer,
        alice,
        bob,
        relay,
    }
}

fn protocol_message(bytes: &[u8]) -> ProtocolMessage {
    MlsMessageIn::tls_deserialize_exact(bytes)
        .unwrap()
        .try_into_protocol_message()
        .unwrap()
}

impl GroupPair {
    fn application(&mut self, plaintext: &[u8]) -> Vec<u8> {
        self.alice
            .create_message(&self.alice_provider, &self.alice_signer, plaintext)
            .unwrap()
            .tls_serialize_detached()
            .unwrap()
    }

    fn assert_opened(&mut self, bytes: &[u8], plaintext: &[u8]) {
        let processed = self
            .bob
            .process_message(&self.bob_provider, protocol_message(bytes))
            .unwrap();
        match processed.into_content() {
            ProcessedMessageContent::ApplicationMessage(message) => {
                assert_eq!(message.into_bytes(), plaintext);
            }
            _ => panic!("expected application message"),
        }
    }

    fn merge_bob(&mut self, commit: &MlsMessageOut) {
        let bytes = commit.tls_serialize_detached().unwrap();
        let staged = self
            .bob
            .process_message(&self.bob_provider, protocol_message(&bytes))
            .unwrap();
        match staged.into_content() {
            ProcessedMessageContent::StagedCommitMessage(staged) => {
                self.bob
                    .merge_staged_commit(&self.bob_provider, *staged)
                    .unwrap();
            }
            _ => panic!("expected staged commit"),
        }
    }
}

#[test]
fn corpus_version_and_endpoint_case_coverage() {
    let vectors = corpus();
    assert_eq!(vectors["corpus_version"], 1);
    assert_eq!(vectors["protocol"]["mls"], "1.0");
    let actual: std::collections::BTreeSet<_> = vectors["cases"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|case| case["owner"] == "openmls" || case["owner"] == "shared")
        .map(|case| case["id"].as_str().unwrap())
        .collect();
    let tested = [
        "opaque-roundtrip",
        "mls-wire",
        "mls-wrong-group",
        "mls-delayed",
        "mls-epoch-order",
        "mls-commit-conflict",
        "mls-member-removed",
    ];
    assert_eq!(actual, tested.into_iter().collect());
}

#[test]
fn opaque_roundtrip() {
    let vectors = corpus();
    let hex = vectors["opaque_payload_hex"].as_str().unwrap();
    let bytes: Vec<_> = (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
        .collect();
    let mut relay = OpaqueRelay::default();
    let slot = relay.put(bytes.clone());
    assert_eq!(relay.get(slot), bytes);
    assert_vector("opaque-roundtrip", &["exact-bytes"]);
}

#[test]
fn two_party_message_crosses_ciphertext_only_relay() {
    let mut pair = joined_pair();
    let plaintext = b"public synthetic application fixture";
    let bytes = pair.application(plaintext);
    let slot = pair.relay.put(bytes.clone());
    assert_eq!(pair.relay.get(slot), bytes);
    assert!(
        !pair
            .relay
            .get(slot)
            .windows(plaintext.len())
            .any(|w| w == plaintext)
    );
    assert!(MlsMessageIn::tls_deserialize_exact(&bytes[..1]).is_err());

    let provider = OpenMlsRustCrypto::default();
    let (credential, signer) = credential(b"version-fixture", SUITE, &provider);
    let package = KeyPackage::builder()
        .build(SUITE, &provider, &signer, credential)
        .unwrap();
    let encoded = package.key_package().tls_serialize_detached().unwrap();
    let decode = || KeyPackageIn::tls_deserialize_exact(encoded.as_slice()).unwrap();
    assert!(
        decode()
            .validate(provider.crypto(), ProtocolVersion::Other(2))
            .is_err()
    );
    assert!(
        decode()
            .validate(provider.crypto(), ProtocolVersion::Mls10)
            .is_ok()
    );
    pair.assert_opened(&bytes, plaintext);
    let epoch = pair.bob.epoch();
    assert!(
        pair.bob
            .process_message(&pair.bob_provider, protocol_message(&bytes))
            .is_err()
    );
    assert_eq!(pair.bob.epoch(), epoch);
    assert_vector(
        "mls-wire",
        &[
            "malformed-rejected",
            "version-rejected",
            "opened",
            "duplicate-rejected",
        ],
    );
}

#[test]
fn mls_wrong_group() {
    let mut local = joined_pair();
    let mut unrelated = joined_pair();
    let epoch = local.bob.epoch();
    let message = unrelated.application(b"different group fixture");
    assert!(matches!(
        local
            .bob
            .process_message(&local.bob_provider, protocol_message(&message)),
        Err(ProcessMessageError::ValidationError(
            ValidationError::WrongGroupId
        ))
    ));
    assert_eq!(local.bob.epoch(), epoch);
    let valid = local.application(b"same group fixture");
    local.assert_opened(&valid, b"same group fixture");
    assert_vector(
        "mls-wrong-group",
        &["group-rejected", "epoch-unchanged", "opened"],
    );
}

#[test]
fn mls_delayed() {
    let mut pair = joined_pair();
    let first = pair.application(b"first application fixture");
    let second = pair.application(b"second application fixture");
    let epoch = pair.bob.epoch();
    pair.assert_opened(&second, b"second application fixture");
    pair.assert_opened(&first, b"first application fixture");
    assert!(
        pair.bob
            .process_message(&pair.bob_provider, protocol_message(&first))
            .is_err()
    );
    assert_eq!(pair.bob.epoch(), epoch);
    assert_vector(
        "mls-delayed",
        &["newer-opened", "delayed-opened", "duplicate-rejected"],
    );
}

#[test]
fn mls_epoch_order() {
    let mut pair = joined_pair();
    let stale = pair.application(b"previous epoch fixture");
    let epoch = pair.bob.epoch();
    let commit = pair
        .alice
        .self_update(
            &pair.alice_provider,
            &pair.alice_signer,
            LeafNodeParameters::default(),
        )
        .unwrap()
        .into_commit();
    pair.alice
        .merge_pending_commit(&pair.alice_provider)
        .unwrap();
    let future = pair.application(b"next epoch fixture");
    assert!(matches!(
        pair.bob
            .process_message(&pair.bob_provider, protocol_message(&future)),
        Err(ProcessMessageError::ValidationError(
            ValidationError::WrongEpoch
        ))
    ));
    assert_eq!(pair.bob.epoch(), epoch);
    pair.merge_bob(&commit);
    assert_eq!(pair.bob.epoch(), pair.alice.epoch());
    assert_ne!(pair.bob.epoch(), epoch);
    assert!(
        pair.bob
            .process_message(&pair.bob_provider, protocol_message(&stale))
            .is_err()
    );
    pair.assert_opened(&future, b"next epoch fixture");
    assert_vector(
        "mls-epoch-order",
        &[
            "future-rejected",
            "commit-merged",
            "stale-rejected",
            "opened",
        ],
    );
}

#[test]
fn mls_commit_conflict() {
    let mut pair = joined_pair();
    let epoch = pair.bob.epoch();
    let competing = pair
        .bob
        .self_update(
            &pair.bob_provider,
            &pair.bob_signer,
            LeafNodeParameters::default(),
        )
        .unwrap()
        .into_commit();
    let chosen = pair
        .alice
        .self_update(
            &pair.alice_provider,
            &pair.alice_signer,
            LeafNodeParameters::default(),
        )
        .unwrap()
        .into_commit();
    assert!(
        pair.bob
            .self_update(
                &pair.bob_provider,
                &pair.bob_signer,
                LeafNodeParameters::default()
            )
            .is_err()
    );
    assert!(pair.bob.pending_commit().is_some());
    assert_eq!(pair.bob.epoch(), epoch);
    pair.bob
        .clear_pending_commit(pair.bob_provider.storage())
        .unwrap();
    assert!(pair.bob.pending_commit().is_none());
    pair.alice
        .merge_pending_commit(&pair.alice_provider)
        .unwrap();
    pair.merge_bob(&chosen);
    assert_eq!(pair.bob.epoch(), pair.alice.epoch());
    let competing = competing.tls_serialize_detached().unwrap();
    assert!(
        pair.alice
            .process_message(&pair.alice_provider, protocol_message(&competing))
            .is_err()
    );
    assert_eq!(pair.bob.epoch(), pair.alice.epoch());
    let valid = pair.application(b"resolved commit fixture");
    pair.assert_opened(&valid, b"resolved commit fixture");
    assert_vector(
        "mls-commit-conflict",
        &[
            "second-local-commit-rejected",
            "local-commit-cleared",
            "peer-commit-merged",
            "conflict-rejected",
            "opened",
        ],
    );
}

#[test]
fn mls_member_removed() {
    let mut pair = joined_pair();
    let index = pair.bob.own_leaf_index();
    let (commit, _, _) = pair
        .alice
        .remove_members(&pair.alice_provider, &pair.alice_signer, &[index])
        .unwrap();
    pair.alice
        .merge_pending_commit(&pair.alice_provider)
        .unwrap();
    pair.merge_bob(&commit);
    assert!(!pair.bob.is_active());
    assert!(
        pair.bob
            .create_message(&pair.bob_provider, &pair.bob_signer, b"inactive")
            .is_err()
    );
    let later = pair.application(b"post-removal fixture");
    assert!(
        pair.bob
            .process_message(&pair.bob_provider, protocol_message(&later))
            .is_err()
    );
    assert!(!pair.bob.is_active());
    assert_vector(
        "mls-member-removed",
        &[
            "inactive",
            "inactive-send-rejected",
            "inactive-receive-rejected",
        ],
    );
}
