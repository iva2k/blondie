"""End-to-end test for the blondie.html wizard using Playwright."""

import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


def test_init_html_wizard_flow(tmp_path):
    """
    Load blondie.html in a headless browser, fill the form,
    click generate, and verify the downloaded zip file structure.
    """
    # Locate blondie.html relative to this test file
    root_dir = Path(__file__).parents[1]
    init_html_path = root_dir / "blondie.html"

    if not init_html_path.exists():
        pytest.fail(f"blondie.html not found at {init_html_path}")

    with sync_playwright() as p:
        try:
            # Launch browser. Headless is default.
            browser = p.chromium.launch()
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.skip(f"Failed to launch browser (run 'playwright install'?): {e}")
            return

        try:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            # Load the file via file:// protocol
            page.goto(init_html_path.as_uri())

            # Verify Title
            assert "Blondie Agent" in page.title()

            # --- Step 1: Secrets ---
            page.fill("#openai-key", "sk-mock-openai-key")
            page.fill("#anthropic-key", "sk-mock-anthropic-key")
            page.fill("#github-token", "ghp_mock_token")

            # --- Step 2: Project Details ---
            page.fill("#project-id", "my-awesome-agent")
            page.fill("#project-goal", "World domination via autonomous coding")

            # --- Step 3: Config ---
            page.select_option("#deployment-target", "docker")

            # --- Action: Generate ---
            # Set up download listener before clicking
            with page.expect_download() as download_info:
                page.click("button:has-text('Generate & Download Configuration')")

            download = download_info.value

            # Save to temp dir
            target_zip = tmp_path / "config.zip"
            download.save_as(target_zip)

            assert target_zip.exists()

            # --- Verification: Zip Content ---
            with zipfile.ZipFile(target_zip, "r") as z:
                files = z.namelist()

                # Check for critical files
                assert ".agent/secrets.env.yaml" in files
                assert ".agent/project.yaml" in files
                assert ".agent/SPEC.md" in files

                # Check Content: Secrets
                secrets_content = z.read(".agent/secrets.env.yaml").decode("utf-8")
                assert "sk-mock-openai-key" in secrets_content
                assert "ghp_mock_token" in secrets_content

                # Check Content: Project
                project_content = z.read(".agent/project.yaml").decode("utf-8")
                assert "id: my-awesome-agent" in project_content

            # --- Verification: UI Update ---
            # The 'next-steps' div should be visible
            assert page.locator("#next-steps").is_visible()

            # The final command should be populated
            cmd_text = page.locator("#final-command").inner_text()
            assert "docker run" in cmd_text
            assert "blondie:latest run" in cmd_text

        finally:
            browser.close()


def test_init_html_load_existing_zip(tmp_path):
    """
    Test loading a pre-existing zip file populates the form correctly.
    """
    root_dir = Path(__file__).parents[1]
    init_html_path = root_dir / "blondie.html"

    if not init_html_path.exists():
        pytest.fail(f"blondie.html not found at {init_html_path}")

    # Create a mock zip file
    mock_zip_path = tmp_path / "mock_config.zip"
    with zipfile.ZipFile(mock_zip_path, "w") as z:
        # secrets.env.yaml
        z.writestr(
            ".agent/secrets.env.yaml",
            """
llm:
  openai:
    api_key: "sk-loaded-openai"
  anthropic:
    api_key: "sk-loaded-anthropic"
git:
  github_token: "ghp_loaded_token"
""",
        )
        # project.yaml (with Vercel deploy to test inference)
        z.writestr(
            ".agent/project.yaml",
            """
id: loaded-project-id
commands:
  deploy: "vercel --prod --token {{secret:cloud.vercel.token}}"
""",
        )
        # SPEC.md
        z.writestr(
            ".agent/SPEC.md",
            """
# Product Spec

Goal: Loaded Goal
""",
        )

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.skip(f"Failed to launch browser: {e}")
            return

        try:
            page = browser.new_page()
            page.goto(init_html_path.as_uri())

            # Upload the zip file to the hidden input
            # Playwright handles hidden inputs for file uploads
            page.set_input_files("#zip-input", str(mock_zip_path))

            # Wait for JS to process the file and populate fields
            page.wait_for_function("document.getElementById('project-id').value === 'loaded-project-id'")

            # Verify fields
            assert page.input_value("#openai-key") == "sk-loaded-openai"
            assert page.input_value("#anthropic-key") == "sk-loaded-anthropic"
            assert page.input_value("#github-token") == "ghp_loaded_token"
            assert page.input_value("#project-id") == "loaded-project-id"
            assert page.input_value("#project-goal") == "Loaded Goal"
            assert page.input_value("#deployment-target") == "vercel"

        finally:
            browser.close()
