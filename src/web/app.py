# src/web/app.py

from dash_extensions.enrich import html, dcc, DashProxy, page_container, TriggerTransform, MultiplexerTransform
from shared.celery_app import bg_manager
from shared.db import init_db
from shared.logs import init_logs

init_logs()
init_db()

app = DashProxy(
    # external_stylesheets=[dbc.themes.BOOTSTRAP],
    name=__name__,
    title="MWE",
    update_title="MWE (r)",
    transforms=[TriggerTransform(), MultiplexerTransform()],
    use_pages=True,
    prevent_initial_callbacks=True,
    suppress_callback_exceptions=True,
    background_callback_manager=bg_manager,
)
server = app.server

app.layout = html.Div([
    html.H2("Dash + Pages"),
    dcc.Link("Home", href="/"),
    html.Br(),
    dcc.Link("Jobs", href="/jobs"),
    html.Hr(),
    page_container,
])

if __name__ == "__main__":
    app.run_server(debug=True)
