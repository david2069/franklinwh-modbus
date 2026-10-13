import sys

import os
tsv_path = os.path.expanduser("~/Downloads/UPDATED_FranklinWH_Modbus_PICS_SM-000028 2.tsv")

with open(tsv_path, 'r') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Let's find sections that describe enums
# A line represents an enum choice if it has leading tabs and starts with capital letters like OFF, ON, RUNNING etc.
for idx, line in enumerate(lines[:300]):
    parts = line.strip().split('\t')
    if not line.startswith('\t') and len(parts) > 1 and parts[0].isdigit():
        print(f"Register {parts[0]}: {parts[1]} ({parts[4] if len(parts) > 4 else ''})")
    elif line.startswith('\t') and line.strip():
        print(f"  Enum: {line.strip()}")
