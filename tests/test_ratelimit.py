from faceai.serving.ratelimit import RateLimiter, Rule, client_ip


def test_token_bucket_burst_then_refill():
    now = [0.0]
    rl = RateLimiter([Rule("/v1/auth/login", capacity=3, per_minute=60)], clock=lambda: now[0])
    assert [rl.check("/v1/auth/login", "1.1.1.1") for _ in range(3)] == [None, None, None]
    retry = rl.check("/v1/auth/login", "1.1.1.1")
    assert retry is not None and retry >= 1
    assert rl.check("/v1/auth/login", "2.2.2.2") is None  # doosra IP alag bucket
    now[0] += 1.0  # 60/min = 1 token/second
    assert rl.check("/v1/auth/login", "1.1.1.1") is None


def test_unlisted_paths_not_limited():
    rl = RateLimiter([Rule("/v1/auth/login", 1, 1)])
    assert all(rl.check("/v1/admin/students", "x") is None for _ in range(50))


def test_client_ip_trusts_xff_only_from_proxy():
    h = {"x-forwarded-for": "9.9.9.9, 10.0.0.2"}
    assert client_ip(h, "10.0.0.2", {"10.0.0.2"}) == "9.9.9.9"
    assert client_ip(h, "5.5.5.5", {"10.0.0.2"}) == "5.5.5.5"  # spoofed header ignored


def test_login_endpoint_rate_limited(app_client_rl):
    c = app_client_rl
    codes = [
        c.post("/v1/auth/login", json={"email": "x@y.in", "password": "nope"}).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
    r = c.post("/v1/auth/login", json={"email": "x@y.in", "password": "nope"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
