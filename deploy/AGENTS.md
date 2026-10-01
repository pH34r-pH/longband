# Deployment boundary map

[`README.md`](README.md), [`PERSISTENCE.md`](PERSISTENCE.md), and [`longband-alpha.service`](longband-alpha.service) describe the portable public Alpha service boundary: one unprivileged loopback process, reverse-proxy assumptions, current in-memory state, and exact-SHA package handoff. Private Fleet owns hostnames, certificates, credentials, target inventories, promotion, rollback, and physical operations.

Do not add secrets, private topology, plaintext debug paths, or deployment approval claims here. A successful public CI/package run is evidence for that exact source and test scope, not a deployment authorization.
