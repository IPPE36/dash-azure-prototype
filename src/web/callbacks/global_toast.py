# src/web/callbacks/global_toast.py

from dash_extensions.enrich import Input, Output, clientside_callback


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
        "class_name": f"position-fixed top-0 end-0 m-3 toast-{kind}",
        "duration": duration,
        "confirm_required": confirm_required,
        "confirm_id": confirm_id,
        "confirm_label": confirm_label,
        "confirm_color": confirm_color,
        "cancel_label": cancel_label,
    }


def register_callbacks_toast():

    clientside_callback(
        """
        function(toast_data) {
            if (!toast_data) {
                throw window.dash_clientside.PreventUpdate;
            }

            const SHOW = {display: "block"};
            const HIDE = {display: "none"};

            const is_open = toast_data.is_open ?? true;
            const header = toast_data.header ?? "";
            const body = toast_data.body ?? "";
            const class_name = toast_data.class_name ?? null;
            const duration = toast_data.duration ?? 20000;

            const confirm_required = Boolean(toast_data.confirm_required);
            const confirm_id = toast_data.confirm_id || "app-toast-confirm-btn";
            const confirm_label = toast_data.confirm_label || "Confirm";
            const confirm_color = toast_data.confirm_color || "danger";
            const cancel_label = toast_data.cancel_label || "Cancel";

            const actions_style = confirm_required ? SHOW : HIDE;
            let actions_children = [];

            if (confirm_required) {
                actions_children = [
                    {
                        namespace: "dash_bootstrap_components",
                        type: "Button",
                        props: {
                            children: confirm_label,
                            id: confirm_id,
                            color: confirm_color,
                            size: "sm",
                            className: "me-2"
                        }
                    },
                    {
                        namespace: "dash_bootstrap_components",
                        type: "Button",
                        props: {
                            children: cancel_label,
                            id: "app-toast-cancel-btn",
                            color: "secondary",
                            size: "sm"
                        }
                    }
                ];
            }

            return [
                is_open,
                header,
                body,
                class_name,
                duration,
                actions_style,
                actions_children
            ];
        }
        """,
        Output("app-toast", "is_open"),
        Output("app-toast", "header"),
        Output("app-toast-body", "children"),
        Output("app-toast", "className"),
        Output("app-toast", "duration"),
        Output("app-toast-actions", "style"),
        Output("app-toast-actions", "children"),
        Input("toast-store", "data"),
    )

    clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks) {
                return window.dash_clientside.no_update;
            }
            return false;
        }
        """,
        Output("app-toast", "is_open", allow_duplicate=True),
        Input("app-toast-cancel-btn", "n_clicks"),
        prevent_initial_call=True,
    )
