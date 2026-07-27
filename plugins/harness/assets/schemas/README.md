# Schema binding

The plugin and `sdd-harness` console script are distributed together. The
canonical machine schema is `harness_core`'s bundled
`assets/schemas/governance.schema.json`; `assets/compatibility.json` pins the
required Plugin/Core/Schema versions. A mismatch enters bootstrap-only mode.

The plugin does not keep a second editable Schema copy.
