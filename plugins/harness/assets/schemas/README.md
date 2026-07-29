# Schema binding

The plugin and `sdd-harness` console script are distributed together. The
canonical machine schema is `harness_core`'s bundled
`assets/schemas/governance.schema.json`. The projection lock pins the required
governance Schema and compiler versions. A mismatch enters bootstrap-only mode.

The plugin does not keep a second editable Schema copy.
