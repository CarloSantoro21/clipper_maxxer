"""Pruebas de la API del dashboard: datos temporales, sin red, sin Claude real y sin ffmpeg (render simulado)."""
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from clipforge import api, campaigns, config, pipeline, story  # noqa: E402
from clipforge.specs import Campaign, ClipSpec, StorySpec, Transcript, Word  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    data, camp_dir = tmp_path / "data", tmp_path / "campaigns"
    camp_dir.mkdir()
    for mod in (config, campaigns):
        monkeypatch.setattr(mod, "CAMPAIGNS", camp_dir)
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(story, "STORIES", data / "stories")

    campaigns.save_campaign(Campaign(slug="podcast", name="Podcast", account="tech-es", min_seconds=5,
                                     max_seconds=60, source_urls=["https://youtu.be/AAAAAAAAAAA"],
                                     required_hashtags=["ad"], banned=["casino"]))
    job = config.job_dir("demo")
    (job / "job.json").write_text(json.dumps({"job_id": "demo", "src": "x.mp4", "campaign": "podcast",
                                              "title": "Demo"}), encoding="utf-8")
    words = [Word(text=f"w{i}", start=i * 0.5, end=i * 0.5 + 0.4) for i in range(80)]
    (job / "transcript.json").write_text(Transcript(duration=40, words=words).model_dump_json(), encoding="utf-8")
    for cid, start, end in (("c01", 2, 20), ("c02", 22, 25)):
        spec = ClipSpec(id=cid, job_id="demo", campaign="podcast", source=str(job / "source.mp4"),
                        start=start, end=end, hook=f"Hook {cid}", title="Mira esto", hashtags=["tech"],
                        score=8, why="pega")
        (job / "specs" / f"{cid}.json").write_text(spec.model_dump_json(), encoding="utf-8")
    (job / "renders" / "c01.mp4").write_bytes(b"\x00" * 2048)

    s = StorySpec(id="mi-historia", title="Mi historia", hook="No lo vi venir", script="No lo vi venir. Fin.")
    story.save_story(s)

    app = api.create_app()
    client = TestClient(app)
    client.queue = app.state.queue
    return client


def _wait(client, task):
    return client.queue.wait(task["id"], timeout=10)


# ---------- jobs / clips ----------

def test_list_and_get_job(env):
    jobs = env.get("/api/jobs").json()
    assert [j["job_id"] for j in jobs] == ["demo"]
    job = env.get("/api/jobs/demo").json()
    c01, c02 = job["clips"]
    assert job["account"] == "tech-es" and job["has_transcript"]
    assert c01["video_url"].startswith("/media/jobs/demo/renders/c01.mp4?v=")
    assert c02["video_url"] is None
    assert c01["account"] == "tech-es" and c01["duration"] == 18
    assert "dura 3s" in c02["issues"][0]  # mínimo 5 s
    assert c01["published_url"] is None and c01["views"] is None
    assert env.get("/api/jobs/nope").status_code == 404
    assert env.get("/api/jobs/..%2Fetc").status_code in (400, 404)


