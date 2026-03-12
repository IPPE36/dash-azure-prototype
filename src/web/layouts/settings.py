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

    AVG_INPUT_WIDTH = "56px"
    STD_INPUT_WIDTH = "56px"
    SWITCH_WIDTH = "56px"
    UNIT_WIDTH = "48px"
    PM_WIDTH = "20px"

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

        INPUT_HEIGHT = "26px" if is_sub else "30px"
        INPUT_PADDING = "py-0" if is_sub else "py-1"
        FONT_SIZE = "0.9rem" if is_sub else "1rem"
        ROW_MARGIN = "2px" if is_sub else "6px"
        LINE_HEIGHT = "0.8" if is_sub else "1.1"

        row_children = [
            dbc.Col(
                html.Div(
                    f"{prefix}{label}",
                    style={
                        "whiteSpace": "normal",
                        "lineHeight": LINE_HEIGHT,
                        "fontSize": FONT_SIZE,
                    },
                ),
                className="d-flex align-items-center px-0 mx-0",
            )
        ]

        if use_switch:
            row_children.append(
                dbc.Col(
                    dbc.Switch(
                        id={"type": "use_switch", "index": label},
                        value=True,
                        disabled=disabled,
                        persistence=True,
                        persistence_type="session",
                    ),
                    width="auto",
                    className="d-flex justify-content-center align-items-center ps-1",
                    style={"width": SWITCH_WIDTH},
                )
            )

        row_children.append(
            dbc.Col(
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
                    className=f"compact-input text-center mx-0 px-0 {INPUT_PADDING}",
                    style={
                        "width": AVG_INPUT_WIDTH,
                        "height": INPUT_HEIGHT,
                        "fontSize": FONT_SIZE,
                    },
                ),
                width="auto",
                className="d-flex align-items-center px-0 py-0",
            )
        )

        if use_std:
            row_children.extend(
                [
                    dbc.Col(
                        html.Div(
                            "±",
                            className="text-center mx-0 px-1",
                        ),
                        width="auto",
                        className="d-flex align-items-center justify-content-center px-0 py-0",
                        style={"width": PM_WIDTH},
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "input_std", "index": label},
                            type="number",
                            value=stddev,
                            min=0,
                            step=1,
                            disabled=disabled,
                            persistence=True,
                            persistence_type="session",
                            className=f"compact-input text-center px-0 mx-0 {INPUT_PADDING}",
                            style={
                                "width": STD_INPUT_WIDTH,
                                "height": INPUT_HEIGHT,
                                "fontSize": FONT_SIZE,
                            },
                        ),
                        width="auto",
                        className="d-flex align-items-center px-0 py-0",
                    ),
                ]
            )

        row_children.append(
            dbc.Col(
                html.Div(
                    "[MPa]",
                    className="text-end mx-0 px-1",
                ),
                width="auto",
                className="d-flex align-items-center px-0 py-0",
                style={"width": UNIT_WIDTH},
            )
        )

        children.append(
            dbc.Row(
                row_children,
                className="g-0 align-items-center mx-0 px-0 py-0",
                style={
                    "flexWrap": "nowrap",
                    "marginBottom": ROW_MARGIN,
                }
            )
        )
    
    list_group = html.Div(
        children,
        className="w-100 p-1 ps-3 mb-3",
        style={"border": "1px solid lightgray", "border-radius": "5px"}
    )
    return list_group



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
                [
                    # Row 1: label
                    dbc.Row(
                        dbc.Col(
                            label,
                            className="d-flex align-items-center",
                        ),
                        className="mb-2",
                    ),

                    # Row 2: switch + slider
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Switch(
                                    id={"type": "use_switch", "index": label},
                                    value=True,
                                    disabled=disabled,
                                    persistence=True,
                                    persistence_type="session",
                                ),
                                className="d-flex align-items-center justify-content-center",
                                xs=3,
                                md=3,
                                lg=3,
                            ),
                            dbc.Col(
                                dcc.RangeSlider(
                                    id={"type": "slider", "index": label},
                                    min=min_value,
                                    max=max_value,
                                    value=[min_value, max_value],
                                    disabled=disabled,
                                    persistence=True,
                                    step=1,
                                    persistence_type="session",
                                    marks={
                                        min_value: str(min_value),
                                        max_value: str(max_value),
                                    },
                                    tooltip={
                                        "placement": "top",
                                        "always_visible": True,
                                    },
                                ),
                                xs=9,
                                md=9,
                                lg=9,
                            ),
                        ]
                    ),
                ],
                className="bg-light",
            )
        )

    return dbc.ListGroup(
        items,
        flush=True,
        className="w-100 mb-3",
        style={
            "border": "1px solid lightgray",
            "borderRadius": "5px",
        },
    )
