# TODO: Auto-Disconnect / Indefinite Monitor Mode

**Status:** Proposed  
**Created:** 2026-02-24  
**Priority:** Low (Future Enhancement)  

## Feature Request

Add auto-disconnect functionality for long-running monitor sessions to prevent indefinite connections when not actively controlling the battery.

## Use Case

Users who want to:
- Monitor battery for extended periods without manually disconnecting
- Automatically stop after idle period (no charge/discharge commands)
- Prevent accidental long-term Modbus connections

## Proposed Implementation

### CLI Options

```bash
# Auto-disconnect after 30 minutes of inactivity
python3 franklinwh_cli.py -i 192.0.2.110 --monitor --auto-disconnect 30

# Or indefinite mode (requires explicit --indefinite flag)
python3 franklinwh_cli.py -i 192.0.2.110 --monitor --indefinite
```

### Behavior

| Mode | Description |
|------|-------------|
| **Default** | Auto-disconnect after 60 min inactivity |
| `--auto-disconnect N` | Disconnect after N minutes of inactivity |
| `--indefinite` | Never auto-disconnect (explicit opt-in) |

### Inactivity Definition

"Inactive" means:
- No charge/discharge commands sent
- No power adjustments (+/-)
- No mode changes (standby, max charge, etc.)

Only monitoring (viewing data) counts as inactivity.

### Implementation Notes

1. **Track last activity timestamp** — Update on any command
2. **Background timer thread** — Check every minute
3. **Graceful disconnect** — Show warning at 5 min, 1 min before disconnect
4. **Activity reset** — Any key press/command resets timer

### Example Warning Messages

```
⚠️  Auto-disconnect in 5 minutes (no activity)
⚠️  Auto-disconnect in 1 minute - press any key to extend
🔌 Auto-disconnected due to inactivity
```

### Files to Modify

- `src/franklinwh/monitor.py` — Add timer logic, CLI args
- `franklinwh_cli.py` — Add `--auto-disconnect`, `--indefinite` arguments

### Considerations

- **Safety**: Don't disconnect during active charge/discharge
- **User experience**: Clear warnings before disconnect
- **Default**: Conservative (60 min) to prevent accidental long connections
- **Override**: Easy to extend with any key press

## Related

- Current monitor requires manual disconnect or quit ('q')
- Modbus connections left open indefinitely may affect aGate performance
