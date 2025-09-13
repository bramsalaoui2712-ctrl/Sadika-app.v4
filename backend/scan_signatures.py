import ast
import sys

if len(sys.argv) < 2:
    print("Usage: python3 scan_signatures.py <fichier_python>")
    sys.exit(1)

fichier = sys.argv[1]

with open(fichier, "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        print(f"Fonction : {node.name} (args: {[a.arg for a in node.args.args]})")
    elif isinstance(node, ast.ClassDef):
        print(f"Classe : {node.name}")
        for sub in node.body:
            if isinstance(sub, ast.FunctionDef):
                print(f"  ↳ méthode : {sub.name} (args: {[a.arg for a in sub.args.args]})")
