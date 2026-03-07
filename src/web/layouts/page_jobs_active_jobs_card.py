
# src/web/layout/page_jobs_active_jobs_card.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc


def build_active_job_card(interval: int, width="30rem"):
    job_card = dbc.Card([
        dcc.ConfirmDialog(id="cnf_job", message=""),
        dcc.Store(id="task_id_current", data=None),
        dcc.Store(id="task_id_finished", data=None),
        dcc.Interval(id="poll", interval=interval, disabled=False, n_intervals=0, max_intervals=300),
        dbc.CardHeader([
            html.H5("Active Jobs", className="mb-2"),
            html.Div(
                dbc.InputGroup(
                    [
                        dbc.Input(id="inp_submit_job", type="text", maxLength=60, placeholder="Job Name"),
                        dbc.Button("Submit", id="btn_submit_job", size="sm", color="primary"),
                    ],
                    className="flex-grow-1 me-2"
                ),
            )
        ]),
        html.Div(id="crd_body_job"),
        dbc.CardFooter([
            html.Div(
                [
                    html.Span("Progress:", className="me-3"),
                    dbc.Progress(
                        id="progress",
                        value=0,
                        max=100,
                        color="primary",
                        className="flex-grow-1",
                        animated=False,
                    ),
                ],
                className="d-flex align-items-center",
            ),
        ]),
    ], style={"width": width})
    return job_card