from __future__ import annotations

import threading

import pytest

pytest.importorskip("PIL")

import spotify_matrix


class FakeSpotify:
    def __init__(self, responses):
        self.responses = list(responses)

    def get_currently_playing(self):
        if not self.responses:
            raise KeyboardInterrupt()
        return self.responses.pop(0)


def playback(key: str, is_playing: bool = True):
    return {
        "is_playing": is_playing,
        "item": {
            "id": key,
            "type": "track",
            "name": f"Track {key}",
            "artists": [{"name": "Artist"}],
            "album": {
                "images": [
                    {
                        "url": f"https://example.com/{key}.png",
                        "height": 64,
                        "width": 64,
                    }
                ]
            },
        },
    }


def run_poll_once(monkeypatch, responses):
    events = []

    def fake_emit(event_api_url, event, payload):
        events.append((event_api_url, event, payload))

    monkeypatch.setattr(spotify_matrix, "emit_display_event", fake_emit)
    monkeypatch.setattr(spotify_matrix, "download_image", lambda url: None)

    try:
        spotify_matrix.poll_spotify(
            FakeSpotify(responses),
            spotify_matrix.SharedPlaybackState(),
            threading.Lock(),
            threading.Event(),
            0.001,
            "http://127.0.0.1:3000/api/display/events",
        )
    except KeyboardInterrupt:
        pass
    return events


def test_spotify_poll_emits_playback_started_once_per_track(monkeypatch):
    events = run_poll_once(monkeypatch, [playback("a", True), playback("a", True), playback("b", True)])

    assert [event for _, event, _ in events] == ["spotify.playback_started", "spotify.playback_started"]
    assert events[0][2]["artKey"] == "a"
    assert events[1][2]["artKey"] == "b"


def test_spotify_poll_emits_pause_and_stop_transitions(monkeypatch):
    events = run_poll_once(monkeypatch, [playback("a", True), playback("a", False), None])

    assert [event for _, event, _ in events] == [
        "spotify.playback_started",
        "spotify.playback_paused",
        "spotify.playback_stopped",
    ]
