//! Longband OpenMLS lifecycle research fixture.
//!
//! This binary intentionally starts as a compile-time integration point. The
//! lifecycle scenarios in README.md are implemented incrementally against
//! upstream OpenMLS APIs; no relay-facing plaintext API belongs here.

fn main() {
    println!("longband-openmls-prototype: lifecycle fixture; not for production");
}

#[cfg(test)]
mod tests {
    /// The relay representation must remain opaque by construction. This
    /// fixture will evolve into captured TLS-serialized MLS objects; keeping
    /// the type byte-only prevents application code from accidentally giving
    /// the relay a plaintext field while the OpenMLS integration is built.
    #[derive(Clone, Debug, PartialEq, Eq)]
    struct RelayObject(Vec<u8>);

    #[test]
    fn relay_object_has_only_opaque_bytes() {
        let object = RelayObject(vec![0xde, 0xad, 0xbe, 0xef]);
        assert_eq!(object.0.len(), 4);
    }
}
