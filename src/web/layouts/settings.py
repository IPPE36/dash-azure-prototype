# src/web/layout/settings.py

from dash_extensions.enrich import dcc
import dash_bootstrap_components as dbc
from dash_extensions.enrich import html


def build_input_list(*, row_list=None):
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
        style={"border": "1px solid lightgray", "border-radius": "5px"},
    )
    return list_group



def build_dropdown(*, options):

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


def build_sliders(*, row_list=None):
    """
    row_list tuples:
    (label, value, min_value, max_value, disabled)

    value can be:
    - None -> defaults to [min_value, max_value]
    - a 2-item list/tuple for RangeSlider
    """
    row_list = row_list or []

    items = []
    for idx, (label, value, min_value, max_value, disabled) in enumerate(row_list):
        slider_index = f"{label}__{idx}"
        if value is None or value == []:
            slider_value = [min_value, max_value]
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            slider_value = list(value)
        else:
            slider_value = [value, value]

        items.append(
            dbc.Col(
                html.Div(
                    [
                        # Clickable label toggles slider enable/disable
                        html.Div(
                            [
                                dbc.Button(
                                    label,
                                    id={"type": "slider_toggle", "index": slider_index},
                                    color="primary",
                                    outline=bool(disabled),
                                    size="sm",
                                    className="w-100 m-0 slider-toggle-btn",
                                    style={"borderBottomLeftRadius": 0, "borderBottomRightRadius": 0},
                                ),
                            ],
                            className="d-flex align-items-center justify-content-center mb-2",
                        ),

                        # Vertical slider
                        html.Div(
                            dcc.RangeSlider(
                                id={"type": "slider", "index": slider_index},
                                min=min_value,
                                max=max_value,
                                value=slider_value,
                                step=1,
                                disabled=disabled,
                                persistence=True,
                                persistence_type="session",
                                vertical=True,
                                verticalHeight=150,
                                marks={
                                    min_value: f"{min_value}%",
                                    max_value: f"{max_value}%",
                                },
                                tooltip={
                                    "placement": "left",
                                    "always_visible": True,
                                },
                            ),
                            className="d-flex m-0 justify-content-center",
                            style={"height": "150px"},
                        ),
                    ],
                    className="p-0 border rounded h-100",
                    style={"backgroundColor": "white"},
                ),
                xs=4,
                sm=4,
                md=3,
                lg=2,
                className="m-0 mb-1 px-0",
            )
        )

    return dbc.Row(
        items,
        className="g-2 mt-1",
        justify="start",
    )
