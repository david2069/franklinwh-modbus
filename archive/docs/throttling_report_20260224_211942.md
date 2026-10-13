# Throttling Monitor Report

**Date:** 2026-02-24 21:19:42
**Host:** 192.0.2.110 (Unit ID: 2)
**Duration:** 60 minutes
**Interval:** 30 seconds

## Summary

| Metric | Value |
|--------|-------|
| Total Samples | 120 |
| Throttling Events | 0 |
| Max Throttle | 0% |
| Avg Throttle | 0.0% |
| Start SoC | 9863% |
| End SoC | 6685% |
| Start Power | 1W |
| End Power | 1W |

## ✅ No Throttling Detected

ThrotPct remained at 0% throughout the test period.

## Key Findings

1. **No throttling:** ThrotPct remained at 0%
2. **ThrotPct readable:** Register 40180 returns valid data
4. **ThrotSrc unimplemented:** Always returned 0xFFFFFFFF

## Conclusion

Throttling monitoring **works but no events occurred** during test. Consider re-testing when SoC > 95% or on hot day.

---
*Report generated automatically by log_throttling_1hour.py*
