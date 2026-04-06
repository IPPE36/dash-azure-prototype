
# src/web/layout/page_jobs.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, dash_table

from web.theme import ICON_SETTINGS
from web.plot_utils import DEFAULT_CONFIG
from web.layouts.settings import build_sliders, build_input_list


COLUMNS = [
    {"name": "ID", "id": "task_id", "editable": False},
    {"name": "", "id": "status_icon", "editable": False},
    {"name": "", "id": "status", "editable": False},
    {"name": "LABEL", "id": "task_name", "editable": True},
    {"name": "TAG", "id": "tag", "editable": False},
    {"name": "DATE", "id": "created_at", "editable": False},
]

# inputs = build_input_list(
#     row_list=[
#         # (level, label, avg, stddev, use_std, disabled, limit_min, limit_max, use_switch)
#         ("main", "Cost1", 80.0, None, False, False, 0, 1000, True),
#     ]
# )


def build_layout_jobs():

    sliders = build_sliders(
        row_list=[
            # (label, value, min_value, max_value, disabled)
            ("X1", 0, 0, 100, False),
            ("X2", 0, 0, 100, False),
            ("X3", 0, 0, 100, False),
            ("X4", 0, 0, 100, False),
            ("X5", 0, 0, 100, False),
            ("X6", 0, 0, 100, False),
            ("X7", 0, 0, 100, False),
            ("X8", 0, 0, 100, False),
            ("X9", 0, 0, 100, False),
        ]
    )
    
    objectives = html.Div([], id="jobs-obj-wrapper")
    objective_selector = dcc.Dropdown(
        id='jobs-obj-selector',
        multi=True,
        clearable=True,
        placeholder='Select Properties',
        options=[],  # load from repo
        value=[],
        className="w-100",
    )

    submit = dbc.InputGroup(
        [
            dbc.Input(
                id="jobs-submit-inp",
                type="text",
                maxLength=50,
                placeholder="New Job Name",
                style=dict(zIndex=2),
            ),
            dbc.Button(
                "Submit",
                id="jobs-submit-btn",
                color="primary",
                className="submit-btn",
                style=dict(zIndex=1),
            ),
        ],
    )

    settings_tabs = dbc.Tabs(
        [
            dbc.Tab(
                id="jobs-settings-tab-bounds-label",
                label="Boundaries",
                tab_id="jobs-settings-tab-bounds",
                children=[sliders],
                label_class_name="bounds-tab",
            ),
            dbc.Tab(
                id="jobs-settings-tab-objectives-label",
                label="Objectives",
                tab_id="jobs-settings-tab-objectives",
                children=[
                    dbc.Row([objective_selector]),
                    dbc.Row([objectives]),
                ],
                label_class_name="target-tab",
            ),
            dbc.Tab(
                id="jobs-settings-tab-submit-label",
                label="Submit",
                tab_id="jobs-settings-tab-submit",
                children=[submit],
                label_class_name="send-tab",
            ),
        ],
        id="jobs-settings-tabs",
        active_tab="jobs-settings-tab-bounds",
        className="app-tabs mb-4",
    )

    offcanvas_title = [
        html.I(className=ICON_SETTINGS),
        "Jobs / Add Task"
    ]

    offcanvas = dbc.Offcanvas(
        [settings_tabs],
        id="jobs-settings-offcanvas",
        title=offcanvas_title,
        is_open=False,
        placement="start",
        className="bg-light ps-1 pe-0 pt-0 pb-0",
        style={"minWidth": "50%"}
    )

    meta = [
        offcanvas,
        dcc.Store(id="jobs-current-id", data=None),
        dcc.Store(id="jobs-finished-id", data=None),
        dcc.Store(id="jobs-todelete-id", data=None),
        dcc.Interval(id="jobs-poll", interval=1000, disabled=False),
    ]

    spinner_wrap = html.Div(
        dbc.Spinner(
            id="jobs-spinner",
            size="md",
            color="info",
        ),
        id="jobs-spinner-wrap",
        style={
            "position": "absolute",
            "top": "0px",
            "right": "0px",
            "display": "none",
        },
    )

    history_alert = html.Div(
        [dbc.Alert("Empty user history, add a new optimization to continue!", color="info")],
        id="jobs-history-alert",
        hidden=True,
    )

    search_bar = dbc.InputGroup(
        [
            dbc.Input(
                id="jobs-search-inp",
                type="text",
                maxLength=50,
                placeholder="Search for Task...",
                style=dict(zIndex=2),
            ),
            dbc.Button(
                "",
                id="jobs-search-btn",
                color="light",
                className="search-btn",
                style=dict(zIndex=1),
            ),
        ],
        style={"minWidth": "220px", "maxWidth": "320px"},
    )

    history_header = html.Div(
        [
            dbc.Button(
                "New Task",
                id="jobs-add-btn",
                color="light",
                disabled=False,
                className="add-btn",
                style={"whiteSpace": "nowrap", "widht": "auto"}
            ),
            html.Div(search_bar, id="jobs-search-group"),
        ],
        className="d-flex gap-2 pt-3 pb-3",
    )

    progress_row = html.Div(
        [
            html.Span("Progress:", className="me-3"),
            dbc.Progress(
                id="jobs-progress",
                value=0,
                max=100,
                color="info",
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
    )

    progress_collapse = dbc.Collapse(
        progress_row,
        id="jobs-active-container-collapse",
        is_open=False,
    )

    table = dash_table.DataTable(
        id="jobs-table",
        columns=COLUMNS,
        row_deletable=False,
        editable=False,
        cell_selectable=False,
        row_selectable="single",
        style_as_list_view=True,
        page_size=10,
        style_header={
            "fontWeight": "bold",
            "textAlign": "right",
            "fontFamily": "inherit",
        },
        style_cell={
            "textAlign": "right",
            "fontFamily": "inherit",
        },
        hidden_columns=["task_id", "status"],
        css=[
            {"selector": ".show-hide", "rule": "display: none"},
            # {"selector": "tr:first-child", "rule": "display: none"},
        ],
        style_data_conditional=[
            {
                "if": {"column_id": "status_icon"},
                "color": "lightgray",
            },
            {
                "if": {
                    "filter_query": '{status} = "COMPLETED"',
                    "column_id": "status",
                },
                "color": "transparent",
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
                "color": "var(--bs-info)",
            },
        ],
    )

    table_wrap = html.Div(table)

    tag_input = dbc.InputGroup(
        [
            dbc.Input(
                id="jobs-tag-inp",
                type="text",
                maxLength=32,
                placeholder="Apply Tag (optional)",
                size="md",
                style=dict(zIndex=2),
            ),
            dbc.Button(
                "",
                id="jobs-tag-btn",
                size="md",
                color="light",
                className="tag-btn",
                disabled=True,
                style=dict(zIndex=1),
            ),
        ],
        className="jobs-tag-input",
        style={"minWidth": "220px", "maxWidth": "320px"},
    )

    actions_row = html.Div(
        [
            html.Div(
                [
                    dbc.Button(
                        "",
                        id="jobs-refresh-btn",
                        size="md",
                        color="light",
                        disabled=False,
                        className="refresh-btn",
                        style={"display": "none"}
                    ),
                    dbc.Button(
                        "Results",
                        id="jobs-result-btn",
                        size="md",
                        color="light",
                        disabled=True,
                        className="load-btn",
                    ),
                    dbc.Button(
                        "Delete",
                        id="jobs-delete-btn",
                        size="md",
                        color="light",
                        disabled=True,
                        className="delete-btn",
                    ),
                    tag_input
                ],
                className="d-flex gap-2",
            ),
        ],
        id="jobs-actions-group",
        hidden=True,
    )

    history_body = html.Div(
        [
            history_alert,
            history_header,
            progress_collapse,
            table_wrap,
            actions_row,
        ],
    )

    results_body = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Graph(
                            id="jobs-results-pareto-graph",
                            figure={
                                "data": [],
                                "layout": {
                                    "height": 320,
                                    "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
                                },
                            },
                            config=DEFAULT_CONFIG,
                        ),
                        xs=12,
                        md=6,
                        className="px-2",
                    ),
                    dbc.Col(
                        dcc.Graph(
                            id="jobs-results-detail-graph",
                            figure={
                                "data": [],
                                "layout": {
                                    "height": 320,
                                    "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
                                },
                            },
                            config=DEFAULT_CONFIG,
                        ),
                        xs=12,
                        md=6,
                        className="px-2",
                    ),
                ],
                className="g-3",
            )
        ],
    )

    history_tabs = dbc.Tabs(
        [
            dbc.Tab(
                label="History",
                tab_id="jobs-tab-history",
                label_class_name="history-tab",
                children=[history_body],
            ),
            dbc.Tab(
                label="Results",
                tab_id="jobs-tab-results",
                label_class_name="results-tab",
                children=[results_body],
            ),
        ],
        id="jobs-tabs",
        active_tab="jobs-tab-history",
        className="app-tabs ms-0 mb-4",
    )

    new_task_section = html.Div(
        [
            html.Div(
                [history_tabs, spinner_wrap],
                className="position-relative",
            ),
        ],
    )

    main = html.Div([new_task_section])

    return dbc.Container([main, *meta], className="app-main px-4 py-1")
