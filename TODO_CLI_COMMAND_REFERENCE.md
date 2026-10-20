# TODO: CLI Command Reference Update

**Status:** Approved (pending implementation)  
**Approved:** 2026-05-15  
**Priority:** S3 — Medium  
**Estimated Effort:** Low (Documentation)

## Description
Update the project documentation (or create a new `CLI_COMMAND_REFERENCE.md`) to ensure every available option in `franklinwh_cli.py` is documented. 

## Requirements (as approved)
- Document every option from the `--help` output.
- Use a table for readability.
- Categorize options (Connectivity, Control, Monitoring, Sequencing).
- Include the new action flags (`--charge`, `--discharge`, `--max-charge`, `--max-discharge`, `--standby`).
- Include sequencing flags (`--sequence`, `--sequence-file`, `--brief`).
- Document themes and interactive monitor options.

## Implementation Notes
- Source of truth is the `ArgumentParser` configuration in `tools/franklinwh_cli.py`.
- Ensure examples from the `--help` footer are also included in the guide.

## Related
- Original approval context: [in_flight_work.md](/in_flight_work.md)
