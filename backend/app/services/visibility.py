"""Which objects a workspace can see.

Two different things are shared, and they are not the same thing:

  types      A global *type* (a schema) can be used from every workspace: it is
             how one catalogue defines "Camera" or "Product Model" once for every
             beamline. That is about the definition.
  objects    An object is visible outside the workspace that owns it only if it is
             itself flagged global. Being of a global type does not do it.

The two used to be the same rule, so every camera of every beamline was visible
in every other one, and a workspace's own list drowned in the others'. What is
meant to be shared — a product model, a vendor, a person, a company, an
inventory document — is flagged; a beamline's own cameras and pumps are not, and
stay in the beamline that has them. Anything created in a global workspace is
flagged when it is made, the way its types and documents already are.
"""
from sqlalchemy import or_

from app.models.asset import Asset


def asset_visible_in(asset: Asset, workspace_id: str) -> bool:
    return asset.workspace_id == workspace_id or bool(asset.is_global)


def visible_assets_clause(workspace_id: str):
    return or_(Asset.workspace_id == workspace_id, Asset.is_global.is_(True))