def test_media_served_with_ranges(env):
    url = env.get("/api/jobs/demo").json()["clips"][0]["video_url"]
    r = env.get(url, headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100


def test_patch_clip_validates_and_merges(env):
    r = env.patch("/api/jobs/demo/clips/c01", json={
        "hook": "Nuevo hook", "end": 19.5, "hashtags": ["#uno", " dos "],
        "captions": {"highlight": "#00FF88", "words_per_line": 2}, "crop_x": 0.3,
        "status": "approved", "views": 1234, "platform": "tiktok", "published_at": "2026-10-01",
    })
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["hook"] == "Nuevo hook" and c["end"] == 19.5 and c["hashtags"] == ["uno", "dos"]
    assert c["captions"]["highlight"] == "#00FF88" and c["captions"]["preset"] == "karaoke"
    saved = json.loads((config.DATA / "jobs/demo/specs/c01.json").read_text(encoding="utf-8"))
    assert saved["captions"]["words_per_line"] == 2 and saved["views"] == 1234
    assert saved["published_at"] == "2026-10-01"

    assert env.patch("/api/jobs/demo/clips/c01", json={"end": 1}).status_code == 422       # end <= start
    assert env.patch("/api/jobs/demo/clips/c01", json={"crop_x": 2}).status_code == 422
    assert env.patch("/api/jobs/demo/clips/c01", json={"status": "viral"}).status_code == 422
    assert env.patch("/api/jobs/demo/clips/c01", json={"source": "/etc/passwd"}).status_code == 422
    assert env.patch("/api/jobs/demo/clips/c01", json={"captions": {"color": "rojo"}}).status_code == 422
    assert env.patch("/api/jobs/demo/clips/c09", json={"hook": "x"}).status_code == 404


def test_old_specs_without_metrics_still_load(env):
    p = config.DATA / "jobs/demo/specs/c02.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    for k in ("published_url", "platform", "views", "published_at"):
        d.pop(k)
    p.write_text(json.dumps(d), encoding="utf-8")
    assert env.get("/api/jobs/demo").json()["clips"][1]["views"] is None


def test_render_clip_uses_queue(env, monkeypatch):
    calls = []

    def fake_render(job_id, only=None, log=print):
        calls.append((job_id, list(only)))
        log("ok")
        return []

    monkeypatch.setattr(pipeline, "render_job", fake_render)
    t = env.post("/api/jobs/demo/clips/c02/render")
    assert t.status_code == 202
    done = _wait(env, t.json())
    assert done["status"] == "done" and calls == [("demo", ["c02"])]
    assert any("ok" in line for line in done["log"])
    assert env.get(f"/api/tasks/{done['id']}").json()["status"] == "done"
    assert env.get("/api/tasks").json()[0]["id"] == done["id"]

    env.patch("/api/jobs/demo/clips/c02", json={"status": "rejected"})
    assert env.post("/api/jobs/demo/clips/c02/render").status_code == 409


def test_new_job_runs_pipeline_and_checks_permission(env, monkeypatch):
    seen = []

    def fake_pipeline(src, campaign, n, log, progress):
        progress(0.5, "planeando")
        log("job: AAAAAAAAAAA")
        seen.append((src, campaign, n))
        return "AAAAAAAAAAA"

    monkeypatch.setattr(pipeline, "clip_pipeline", fake_pipeline)
    r = env.post("/api/jobs", json={"src": "https://youtu.be/AAAAAAAAAAA", "campaign": "podcast", "n": 3})
    assert r.status_code == 202
    done = _wait(env, r.json())
    assert done["status"] == "done" and done["result"]["job"] == "AAAAAAAAAAA"
    assert seen == [("https://youtu.be/AAAAAAAAAAA", "podcast", 3)]

    # link fuera de campaña: pide nota de permiso
    r = env.post("/api/jobs", json={"src": "https://youtu.be/BBBBBBBBBBB", "campaign": "podcast"})
    assert r.status_code == 409
    r = env.post("/api/jobs", json={"src": "https://youtu.be/BBBBBBBBBBB", "permission_note": "es mío"})
    assert r.status_code == 202
    assert env.post("/api/jobs", json={"src": "x", "campaign": "noexiste"}).status_code == 404


def test_task_errors_are_reported(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Falta ffmpeg")

    monkeypatch.setattr(pipeline, "render_job", boom)
    done = _wait(env, env.post("/api/jobs/demo/clips/c01/render").json())
    assert done["status"] == "error" and "ffmpeg" in done["error"]


# ---------- stories ----------

def test_stories_crud_and_render(env, monkeypatch):
    stories = env.get("/api/stories").json()
    assert stories[0]["id"] == "mi-historia" and stories[0]["account"] == "experimentos"
    r = env.patch("/api/stories/mi-historia", json={"hook": "Otro hook", "part": 2, "views": 10,
                                                    "captions": {"position": "upper"}})
    assert r.status_code == 200 and r.json()["part"] == 2 and r.json()["captions"]["position"] == "upper"
    assert env.patch("/api/stories/mi-historia", json={"id": "otro"}).status_code == 422
    assert env.get("/api/stories/nope").status_code == 404

    rendered = []
    monkeypatch.setattr(pipeline, "render_story_by_id", lambda sid, log=print: rendered.append(sid))
    assert _wait(env, env.post("/api/stories/mi-historia/render").json())["status"] == "done"

    def fake_write(premise, seconds, part):
        s = StorySpec(id="nueva", title="Nueva", hook="h", script="h. fin", part=part)
        story.save_story(s)
        return s

    monkeypatch.setattr(story, "write_story", fake_write)
    done = _wait(env, env.post("/api/stories", json={"premise": "Un vecino raro", "seconds": 60, "part": 1}).json())
    assert done["status"] == "done" and done["result"]["story"] == "nueva"
    assert rendered == ["mi-historia", "nueva"]


# ---------- campañas ----------

def test_campaigns_list_put(env):
    assert [c["slug"] for c in env.get("/api/campaigns").json()] == ["podcast"]
    body = {"slug": "nueva", "name": "Nueva", "account": "gaming-es", "max_seconds": 45}
    assert env.put("/api/campaigns", json=body).status_code == 200
    assert campaigns.load_campaign("nueva").account == "gaming-es"
    assert env.put("/api/campaigns", json={"slug": "../x", "name": "x"}).status_code == 400
    assert env.put("/api/campaigns", json={"slug": "x", "name": "x", "platforms": ["myspace"]}).status_code == 422
    assert env.get("/api/campaigns/nueva").json()["max_seconds"] == 45


def test_extract_campaign_returns_draft_without_saving(env, monkeypatch):
    captured = {}

    def fake_ask(prompt, schema, **kw):
        captured["prompt"], captured["schema"] = prompt, schema
        return {"slug": "Mi Campaña Tech", "name": "Tech", "rate_per_1k": 1.2,
                "required_hashtags": ["#ad"], "source_urls": ["https://youtu.be/CCCCCCCCCCC"],
                "active": True, "extra": "se ignora"}

    monkeypatch.setattr(api, "ask_json", fake_ask)
    r = env.post("/api/campaigns/extract", json={"text": "Paga $1.2 por 1K vistas. Usa #ad. Material: ..."})
    assert r.status_code == 200, r.text
    d = r.json()["draft"]
    assert d["slug"] == "mi-campa-a-tech" and d["required_hashtags"] == ["ad"] and d["active"] is False
    assert "Paga $1.2" in captured["prompt"] and "rate_per_1k" in captured["schema"]["properties"]
    assert not (config.CAMPAIGNS / f"{d['slug']}.yaml").exists()

    def fail(*a, **k):
        raise api.ClaudeError("sin sesión")

    monkeypatch.setattr(api, "ask_json", fail)
    assert env.post("/api/campaigns/extract", json={"text": "brief cualquiera aquí"}).status_code == 502


# ---------- chat ----------

def test_build_chat_command():
    cmd = api.build_chat_command(None, claude_bin="claude-fake-bin")
    assert cmd[:2] == ["claude-fake-bin", "-p"]
    assert cmd[cmd.index("--output-format") + 1] == "stream-json" and "--verbose" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    i = cmd.index("--allowedTools")
    assert cmd[i + 1:i + 6] == ["Bash(clipforge:*)", "Read", "Edit", "Glob", "Grep"]
    assert "--resume" not in cmd
    cmd = api.build_chat_command("abc-123", claude_bin="claude-fake-bin")
    assert cmd[-2:] == ["--resume", "abc-123"]


def test_context_line():
    line = api.context_line(api.ChatContext(job="demo", clip="c01"))
    assert "job=demo" in line and "data/jobs/demo/specs/c01.json" in line
    assert "ningún clip" in api.context_line(api.ChatContext())


def _lines(*events):
    return iter(json.dumps(e) + "\n" for e in events)


def test_stream_json_to_sse():
    out = "".join(api.stream_json_to_sse(_lines(
        {"type": "system", "subtype": "init", "session_id": "s1"},
        {"type": "stream_event", "session_id": "s1", "event": {"type": "message_start"}},
        {"type": "stream_event", "session_id": "s1",
         "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Listo, "}}},
        {"type": "assistant", "session_id": "s1", "message": {"content": [
            {"type": "text", "text": "Listo, "},
            {"type": "tool_use", "name": "Bash", "input": {"command": "clipforge render demo --only c01"}}]}},
        {"type": "assistant", "session_id": "s1", "message": {"content": [{"type": "text", "text": "re-renderizado."}]}},
        {"type": "result", "session_id": "s1", "is_error": False, "result": "x"},
    )))
    events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in out.strip().split("\n\n")]
    kinds = [k for k, _ in events]
    assert kinds == ["session", "text", "tool", "text", "done"]
    text = "".join(d["text"] for k, d in events if k == "text")
    assert text == "Listo, re-renderizado."  # sin duplicar lo que ya llegó por deltas
    assert events[2][1]["detail"].startswith("clipforge render")
    assert events[-1][1]["session_id"] == "s1"


