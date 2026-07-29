from dash import ALL

from ghostrecon.models.api import DashboardRole

ACTION_PATTERN = {
    "type": "dashboard-action",
    "kind": ALL,
    "action": ALL,
    "target_id": ALL,
    "version": ALL,
    "policy_hash": ALL,
    "enabled": ALL,
}


MUTATING_ROLES = {
    DashboardRole.ANALYST.value,
    DashboardRole.GOVERNANCE_REVIEWER.value,
    DashboardRole.ADMINISTRATOR.value,
}


SEQUENCE_LAYER_COUNT = 20
