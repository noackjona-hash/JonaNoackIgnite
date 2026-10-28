# Regel: Kontinuierliche Git-Commits & Revisionssicherheit

## Anweisung für alle AI-Agenten
- Nach **jeder** Code-Änderung, neuem Feature, Refactoring, Bugfix oder Dokumentations-Update **muss sofort ein Git-Commit erstellt werden**.
- Das Vorgehen lautet ausnahmslos:
  1. Status prüfen (`git status`)
  2. Modifizierte und neue Dateien gezielt stagen (`git add <dateien>`)
  3. Konventionellen, präzisen Commit mit Typ erstellen (`git commit -m "feat/fix/docs/refactor: ..."` auf Deutsch oder Englisch)
  4. Sofort zu Remote pushen (`git push origin main`)
- Es dürfen am Ende eines Aufgaben-Schritts niemals uncommittete Änderungen im Arbeitsverzeichnis (`working tree`) verbleiben.
