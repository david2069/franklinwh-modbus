# Agent Onboarding & Project Standards

> **MANDATORY:** All agents must read and adhere to this document before performing any work in this repository.

## 1. Professional Communication Standard
All technical communications, documentation, and logic labels must utilize **Plain Technical Business English**. 

### 1.1 Prohibited Terminology
The use of informal, "cutesy," or made-up terminology is strictly prohibited. This includes but is not limited to:
*   ~~"Ghost Pass"~~ → Use **False Positive** or **Write-Verify Asymmetry**
*   ~~"Silent Discard"~~ → Use **Non-Conformant Write Persistence**
*   ~~"Paradox"~~ → Use **Operational State Deviation**
*   ~~"Cute/Cutesy"~~ → Use **Professional Technical Communication**

## 2. Technical Source of Truth
Agents must prioritize the following normative references over heuristic assumptions:
1.  **[NORMATIVE_REFERENCE_MASTER.md](~/.gemini/antigravity/brain/caabe7a8-880e-4e0e-a695-af48b8dde79e/NORMATIVE_REFERENCE_MASTER.md)**: The authoritative source for protocol compliance and technical definitions.
2.  **[FWH-PICS-PUB]**: Official SunSpec SM-000028 certification.
3.  **[FWH-PICS-ENG]**: Engineering supplemental PICS for SPAN/Solar extensions.

## 3. Mandatory Implementation Patterns
*   **Synchronous Verification Pattern**: All Modbus writes must be followed by a read-back comparison.
*   **Differentiated Verification Status**: Sequencer results must distinguish between `[VERIFIED]` (successful transition) and `[MATCHED - NO TRANSITION]` (pre-existing state).
*   **First, Do No Harm**: Safety-critical registers must never be subjected to "Toggle Testing" or active probing without explicit user authorization.

## 4. Workflows
*   **Phased Development**: Follow the established phases in `PHASES_AND_ROADMAP.md`.
*   **Test Traceability**: All test results must be recorded in `tests/results/` with date-stamped filenames.

---
**Failure to adhere to these standards constitutes a breach of project governance.**
