# ReproDossier

> For this build artifact, is the output bit-for-bit reproducible across independent evidence sources and attested without central authority?

ReproDossier compiles reproducibility evidence from orthogonal sources (build matrix hashes + diff, distributed builder consensus, enclave attestation) into a deterministic 3-way verdict + append-only hash-chained ledger.

## Usage

```bash
python -m ReproDossier.reprodossier sample          # 3 example verdicts
python -m ReproDossier.reprodossier run state.json  # JSON output
python -m ReproDossier.reprodossier report state.json  # Markdown
```

## Input shape (state.json)
- `input_id`: string
- `evidence`: list of {output_hash (sha256), source_id}
- `ledger`: (optional) prior chain

## Verdicts
- `reproducible`: hashes match across sources + quorum
- `mismatch`: divergence detected (details in reasons)
- `unattested`: insufficient sources or binding failure

## Boundary
This is not a package builder, not an ML trainer, not a centralized policy engine. It only attests reproducibility evidence.

## Provenance
- recreate run 011-reprodossier
- sources: reproducible-builds + trustix + lexe-public
- stdlib-only, deterministic, MIT

## License
MIT © Jung Wook Yang, 2026
