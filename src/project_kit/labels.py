"""Labels project-kit derives from the backlog: one per issue type and per priority."""

# (name, colour, description). Bugs reuse GitHub's own default "bug" label.
TYPE_LABELS = {
    "epic": ("type:epic", "3E4B9E", "Epic: groups child issues"),
    "feature": ("type:feature", "1D76DB", "New functionality"),
    "adr": ("type:adr", "5319E7", "Architecture decision"),
    "chore": ("type:chore", "6E7781", "Maintenance or technical task"),
    "docs": ("type:docs", "0075CA", "Documentation"),
    "bug": ("bug", "D73A4A", "Something is not working"),
}
PRIORITY_LABELS = {
    "P0": ("P0", "B60205", "Critical priority"),
    "P1": ("P1", "D93F0B", "High priority"),
    "P2": ("P2", "FBCA04", "Medium priority"),
    "P3": ("P3", "C2E0C6", "Low priority"),
}
