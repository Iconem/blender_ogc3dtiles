import io
import json

import pytest

from blender_ogc3dtiles import aggregate as ag


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(seen, name="upload-" + "a" * 32):
    def open_(req, timeout=0):
        seen.append((req.full_url, req.get_method(), json.loads(req.data.decode("utf-8"))))
        return _Resp(json.dumps({"set": name, "count": 1}).encode())
    return open_


def test_a_bare_word_is_a_set_name():
    assert ag.is_set_name("opendata") and ag.is_set_name("iconem-open")
    assert not ag.is_set_name("sets.json")
    assert not ag.is_set_name(r"\\nas\share\iconem.json")
    assert not ag.is_set_name("C:/data/iconem.json")


def test_set_url():
    assert ag.set_url("https://h.example/", "opendata") == "https://h.example/aggregate/tileset.json?set=opendata"
    assert ag.set_url("", "opendata", "&nest=geodetic").startswith(ag.DEFAULT_SERVER + "/aggregate/tileset.json?set=opendata&nest=geodetic")
    assert ag.tileset_url("https://h.example", "opendata", "nest=flat") == "https://h.example/aggregate/tileset.json?set=opendata&nest=flat"
    assert ag.tileset_url("https://h.example", "  ") == ""


def test_a_manifest_is_posted_on_start_only(tmp_path):
    f = tmp_path / "team.json"
    f.write_text(json.dumps({"label": "Team", "entries": [{"url": "https://x.example/a/cloud.js", "format": "potree"}]}))
    seen = []
    assert ag.tileset_url("https://h.example", str(f), opener=_opener(seen)) == ""      # never sent yet
    assert not seen
    url = ag.tileset_url("https://h.example", str(f), "nest=geodetic", post=True, opener=_opener(seen))
    assert url == "https://h.example/aggregate/tileset.json?set=upload-" + "a" * 32 + "&nest=geodetic"
    assert seen[0][0] == "https://h.example/aggregate/set" and seen[0][1] == "POST"
    assert seen[0][2]["entries"][0]["format"] == "potree"
    assert ag.tileset_url("https://h.example", str(f), "nest=geodetic", opener=_opener(seen)) == url   # remembered
    assert len(seen) == 1


def test_a_bad_manifest_says_why(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{}")
    with pytest.raises(ValueError, match="entries"):
        ag.tileset_url("https://h.example", str(f), post=True, opener=_opener([]))
    f.write_text(json.dumps([{"url": "ftp://x"}]))
    with pytest.raises(ValueError, match="entry 0"):
        ag.read_manifest(str(f))
    with pytest.raises(ValueError, match="not found"):
        ag.tileset_url("https://h.example", str(tmp_path / "none.json"), post=True, opener=_opener([]))


def test_max_km_hides_the_wide_datasets():
    index = {"datasets": [{"id": "small", "radius": 4000.0}, {"id": "wide", "radius": 30000.0},
                          {"id": "unknown"}, {"id": "edge", "radius": 10000.0}]}
    assert ag.wide_ids(index, 20.0) == ["wide"]
    assert ag.split_max_km("nest=geodetic&max_km=20") == ("nest=geodetic", 20.0)
    assert ag.split_max_km("&nest=geodetic") == ("nest=geodetic", None)
    seen = []

    def open_(req, timeout=0):
        seen.append(req.full_url)
        return _Resp(json.dumps(index).encode())
    assert ag.tileset_url("https://k.example", "open", "nest=geodetic&max_km=20", opener=open_) == ""   # not read yet
    url = ag.tileset_url("https://k.example", "open", "nest=geodetic&max_km=20", post=True, opener=open_)
    assert seen == ["https://k.example/aggregate/index.json?set=open&nest=geodetic"]
    assert url == "https://k.example/aggregate/tileset.json?set=open&nest=geodetic&hide=wide"
    assert ag.tileset_url("https://k.example", "open", "nest=geodetic&max_km=20", opener=open_) == url
    assert len(seen) == 1