def test_chat_endpoint_streams_sse(env, monkeypatch):
    captured = {}

    class FakeProc:
        returncode = 0
        stderr = None

        def __init__(self, cmd, cwd, **kw):
            captured["cmd"], captured["cwd"] = cmd, cwd
            import io
            self.stdin = io.StringIO()
            self.stdout = io.StringIO("".join(_lines(
                {"type": "system", "subtype": "init", "session_id": "sess-9"},
                {"type": "assistant", "session_id": "sess-9", "message": {"content": [{"type": "text", "text": "Hola"}]}},
                {"type": "result", "session_id": "sess-9", "is_error": False},
            )))
            self.stdin.close = lambda: captured.setdefault("prompt", self.stdin.getvalue())

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(api.shutil, "which", lambda exe: "/usr/bin/claude")
    monkeypatch.setattr(api.subprocess, "Popen", FakeProc)
    r = env.post("/api/chat", json={"message": "sube el hook", "session_id": "sess-8",
                                    "context": {"job": "demo", "clip": "c01"}})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert "event: text" in r.text and '"Hola"' in r.text and '"session_id": "sess-9"' in r.text
    assert captured["cmd"][-2:] == ["--resume", "sess-8"]
    assert captured["cwd"] == str(config.ROOT)
    assert captured["prompt"].startswith("[Contexto del dashboard: job=demo") and "sube el hook" in captured["prompt"]
