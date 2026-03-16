# src/web/layout/global_toast.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html


def toast_class(kind: str) -> str:
    return f"position-fixed top-0 end-0 m-3 toast-{kind}"


def build_global_toast():
    return dbc.Toast(
        id="app-toast",
        header="",
        is_open=False,
        dismissable=True,
        duration=5000,
        color="light",
        style={"zIndex": 2000, "minWidth": "320px", "backgroundColor": "white"},
        children=html.Div(
            [
                html.Div(id="app-toast-body", className="mb-2"),
                html.Div(
                    [
                        dbc.Button(
                            "Delete",
                            id="app-toast-confirm-btn",
                            color="danger",
                            size="sm",
                            className="me-2",
                        ),
                        dbc.Button(
                            "Cancel",
                            id="app-toast-cancel-btn",
                            color="secondary",
                            size="sm",
                        ),
                    ],
                    id="app-toast-actions",
                    style={"display": "none"},
                ),
            ],
        ),
    )
