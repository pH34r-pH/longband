# Network-capture analysis boundary

This offline helper assists the operator-opacity exercise in [issue #55](https://github.com/pH34r-pH/longband/issues/55).
It scans the supplied capture bytes, follows decoded TCP streams separately in each direction, and scans each supplied operator-visible artifact for one exact canary. It does not capture traffic, contact a relay, read participant state, or decide Alpha acceptance.

Use only a run-unique synthetic canary and authorized capture artifacts. Keep raw captures, logs, endpoint details, and the canary in private, access-controlled storage. The JSON receipt omits their paths and contents. It records file digests and counts, the local TShark version, caller-declared source commit and Fleet run ID, and whether TShark saw categories of network metadata; it does not reproduce addresses, ports, timestamps, or TLS values. Relay identifiers are not assessed.

```sh
python scripts/analyze_network_capture.py /private/traffic.pcap \
  --artifact /private/proxy.log --artifact /private/derived-strings.txt \
  --canary-file /private/canary.txt --source-sha <40-lowercase-hex> \
  --run-id <fleet-run-number> --output /private/new-receipt.json
```

Supply every relevant operator-visible log, request/response body, and derived artifact as a separate `--artifact`; no single supplied file proves that the list is complete. The source and run identifiers are declarations to be checked against the protected Fleet receipt. A found canary produces a nonzero exit and a sanitized `found` receipt, including an explicit incomplete-coverage marker if a later step fails. Empty, missing, changed, oversized, truncated or malformed inputs, a decoder failure, detected TCP gaps, or a resource-budget failure produce a nonzero exit without a negative receipt. Existing receipt paths are never overwritten.

The operational bounds are 128 MiB per file, 512 MiB of total file reads, 32 additional artifacts, 256 TCP streams, 64 MiB of decoder output per invocation, 120 seconds per decoder invocation, and a 300-second analysis deadline. The deadline is checked during reads and around decoder calls; a blocked filesystem read or process teardown can exceed it. Exceeding a bound is incomplete evidence, not a security result. TShark must be available on `PATH`; run the analysis in an isolated, network-disabled environment with an independently reviewed TShark installation and external resource limits. TShark dissectors process untrusted input.

`not-found-in-supplied-bytes` is **not a confidentiality verdict**. Capture completeness, packets lost before or outside the capture, TLS decryption, decompression and other application encodings, reassembly of UDP/IP fragments, unsupplied artifacts, hidden endpoint state, and the identity of the caller-declared source/run are not established. A canary split across TCP segments in the same direction is checked; the directions are never concatenated. A failure to detect a TCP gap is not proof that no gap exists. The tool records categories of observed metadata, not an exhaustive inventory of the operator's visibility.

The final exercise still requires the protected Fleet capture, an independently reviewed capture and artifact inventory, appropriate decoding of every applicable surface, sanitized retention and cleanup, and independent security review. A local synthetic test does not satisfy those gates.
