"""Data regions of a workspace.

=============== ================== ==========================
Region code     Location           Available on
=============== ================== ==========================
``us-east``     Virginia, USA      all plans (the default)
``eu-central``  Frankfurt, Germany Business and Enterprise
``ap-south``    Mumbai, India      Enterprise only
=============== ================== ==========================

Rules:

- The region is chosen when the workspace is created. Picking a region the
  plan does not include raises ``ERR_PLAN_REQUIRED`` (HTTP 403).
- The region is **fixed at creation** and can never be changed. To move
  data, export the workspace and create a new one in the other region. A
  change request raises ``ERR_CONFLICT``.
"""

from __future__ import annotations

from acme_cloud.common.enums import DEFAULT_REGION, Plan, Region
from acme_cloud.common.errors import ConflictError, PlanRequiredError, ValidationError
from acme_cloud.workspaces.models import Workspace


def parse_region(value: str | Region | None) -> Region:
    """Turn a region code into a ``Region``; ``None`` gives the default ``us-east``."""
    if value is None:
        return DEFAULT_REGION
    try:
        return Region(value)
    except ValueError:
        codes = ", ".join(r.value for r in Region)
        raise ValidationError(f"unknown region {value!r}; choose one of {codes}") from None


def is_region_allowed(plan: Plan, region: Region) -> bool:
    """True when ``plan`` may create a workspace in ``region``."""
    return plan.at_least(region.minimum_plan)


def allowed_regions(plan: Plan) -> list[Region]:
    """Regions offered in the "create workspace" dialog for ``plan``."""
    return [region for region in Region if is_region_allowed(plan, region)]


def require_region(plan: Plan, region: Region) -> None:
    """Raise PlanRequiredError when ``plan`` does not include ``region``."""
    if not is_region_allowed(plan, region):
        needed = region.minimum_plan
        raise PlanRequiredError(
            f"the {region.value} region ({region.location}) needs the "
            f"{needed.value} plan or higher",
            region=region.value, minimum_plan=needed.value, current_plan=plan.value,
        )


def assert_region_unchanged(workspace: Workspace, requested: str | Region) -> None:
    """Reject any attempt to move a workspace to another region.

    Asking for the region the workspace already has is a no-op.
    """
    region = parse_region(requested)
    if region is not workspace.region:
        raise ConflictError(
            "a workspace's region is fixed at creation; export the data and "
            "create a new workspace in the other region",
            workspace_id=workspace.id, current_region=workspace.region.value,
            requested_region=region.value,
        )
