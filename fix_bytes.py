#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Read the file as bytes
with open('/app/backend/al_sadika_core_v2.py', 'rb') as f:
    content = f.read()

# The problematic bytes sequence for "Al SÃ¢dika â€" noyau unique (V2, patches fusionnÃ©s)"
# Let's find and replace the byte sequence directly
old_bytes = b'Al S\xc3\x83\xc2\xa2dika \xc3\xa2\xe2\x82\xac\xe2\x80\x9d noyau unique (V2, patches fusionn\xc3\x83\xc2\xa9s)'
new_bytes = 'Al Sâdika — noyau unique (V2, patches fusionnés)'.encode('utf-8')

print(f"Looking for byte sequence of length {len(old_bytes)}")
print(f"Replacement will be {len(new_bytes)} bytes")

if old_bytes in content:
    print("Found the byte sequence!")
    new_content = content.replace(old_bytes, new_bytes)
    
    with open('/app/backend/al_sadika_core_v2.py', 'wb') as f:
        f.write(new_content)
    print("Replacement completed")
else:
    print("Byte sequence not found")
    # Let's find what's actually there around line 11
    lines = content.split(b'\n')
    for i, line in enumerate(lines[:15]):
        if b'Al' in line and b'dika' in line:
            print(f"Line {i+1} bytes: {line}")
            print(f"Line {i+1} decoded: {line.decode('utf-8', errors='replace')}")