#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Read the file
with open('/app/backend/al_sadika_core_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the garbled UTF-8 with proper UTF-8
old_text = 'Al SÃ¢dika â€" noyau unique (V2, patches fusionnÃ©s)'
new_text = 'Al Sâdika — noyau unique (V2, patches fusionnés)'

# Perform replacement
new_content = content.replace(old_text, new_text)

# Write back
with open('/app/backend/al_sadika_core_v2.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Replacement completed')