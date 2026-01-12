"""
Vertical Templates

Industry-specific agent templates:
- Finance (4 templates)
- Healthcare (4 templates)
- Energy (4 templates)
- Government (4 templates)

Each template is 70% pre-built, 30% customizable.
"""

from services.templates.verticals.finance import get_finance_templates
from services.templates.verticals.healthcare import get_healthcare_templates
from services.templates.verticals.energy import get_energy_templates
from services.templates.verticals.government import get_government_templates

__all__ = [
    "get_finance_templates",
    "get_healthcare_templates",
    "get_energy_templates",
    "get_government_templates",
]


def register_all_vertical_templates(registry) -> int:
    """
    Register all vertical templates with the registry.

    Returns:
        Number of templates registered
    """
    count = 0

    for template in get_finance_templates():
        if registry.register(template):
            count += 1

    for template in get_healthcare_templates():
        if registry.register(template):
            count += 1

    for template in get_energy_templates():
        if registry.register(template):
            count += 1

    for template in get_government_templates():
        if registry.register(template):
            count += 1

    return count
