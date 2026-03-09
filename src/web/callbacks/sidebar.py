# src/web/callbacks/sidebar.py

from dash_extensions.enrich import clientside_callback, Output, Input, State


def register_callbacks_mobile_offcanvas() -> None:
    
    clientside_callback(
        """
        function(n_clicks, is_open) {
            return !is_open;
        }
        """,
        Output("mobile-offcanvas", "is_open"),
        Input("mobile-open-offcanvas-btn", "n_clicks"),
        State("mobile-offcanvas", "is_open"),
    )