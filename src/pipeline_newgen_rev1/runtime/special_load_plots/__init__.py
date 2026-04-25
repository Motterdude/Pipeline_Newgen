"""Special load-mode plots: ethanol-equivalent consumption and machine scenarios."""
from .ethanol_equivalent import (
    plot_ethanol_equivalent_consumption_overlay,
    plot_ethanol_equivalent_ratio,
)
from .machine_scenarios import plot_machine_scenario_suite

__all__ = [
    "plot_ethanol_equivalent_consumption_overlay",
    "plot_ethanol_equivalent_ratio",
    "plot_machine_scenario_suite",
]
