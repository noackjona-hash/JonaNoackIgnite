import ast
import os

# Projekt-Root ermitteln: die AST-Ausgabe liegt jetzt in docs/.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(ROOT_DIR, "docs", "ast.txt")

def dump_ast():
    with open('gui.py', 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as out:
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                out.write(f'Class: {node.name}\n')
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        out.write(f'  def {item.name}\n')
            elif isinstance(node, ast.FunctionDef):
                out.write(f'Function: {node.name}\n')

if __name__ == '__main__':
    dump_ast()
