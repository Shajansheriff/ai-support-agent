"""Load independent service packages under unique names for in-process testing."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for name in ("gateway", "agent", "orders", "refunds", "approvals", "worker"):
    package = ROOT / "services" / name / "app"
    spec = importlib.util.spec_from_file_location(
        f"{name}_app", package / "__init__.py",
        submodule_search_locations=[str(package)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
