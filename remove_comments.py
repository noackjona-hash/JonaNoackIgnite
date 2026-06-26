import os
import tokenize

def remove_comments_smart(file_path):
    # 1. Originalen Code zeilenweise einlesen
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 2. Koordinaten der Kommentare finden
    comments_by_row = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            for tok in tokenize.generate_tokens(f.readline):
                if tok.type == tokenize.COMMENT:
                    # tok.start[0] ist die Zeilennummer (beginnt bei 1)
                    # tok.start[1] und tok.end[1] sind Start- und Endspalte
                    comments_by_row[tok.start[0]] = (tok.start[1], tok.end[1])
        except tokenize.TokenError:
            pass # Unvollständige Token ignorieren wir

    # 3. Kommentare gezielt herausschneiden
    new_lines = []
    for i, line in enumerate(lines):
        row = i + 1
        if row in comments_by_row:
            start_col, end_col = comments_by_row[row]
            
            # Den Kommentar aus dem String herausschneiden
            line = line[:start_col] + line[end_col:]
            
            # Wenn die Zeile nach dem Entfernen leer ist (z.B. weil es nur ein Kommentar war),
            # wird diese eine Zeile übersprungen und nicht wieder eingefügt.
            if not line.strip():
                continue
        
        new_lines.append(line)
    
    # 4. Den bereinigten Code mit originaler Formatierung zurückschreiben
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

# Ordner und Skriptnamen bestimmen
current_dir = os.path.dirname(os.path.abspath(__file__))
script_name = os.path.basename(__file__)

# Alle .py Dateien durchgehen
for filename in os.listdir(current_dir):
    if filename.endswith('.py') and filename != script_name:
        file_path = os.path.join(current_dir, filename)
        try:
            remove_comments_smart(file_path)
            print(f"Kommentare sauber entfernt (Formatierung behalten): {filename}")
        except Exception as e:
            print(f"Fehler bei {filename}: {e}")