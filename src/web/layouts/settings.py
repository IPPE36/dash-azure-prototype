# src/web/layout/settings.py

from dash_extensions.enrich import dcc
import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

def build_settings_input_list(*, row_list=None):
    """
    row_list tuples:
    (level, label, avg, stddev, use_std, disabled, limit_min, limit_max, use_switch)
    """
    row_list = row_list or []
    children = []

    for (
        level,
        label,
        avg,
        stddev,
        use_std,
        disabled,
        limit_min,
        limit_max,
        use_switch,
    ) in row_list:
        is_sub = level == "sub"
        prefix = "→ " if is_sub else ""

        base_label_width = 73 if not use_std else 50
        label_width = f"{base_label_width - 10}%" if use_switch else f"{base_label_width}%"

        controls = [
            dbc.InputGroupText(
                f"{prefix}{label}",
                style={
                    "width": label_width,
                    "whiteSpace": "normal",
                    "lineHeight": "1.2",
                    "textAlign": "left",
                    "justifyContent": "flex-start",
                    "paddingLeft": "1rem" if is_sub else "0.5rem",
                },
            ),
        ]

        if use_switch:
            controls.append(
                dbc.InputGroupText(
                    dbc.Switch(
                        id={"type": "use_switch", "index": label},
                        value=True,
                        disabled=disabled,
                        persistence=True,
                        persistence_type="session",
                        style={"margin": "0"},
                    ),
                    style={
                        "width": "10%",
                        "display": "flex",
                        "justifyContent": "center",
                        "alignItems": "center",
                        "padding": "0",
                    },
                )
            )

        controls.append(
            dbc.Input(
                id={"type": "input_avg", "index": label},
                type="number",
                value=avg,
                min=limit_min,
                max=limit_max,
                step=1,
                disabled=disabled,
                persistence=True,
                persistence_type="session",
                className="compact-input text-center flex-grow-1",
            )
        )

        if use_std:
            controls.extend([
                dbc.InputGroupText(
                    "±",
                    style={
                        "justifyContent": "center",
                        "textAlign": "center",
                        "flex": "0 0 auto",
                    },
                ),
                dbc.Input(
                    id={"type": "input_std", "index": label},
                    type="number",
                    value=stddev,
                    min=0,
                    step=1,
                    disabled=disabled,
                    persistence=True,
                    persistence_type="session",
                    className="compact-input text-center flex-grow-1",
                ),
            ])

        controls.append(
            dbc.InputGroupText(
                "MPa",
                style={
                    "justifyContent": "flex-end",
                    "textAlign": "right",
                    "flex": "0 0 auto",
                },
            )
        )

        children.append(
            html.Div(
                dbc.InputGroup(
                    controls,
                    size="sm",
                    className="w-100 m-0 borderless-inputgroup",
                    style={"flexWrap": "nowrap", "border": "1px solid lightgray", "border-radius": "5px"},
                ),
                className="m-0 mb-1",
            )
        )

    return html.Div(children, className="w-100")


def build_settings_dropdown(*, options):

    normalized_options = [
        {"label": opt, "value": opt} if not isinstance(opt, dict) else opt
        for opt in (options or [])
    ]
            
    dropdown = dcc.Dropdown(
        id="dd",
        options=normalized_options,
        multi=True,
        disabled=False,
        persistence=True,
        persistence_type="session",
        className="mt-3 mx-0 p-0",
        placeholder="Select...",
    )

    return dropdown



def build_settings_slider_list(*, row_list=None):
    """
    row_list tuples:
    (label, value, min_value, max_value, disabled)
    """
    row_list = row_list or []

    items = []
    for label, value, min_value, max_value, disabled in row_list:
        items.append(
            dbc.ListGroupItem(
                html.Div(
                    [
                        html.Div(
                            label,
                            className="small text-muted mb-1",
                            style={"textAlign": "left"},
                        ),
                        dcc.Slider(
                            id={"type": "slider", "index": label},
                            min=min_value,
                            max=max_value,
                            value=value,
                            disabled=disabled,
                            persistence=True,
                            persistence_type="session",
                            tooltip={"placement": "bottom", "always_visible": False},
                            marks={
                                min_value: str(min_value),
                                max_value: str(max_value),
                            },
                        ),
                    ]
                ),
                className="py-2",
                color="light",
            )
        )
    return dbc.ListGroup(items, flush=True, className="w-100", style={"border": "1px solid lightgray", "border-radius": "5px"})