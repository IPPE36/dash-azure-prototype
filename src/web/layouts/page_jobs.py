
# src/web/layout/page_jobs.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, dash_table

from web.theme import TRANSPARENT, ICON_SETTINGS
from web.layouts.settings import build_sliders



# settings_children = build_settings_input_list(
#     row_list=[
#         ("main", "Cost1", 80.0, None, False, False, 0, 1000, True),
#         ("main", "Cost2", 80.0, None, False, False, 0, 1000, True),
#         ("main", "Cost3", 80.0, None, False, False, 0, 1000, True),
#         ("main", "Cost4", 80.0, None, False, False, 0, 1000, True),
#         ("main", "Cost5", 80.0, None, False, False, 0, 1000, True),
#     ]
# )
# dd = build_settings_dropdown(options=["Steel", "Concrete", "Timber", "Aluminum"])

sliders = build_sliders(
    row_list=[
        ("Strength", 25, 0, 100, False),
        ("Pressure", 40, 10, 80, False),
        ("Locked value", 15, 0, 50, True),
        ("Pressure", 40, 10, 80, False),
        ("Pressure", 40, 10, 80, False),
        ("Locked value", 15, 0, 50, True),
        ("Pressure", 40, 10, 80, False),
        ("Pressure", 40, 10, 80, False),
        ("Locked value", 15, 0, 50, True),
        ("Pressure", 40, 10, 80, False),
        ("Pressure", 40, 10, 80, False),
        ("Locked value", 15, 0, 50, True),
    ]
)

COLUMNS = [
    {"name": "ID", "id": "task_id", "editable": False},
    {"name": "STATUS", "id": "status_icon", "editable": False},
    {"name": "STATUS", "id": "status", "editable": False},
    {"name": "LABEL", "id": "task_name", "editable": True},
    {"name": "VERSION", "id": "version", "editable": False},
    {"name": "DATE", "id": "created_at", "editable": False}
]


