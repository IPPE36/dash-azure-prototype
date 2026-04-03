from dash_extensions.enrich import ALL, Input, Output, clientside_callback


def register_callbacks_home() -> None:
    clientside_callback(
        """
        function(clicks) {
            if (!clicks || !clicks.length) {
                return window.dash_clientside.no_update;
            }
            const ctx = dash_clientside.callback_context;
            if (!ctx || !ctx.triggered || !ctx.triggered.length) {
                return window.dash_clientside.no_update;
            }
            const propId = ctx.triggered[0].prop_id || "";
            const idStr = propId.split(".")[0];
            let idx = null;
            try {
                const parsed = JSON.parse(idStr);
                idx = parsed && parsed.index;
            } catch (e) {
                idx = null;
            }
            if (idx === null || idx === undefined) {
                return window.dash_clientside.no_update;
            }
            const el = document.getElementById("home-carousel");
            if (!el || !window.bootstrap) {
                return window.dash_clientside.no_update;
            }
            const carousel = window.bootstrap.Carousel.getOrCreateInstance(el);
            carousel.to(idx);
            return idx;
        }
        """,
        Output("home-carousel-jump", "data"),
        Input({"type": "home-carousel-jump", "index": ALL}, "n_clicks"),
    )
