from __future__ import annotations

from pathlib import Path

from dash import Dash

from ghostrecon.common.config import Settings
from ghostrecon.console.callbacks import register_callbacks
from ghostrecon.console.layouts import build_shell


def create_console_dash_app(settings: Settings) -> Dash:
    assets_folder = Path(__file__).parent / "assets"
    dash_app = Dash(
        __name__,
        assets_folder=str(assets_folder),
        suppress_callback_exceptions=True,
        title="GhostRecon Console",
        update_title=None,
    )
    dash_app.layout = lambda: build_shell(settings)
    register_callbacks(dash_app, settings)
    return dash_app
