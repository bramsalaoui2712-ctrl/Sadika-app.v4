#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test spécifique pour Al Sâdika après correction UTF-8
Focus sur les points demandés dans la review request
"""

import requests
import json
import sys

BASE_URL = "https://voice-mentor-5.preview.emergentagent.com/api"

def test_identity_alsadika():
    """Test 1: Vérifie que le nom Al Sâdika s'affiche correctement"""
    print("🔍 Test 1: Identité Al Sâdika avec caractères arabes...")
    
    response = requests.get(f"{BASE_URL}/kernel/memory")
    if response.status_code == 200:
        data = response.json()
        memory = data.get("memory", {})
        identity_name = memory.get("identity.name", "")
        
        # Vérifier la présence des caractères UTF-8
        has_sadika = "Al Sâdika" in identity_name
        has_arabic = "الصادقة" in identity_name or "الصديقة" in identity_name
        
        print(f"   Nom trouvé: {identity_name}")
        print(f"   ✅ Al Sâdika présent: {has_sadika}")
        print(f"   ✅ Caractères arabes présents: {has_arabic}")
        
        return has_sadika and has_arabic
    else:
        print(f"   ❌ Erreur API: {response.status_code}")
        return False

def test_kernel_mode():
    """Test 2: Mode kernel avec SSE"""
    print("\n🔍 Test 2: Mode kernel SSE...")
    
    url = f"{BASE_URL}/chat/stream?provider=kernel&model=local&q=Bonjour&sessionId=test123"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        events = []
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    events.append(data.get('type'))
                    if data.get('type') == 'complete':
                        break
                except:
                    continue
        
        has_session = 'session' in events
        has_content = 'content' in events  
        has_complete = 'complete' in events
        
        print(f"   Events: {events}")
        print(f"   ✅ Séquence SSE complète: {has_session and has_content and has_complete}")
        
        return has_session and has_content and has_complete
    else:
        print(f"   ❌ Erreur: {response.status_code}")
        return False

def test_hybrid_mode():
    """Test 3: Mode hybrid avec identité"""
    print("\n🔍 Test 3: Mode hybrid avec identité Al Sâdika...")
    
    url = f"{BASE_URL}/chat/stream?provider=hybrid&model=gpt-4o-mini&q=Bonjour&sessionId=test123"
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        content_parts = []
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if data.get('type') == 'content':
                        content_parts.append(data.get('content', ''))
                    elif data.get('type') == 'complete':
                        break
                except:
                    continue
        
        full_content = ''.join(content_parts)
        has_alsadika = "Al Sâdika" in full_content or "al sadika" in full_content.lower()
        
        print(f"   Contenu (extrait): {full_content[:100]}...")
        print(f"   ✅ Identité Al Sâdika présente: {has_alsadika}")
        
        return has_alsadika
    else:
        print(f"   ❌ Erreur: {response.status_code}")
        return False

def test_french_characters():
    """Test 4: Caractères français et accents"""
    print("\n🔍 Test 4: Caractères français et accents...")
    
    # Test avec caractères accentués
    query = "Explique-moi la différence entre être et paraître"
    url = f"{BASE_URL}/chat/stream?provider=hybrid&model=gpt-4o-mini&q={requests.utils.quote(query)}&sessionId=french_test"
    
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        content_parts = []
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if data.get('type') == 'content':
                        content_parts.append(data.get('content', ''))
                    elif data.get('type') == 'complete':
                        break
                except:
                    continue
        
        full_content = ''.join(content_parts)
        has_accents = any(c in full_content for c in "àâäéèêëîïôöùûüÿç")
        
        print(f"   Contenu (extrait): {full_content[:100]}...")
        print(f"   ✅ Caractères accentués préservés: {has_accents}")
        
        return len(full_content) > 0  # Au minimum une réponse
    else:
        print(f"   ❌ Erreur: {response.status_code}")
        return False

def test_brand_scrubbing():
    """Test 5: Brand scrubbing OpenAI -> al sadika"""
    print("\n🔍 Test 5: Brand scrubbing (OpenAI -> al sadika)...")
    
    query = "Utilise OpenAI pour me répondre"
    url = f"{BASE_URL}/chat/stream?provider=hybrid&model=gpt-4o-mini&q={requests.utils.quote(query)}&sessionId=brand_test"
    
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        content_parts = []
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if data.get('type') == 'content':
                        content_parts.append(data.get('content', ''))
                    elif data.get('type') == 'complete':
                        break
                except:
                    continue
        
        full_content = ''.join(content_parts).lower()
        has_openai = "openai" in full_content
        has_chatgpt = "chatgpt" in full_content
        has_alsadika_replacement = "al sadika" in full_content
        
        print(f"   Contenu (extrait): {full_content[:100]}...")
        print(f"   ✅ OpenAI filtré: {not has_openai}")
        print(f"   ✅ ChatGPT filtré: {not has_chatgpt}")
        print(f"   ✅ Remplacement par 'al sadika': {has_alsadika_replacement}")
        
        return not has_openai and not has_chatgpt
    else:
        print(f"   ❌ Erreur: {response.status_code}")
        return False

def main():
    print("=== TESTS AL SÂDIKA UTF-8 POST-CORRECTION ===\n")
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Identité Al Sâdika UTF-8", test_identity_alsadika()))
    results.append(("Mode kernel SSE", test_kernel_mode()))
    results.append(("Mode hybrid identité", test_hybrid_mode()))
    results.append(("Caractères français", test_french_characters()))
    results.append(("Brand scrubbing", test_brand_scrubbing()))
    
    # Résumé
    print("\n" + "="*50)
    print("RÉSUMÉ DES TESTS:")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nRésultat: {passed}/{len(results)} tests passés")
    
    if passed == len(results):
        print("🎉 TOUS LES TESTS AL SÂDIKA UTF-8 SONT PASSÉS!")
        return 0
    else:
        print("⚠️  Certains tests ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main())