def build_jobs_layout():

    submit = dbc.InputGroup(
        [
            dbc.Input(
                id="jobs-submit-inp",
                type="text",
                maxLength=50,
                placeholder="New Job Name",
            ),
            dbc.Button(
                "Submit",
                id="jobs-submit-btn",
                color="secondary",
                className="submit-btn",
            ),
        ],
    )

    offcanvas = dbc.Offcanvas(
        [
            dbc.Tabs(
                [
                    dbc.Tab(
                        label="Boundaries",
                        tab_id="jobs-settings-tab-bounds",
                        children=[sliders],
                        label_class_name="bounds-btn",
                    ),
                    dbc.Tab(
                        label="Objectives",
                        tab_id="jobs-settings-tab-objectives",
                        children=[],
                        label_class_name="target-btn",
                    ),
                    dbc.Tab(
                        label="Submit",
                        tab_id="jobs-settings-tab-submit",
                        children=[submit],
                        label_class_name="send-btn",
                    ),
                ],
                id="jobs-settings-tabs",
                active_tab="jobs-settings-tab-bounds",
                className="app-tabs mb-3",
            ),
        ],
        id="jobs-settings-offcanvas",
        title=[
            html.I(className=ICON_SETTINGS),
            "Jobs / Add Task"
        ],
        is_open=False,
        placement="start",
        className="bg-light",
        style={"minWidth": "50%"}
    )

    meta = [
        offcanvas,
        dcc.Store(id="jobs-current-id", data=None),
        dcc.Store(id="jobs-finished-id", data=None),
        dcc.Store(id="jobs-todelete-id", data=None),
        dcc.Interval(id="jobs-poll", interval=1000, disabled=False),
    ]

    new_task_section = html.Div(
        [
            html.Div(
                [
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                label="Task History",
                                tab_id="jobs-tab-history",
                                label_class_name="history-btn",
                            ),
                            dbc.Tab(
                                label="Results",
                                tab_id="jobs-tab-results",
                                label_class_name="results-btn",
                            ),
                        ],
                        id="jobs-tabs",
                        active_tab="jobs-tab-history",
                        className="app-tabs mb-3",
                    ),

                    html.Div(
                        dbc.Spinner(
                            id="jobs-spinner",
                            size="md",
                            color="primary",
                        ),
                        id="jobs-spinner-wrap",
                        style={
                            "position": "absolute",
                            "top": "0px",
                            "right": "0px",
                            "display": "none",
                        },
                    ),
                ],
                className="position-relative",
            ),
        ],
        className="mb-3",
    )

    history_section = dbc.Collapse(
        [
            html.Div(
                [
                    dbc.Alert("This is a primary alert", color="primary"),
                ],
            ),
            html.Div(
                [
                    dbc.Button(
                        "New Task",
                        id="jobs-add-btn",
                        color="secondary",
                        disabled=False,
                        className="add-btn",
                        style={"whiteSpace": "nowrap", "widht": "auto"}
                    ),
                    dbc.InputGroup(
                        [
                            dbc.Input(
                                id="jobs-search-inp",
                                type="text",
                                maxLength=50,
                                placeholder="Search for Task...",
                            ),
                            dbc.Button(
                                "",
                                id="jobs-search-btn",
                                color="secondary",
                                className="search-btn",
                            ),
                        ],
                    ),
                ],
                className="d-flex gap-5 pt-3 pb-3",
            ),
            dbc.Collapse(
                html.Div(
                    [
                        html.Span("Progress:", className="me-3"),
                        dbc.Progress(
                            id="jobs-progress",
                            value=0,
                            max=100,
                            color="primary",
                            className="flex-grow-1 me-3",
                        ),
                        html.Div(
                            "0%",
                            id="jobs-progress-text",
                            style={
                                "minWidth": "45px",
                                "textAlign": "right",
                            },
                        ),
                    ],
                    className="d-flex align-items-center",
                ),
                id="jobs-active-container-collapse",
                is_open=False,
            ),

            html.Div(
                dash_table.DataTable(
                    id="jobs-table",
                    columns=COLUMNS,
                    row_deletable=False,
                    editable=False,
                    cell_selectable=False,
                    row_selectable="single",
                    style_as_list_view=True,
                    page_size=10,
                    style_header={"display": "none"},
                    style_cell={
                        "backgroundColor": TRANSPARENT,
                        "textAlign": "left",
                        "fontFamily": "inherit",
                    },
                    hidden_columns=["task_id"],
                    css=[
                        {"selector": ".show-hide", "rule": "display: none"},
                        {"selector": "tr:first-child", "rule": "display: none"},
                    ],
                    style_data_conditional=[
                        {
                            "if": {"column_id": "status_icon"},
                            "color": "lightgray",
                        },
                        {
                            "if": {
                                "filter_query": '{status} = "COMPLETED"',
                                "column_id": "status_icon",
                            },
                            "color": "white",
                        },
                        {
                            "if": {
                                "filter_query": '{status} = "ABORTED"',
                                "column_id": "status_icon",
                            },
                            "color": "red",
                        },
                        {
                            "if": {
                                "filter_query": '{status} = "RUNNING"',
                                "column_id": "status_icon",
                            },
                            "color": "var(--bs-primary)",
                        },
                    ],
                ),
            ),

            html.Div(
                [
                    dbc.Button(
                        "",
                        id="jobs-refresh-btn",
                        size="sm",
                        color="secondary",
                        disabled=False,
                        className="refresh-btn",
                        style={"display": "none"}
                    ),
                    dbc.Button(
                        "Load Results",
                        id="jobs-result-btn",
                        size="sm",
                        color="secondary",
                        disabled=True,
                        className="load-btn",
                    ),
                    dbc.Button(
                        "Delete",
                        id="jobs-delete-btn",
                        size="sm",
                        color="secondary",
                        disabled=True,
                        className="delete-btn",
                    ),
                ],
                className="d-flex gap-2 mt-1",
            ),
        ],
        id="jobs-history-container",
        is_open=True,
    )

    results_section = dbc.Collapse(
        [
            dcc.Graph(
                id="jobs-results-graph",
                figure={
                    "data": [],
                    "layout": {
                        "height": 320,
                        "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
                    },
                },
                config={"displayModeBar": False},
            )
        ],
        id="jobs-results-container",
        is_open=False,
    )

    main = html.Div(
        [
            new_task_section,
            history_section,
            results_section,
        ]
    )

    return dbc.Container([main, *meta], className="app-main p-3 pt-1")
