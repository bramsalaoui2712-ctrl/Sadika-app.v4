#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Read the file as bytes first
with open('/app/backend/al_sadika_core_v2.py', 'rb') as f:
    raw_content = f.read()

# Decode as latin-1 first, then encode as utf-8 to fix double encoding
try:
    # First decode as latin-1 to get the raw bytes as string
    intermediate = raw_content.decode('latin-1')
    # Then encode back to bytes and decode as utf-8
    fixed_content = intermediate.encode('latin-1').decode('utf-8')
except:
    # If that fails, try direct utf-8 decode
    fixed_content = raw_content.decode('utf-8', errors='replace')

# Now do the specific replacement
old_text = 'Al SÃ¢dika â€" noyau unique (V2, patches fusionnÃ©s)'
new_text = 'Al Sâdika — noyau unique (V2, patches fusionnés)'

# Check if the old text exists
if old_text in fixed_content:
    print(f"Found {fixed_content.count(old_text)} occurrences of the old text")
    fixed_content = fixed_content.replace(old_text, new_text)
    print("Replacement done")
else:
    print("Old text not found in decoded content")
    # Let's try to find what's actually there
    lines = fixed_content.split('\n')
    for i, line in enumerate(lines[:20]):
        if 'Al' in line and 'dika' in line:
            print(f"Line {i+1}: {repr(line)}")

# Write back the fixed content
with open('/app/backend/al_sadika_core_v2.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print('File processing completed')