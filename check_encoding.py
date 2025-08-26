#!/usr/bin/env python3
# -*- coding: utf-8 -*-

with open('/app/backend/al_sadika_core_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_text = 'Al SÃ¢dika â€" noyau unique (V2, patches fusionnÃ©s)'
print('Found occurrences:', content.count(old_text))
print('First occurrence at position:', content.find(old_text))

# Let's also check the bytes
with open('/app/backend/al_sadika_core_v2.py', 'rb') as f:
    raw_content = f.read()
    
print('Raw bytes around position 500-600:')
print(raw_content[500:600])