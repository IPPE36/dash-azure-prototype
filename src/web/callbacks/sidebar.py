# src/web/callbacks/sidebar.py

from dash_extensions.enrich import clientside_callback, callback, Output, Input, State, ALL, Trigger
from dash_extensions.enrich import callback_context as ctx
from dash.exceptions import PreventUpdate


def register_callbacks_mobile() -> None:
    
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


    @callback(
        Output({"type": "main-nav-btn", "index": ALL}, "color"),
        Output({"type": "main-nav-panel", "index": ALL}, "hidden"),
        Trigger({"type": "main-nav-btn", "index": ALL}, "n_clicks"),
    )
    def nav_panels():
        
        active = ctx.triggered_id
        if not active:
            raise PreventUpdate

        colors = []
        hidden = []
        for btn in ctx.inputs_list[0]:
            if btn["id"] == active:
                colors.append("primary")
                hidden.append(False)
            else:
                colors.append("secondary")
                hidden.append(True)

        return colors, hidden
