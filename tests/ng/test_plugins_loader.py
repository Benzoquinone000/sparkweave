"""Tests for NG playground plugin manifest discovery."""

from __future__ import annotations

from sparkweave.plugins.loader import discover_plugins, load_plugin_manifest


def test_discover_plugins_loads_child_yaml_manifest(tmp_path) -> None:
    plugin_dir = tmp_path / "demo_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.yaml").write_text(
        "\n".join(
            [
                "name: demo_plugin",
                "type: playground",
                "description: Demo plugin",
                "version: 1.2.3",
                "author: SparkWeave",
                "stages: [plan, answer]",
                "entrypoint: demo.module:Plugin",
            ]
        ),
        encoding="utf-8",
    )

    manifests = discover_plugins([tmp_path])

    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest.name == "demo_plugin"
    assert manifest.type == "playground"
    assert manifest.stages == ["plan", "answer"]
    assert manifest.entrypoint == "demo.module:Plugin"
    assert manifest.to_dict()["version"] == "1.2.3"


def test_load_plugin_manifest_supports_direct_json_manifest(tmp_path) -> None:
    plugin_dir = tmp_path / "json_plugin"
    plugin_dir.mkdir()
    manifest_path = plugin_dir / "plugin.json"
    manifest_path.write_text(
        """
        {
          "name": "json_plugin",
          "type": "playground",
          "description": "JSON plugin",
          "stages": "draft, review"
        }
        """,
        encoding="utf-8",
    )

    manifest = load_plugin_manifest(manifest_path)

    assert manifest.name == "json_plugin"
    assert manifest.description == "JSON plugin"
    assert manifest.stages == ["draft", "review"]
    assert discover_plugins([plugin_dir]) == [manifest]


def test_discover_plugins_keeps_first_manifest_for_duplicate_names(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "manifest.yaml").write_text(
        "name: duplicate_plugin\ndescription: First\n",
        encoding="utf-8",
    )
    (second / "manifest.yaml").write_text(
        "name: duplicate_plugin\ndescription: Second\n",
        encoding="utf-8",
    )

    manifests = discover_plugins([tmp_path])

    assert len(manifests) == 1
    assert manifests[0].description == "First"

