# src/web/callbacks/global_toast.py

import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Input, Output, callback

from web.theme import HIDE, SHOW


def toast_class(kind: str) -> str:
    return f"position-fixed top-0 end-0 m-3 toast-{kind}"


def toast_payload(
    header,
    body,
    *,
    kind="light",
    is_open=True,
    duration=4000,
    confirm_required=False,
    confirm_id=None,
    confirm_label="Confirm",
    confirm_color="danger",
    cancel_label="Cancel",
):
    return {
        "is_open": is_open,
        "header": header,
        "body": body,
        "class_name": toast_class(kind),
        "duration": duration,
        "confirm_required": confirm_required,
        "confirm_id": confirm_id,
        "confirm_label": confirm_label,
        "confirm_color": confirm_color,
        "cancel_label": cancel_label,
    }


def toast_close_payload():
    return {
        "is_open": False,
        "header": "",
        "body": "",
        "class_name": toast_class("light"),
        "duration": 0,
        "confirm_required": False,
        "confirm_id": None,
        "confirm_label": "Confirm",
        "confirm_color": "danger",
        "cancel_label": "Cancel",
    }


def register_callbacks_toast():

    @callback(
        Output("app-toast", "is_open"),
        Output("app-toast", "header"),
        Output("app-toast-body", "children"),
        Output("app-toast", "className"),
        Output("app-toast", "duration"),
        Output("app-toast-actions", "style"),
        Output("app-toast-actions", "children"),
        Input("toast-store", "data"),
    )
    def cb_global_toast(toast_data):
        if not toast_data:
            raise PreventUpdate

        is_open = toast_data.get("is_open", True)
        header = toast_data.get("header", "")
        body = toast_data.get("body", "")
        class_name = toast_data.get("class_name")
        duration = toast_data.get("duration", 5000)

        confirm_required = bool(toast_data.get("confirm_required"))
        confirm_id = toast_data.get("confirm_id") or "app-toast-confirm-btn"
        confirm_label = toast_data.get("confirm_label") or "Confirm"
        confirm_color = toast_data.get("confirm_color") or "danger"
        cancel_label = toast_data.get("cancel_label") or "Cancel"

        actions_style = SHOW if confirm_required else HIDE
        actions_children = []
        if confirm_required:
            actions_children = [
                dbc.Button(
                    confirm_label,
                    id=confirm_id,
                    color=confirm_color,
                    size="sm",
                    className="me-2",
                ),
                dbc.Button(
                    cancel_label,
                    id="app-toast-cancel-btn",
                    color="secondary",
                    size="sm",
                ),
            ]

        return (
            is_open,
            header,
            body,
            class_name,
            duration,
            actions_style,
            actions_children,
        )

