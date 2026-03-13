#!/usr/bin/env python3
# scripts/build_wizard.py

"""Build the standalone blondie.html wizard by injecting templates."""

import json
from pathlib import Path


def main() -> None:
    """Read templates and inject into blondie.template.html."""
    root_dir = Path(__file__).parents[1]
    templates_dir = root_dir / "templates"
    template_html_path = root_dir / "blondie.template.html"
    output_html_path = root_dir / "blondie.html"

    if not templates_dir.exists():
        print(f"Error: Templates directory not found: {templates_dir}")
        return

    if not template_html_path.exists():
        print(f"Error: HTML template not found: {template_html_path}")
        return

    print(f"Reading templates from {templates_dir}...")
    templates_data: dict[str, dict[str, str]] = {}

    # Iterate over subdirectories in templates/ (e.g., basic, python, node)
    for template_path in templates_dir.iterdir():
        if not template_path.is_dir():
            continue

        template_name = template_path.name
        templates_data[template_name] = {}
        print(f"  - Found template: {template_name}")

        # Recursively read files in the template directory
        for file_path in template_path.rglob("*"):
            if file_path.is_file():
                # Store relative path as key (e.g., ".agent/project.yaml")
                rel_path = file_path.relative_to(template_path).as_posix()
                try:
                    content = file_path.read_text(encoding="utf-8")
                    templates_data[template_name][rel_path] = content
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"    Warning: Skipping {rel_path}: {e}")

    # Serialize to JSON
    json_data = json.dumps(templates_data, indent=None)  # Minified JSON

    # Read HTML template
    html_content = template_html_path.read_text(encoding="utf-8")

    # Inject data
    placeholder = "// __TEMPLATES_JSON_PLACEHOLDER__"
    injection = f"TEMPLATES = {json_data};"

    if placeholder not in html_content:
        print("Error: Placeholder '// __TEMPLATES_JSON_PLACEHOLDER__' not found in HTML template.")
        return

    final_html = html_content.replace(placeholder, injection)
    output_html_path.write_text(final_html, encoding="utf-8")
    print(f"Generated {output_html_path} ({len(final_html)} bytes)")


if __name__ == "__main__":
    main()
