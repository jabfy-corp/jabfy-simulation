"""Unit tests for the SmartTV device state machine."""

from sim.devices.entertainment import SmartTV, VALID_SOURCES


def make_tv(**kwargs) -> SmartTV:
    defaults = dict(id="living_tv", location="salon", topic_prefix="http/living_tv")
    return SmartTV(**{**defaults, **kwargs})


class TestSmartTV:
    def test_initial_state_off(self):
        tv = make_tv()
        state = tv.get_state()
        assert state["switch"] == "off"
        assert state["volume"] == 30
        assert state["mute"] is False
        assert state["inputSource"] == "HDMI1"
        assert state["app"] is None

    def test_turn_on(self):
        tv = make_tv()
        r = tv.apply_command("turn_on")
        assert r.success
        assert tv.get_state()["switch"] == "on"

    def test_turn_off(self):
        tv = make_tv(state=True)
        r = tv.apply_command("turn_off")
        assert r.success
        assert tv.get_state()["switch"] == "off"

    def test_toggle(self):
        tv = make_tv()
        tv.apply_command("toggle")
        assert tv.get_state()["switch"] == "on"
        tv.apply_command("toggle")
        assert tv.get_state()["switch"] == "off"

    def test_set_volume(self):
        tv = make_tv(state=True)
        r = tv.apply_command("set_volume", {"volume": 50})
        assert r.success
        assert tv.get_state()["volume"] == 50

    def test_set_volume_clamped(self):
        tv = make_tv(state=True)
        tv.apply_command("set_volume", {"volume": 200})
        assert tv.get_state()["volume"] == 100
        tv.apply_command("set_volume", {"volume": -10})
        assert tv.get_state()["volume"] == 0

    def test_volume_zero_sets_muted(self):
        tv = make_tv(state=True)
        tv.apply_command("set_volume", {"volume": 0})
        assert tv.get_state()["mute"] is True

    def test_volume_up_down(self):
        tv = make_tv(state=True, volume=50)
        tv.apply_command("volume_up", {"step": 10})
        assert tv.get_state()["volume"] == 60
        tv.apply_command("volume_down", {"step": 20})
        assert tv.get_state()["volume"] == 40

    def test_mute_unmute(self):
        tv = make_tv(state=True)
        tv.apply_command("mute")
        assert tv.get_state()["mute"] is True
        tv.apply_command("unmute")
        assert tv.get_state()["mute"] is False

    def test_set_source_valid(self):
        tv = make_tv(state=True)
        r = tv.apply_command("set_source", {"source": "HDMI2"})
        assert r.success
        assert tv.get_state()["inputSource"] == "HDMI2"

    def test_set_source_invalid(self):
        tv = make_tv(state=True)
        r = tv.apply_command("set_source", {"source": "INVALID"})
        assert not r.success

    def test_select_source_alias(self):
        tv = make_tv(state=True)
        r = tv.apply_command("select_source", {"source": "Netflix"})
        assert r.success

    def test_launch_app(self):
        tv = make_tv(state=True)
        r = tv.apply_command("launch_app", {"app": "Netflix"})
        assert r.success
        assert tv.get_state()["app"] == "Netflix"

    def test_commands_fail_when_off(self):
        tv = make_tv(state=False)
        for cmd, params in [
            ("set_volume", {"volume": 50}),
            ("mute", {}),
            ("unmute", {}),
            ("set_source", {"source": "HDMI1"}),
            ("launch_app", {"app": "test"}),
        ]:
            r = tv.apply_command(cmd, params)
            assert not r.success, f"Expected failure for {cmd} when TV is off"

    def test_unknown_action(self):
        tv = make_tv()
        r = tv.apply_command("explode")
        assert not r.success

    def test_case_insensitive(self):
        tv = make_tv()
        tv.apply_command("TURN_ON")
        assert tv.get_state()["switch"] == "on"

    def test_turn_off_clears_app(self):
        tv = make_tv(state=True)
        tv.apply_command("launch_app", {"app": "YouTube"})
        assert tv.get_state()["app"] == "YouTube"
        tv.apply_command("turn_off")
        assert tv.get_state()["app"] is None

    def test_topics(self):
        tv = make_tv()
        assert tv.telemetry_topic == "http/living_tv"
        assert tv.command_topic == "http/living_tv/set"

    def test_tick_telemetry(self):
        tv = make_tv(telemetry_interval_ms=500)
        assert tv.tick(300) is False
        assert tv.tick(250) is True   # 550ms ≥ 500ms

    def test_all_valid_sources(self):
        """All declared VALID_SOURCES should be accepted."""
        tv = make_tv(state=True)
        for src in VALID_SOURCES:
            r = tv.apply_command("set_source", {"source": src})
            assert r.success, f"Source {src!r} should be valid"
