# src/web/pages/home.py

from dash_extensions.enrich import register_page, html

register_page(__name__, path="/")

layout = html.Div(
    [
        html.H3("Home"),
        html.Div("Welcome."),
    ]
)