# Wikilink implementation Questionaire

1. **Resolution Ambiguity**: When `[[Foo]]` matches multiple files (e.g., `work/Foo.md` and `personal/Foo.md`), the spec says "prefer the closest ancestor shared with the current file". If both are equally "close" (e.g., in different top-level folders), should we just pick the first alphabetically or prompt the user? Answer: lets' do absolute.
2. **Rename Propagation Performance**: For a vault with 5000+ files, rewriting links synchronously will freeze the UI. Should we implement a "Dry Run" preview before actually committing the changes to disk? Let's not focus on crazy amount of files foe now.
3. **Broken Link Creation**: When clicking a broken link `[[NewNote]]`, the spec says it creates a note "next to the linking note". If the linking note is in a deep folder, should we allow the user to override the destination folder via the creation dialog? Pick a simple rule, we will build a way cooler AI flow later.
4. **Callout Styling**: Should callouts be collapsible like in Obsidian (`> [!note]- `)?  Yes, if it does not introduce too much complexity.
5. **Transclusion CSS**: Should transcluded content have a visual border or background to indicate it is "borrowed" from another file? For now, yes.
6. **Case Sensitivity**: The spec says "Paths are matched case-sensitively on Linux". Should we offer a "Smart Case" option where it tries case-insensitive if a case-sensitive match fails? No, just case sensitive.
