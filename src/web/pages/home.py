# src/web/pages/home.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import register_page, html

register_page(__name__, path="/")

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H1("Suite", className="display-5 fw-semibold"),
                            html.P(
                                "Welcome. Use Jobs to run and monitor background tasks.",
                                className="lead mb-4",
                            ),
                            dbc.Button("Open Jobs", href="/jobs", color="primary", size="lg"),
                        ]
                    ),
                    className="border-0 shadow-sm",
                ),
                lg=8,
                className="py-5",
            ),
            justify="center",
        )
    ],
    fluid=True,
    className="min-vh-100 d-flex align-items-center bg-body-tertiary",
)
