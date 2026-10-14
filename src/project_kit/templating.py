"""Minimal ``{{variable}}`` substitution for the templates project-kit ships.

Deliberately strict: an unknown variable is an error, so a typo in a template that the
project has overridden is reported instead of leaking ``{{...}}`` into generated files.
"""

import re

_VARIABLE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")


class TemplateError(ValueError):
    """The template uses a variable that was not provided."""


def render(text: str, variables: dict[str, str]) -> str:
    unknown = sorted({name for name in _VARIABLE.findall(text) if name not in variables})
    if unknown:
        known = ", ".join(sorted(variables))
        raise TemplateError(
            f"Unknown template variable(s): {', '.join(unknown)}. Available: {known}."
        )
    return _VARIABLE.sub(lambda m: variables[m.group(1)], text)
