from worker import runtime as runtime_mod


def test_get_runtime_singleton():
    runtime_mod._RUNTIME = None
    r1 = runtime_mod.get_runtime()
    r2 = runtime_mod.get_runtime()
    assert r1 is r2


def test_model_runtime_predict():
    runtime_mod._RUNTIME = None
    r = runtime_mod.ModelRuntime()
    result = r.predict(5)
    assert result.startswith("processed click #5")