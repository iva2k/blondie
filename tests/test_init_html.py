"""End-to-end test for the blondie.html wizard using Playwright."""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="module", autouse=True)
def build_wizard():
    """Ensure blondie.html is built before running tests."""
    root_dir = Path(__file__).parents[1]
    script_path = root_dir / "scripts" / "build_wizard.py"

    # Run the build script
    subprocess.run([sys.executable, str(script_path)], check=True, cwd=root_dir)


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

            # Attach console listeners for debugging
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
            page.on("pageerror", lambda exc: print(f"BROWSER ERROR: {exc}"))

            # Handle dialogs (alerts) automatically but log them
            page.on("dialog", lambda dialog: print(f"BROWSER DIALOG: {dialog.message}") or dialog.accept())

            # Load the file via file:// protocol
            page.goto(init_html_path.as_uri())

            # Verify libraries loaded
            if not page.evaluate("typeof JSZip !== 'undefined'"):
                pytest.fail("JSZip library not loaded in browser. Check network/CDN access.")

            # Verify Title
            assert "Blondie Agent" in page.title()

            # --- Step 1: Project Definition ---
            page.fill("#project-id", "my-awesome-agent")
            page.fill("#git-repo-url", "https://github.com/test/repo.git")

            # --- Step 3: Template Selection (triggers secrets population) ---
            # Wait for templates to load and dropdown to populate
            page.wait_for_selector("#template-select option[value='basic']", state="attached")
            # Explicitly select 'basic' to trigger any change handlers
            page.select_option("#template-select", "basic")

            # --- Step 2: Secrets ---
            # These are now dynamic. Wait for them to appear.
            page.wait_for_selector("#openai-key")

            page.fill("#openai-key", "sk-mock-openai-key")
            page.fill("#anthropic-key", "sk-mock-anthropic-key")
            # Groq is in basic template
            if page.locator("#groq-key").is_visible():
                page.fill("#groq-key", "gsk_mock_groq_key")

            page.fill("#github-token", "ghp_mock_token")

            # --- Step 4: Project Details ---
            page.fill("#project-goal", "World domination via autonomous coding")
            page.fill("#initial-tasks", "Task A\nTask B")

            # --- Step 5: Configuration ---
            page.select_option("#deployment-target", "docker")

            # Toggle SSH
            page.check('input[name="git-auth"][value="ssh"]')

            # Upload dummy key
            dummy_key = tmp_path / "id_rsa_dummy"
            dummy_key.write_text("OPENSSH PRIVATE KEY", encoding="utf-8")
            page.set_input_files("#ssh-key-file", str(dummy_key))

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
                assert ".agent/TASKS.md" in files

                # Check Content: Secrets
                secrets_content = z.read(".agent/secrets.env.yaml").decode("utf-8")
                assert "sk-mock-openai-key" in secrets_content
                # Token should be empty because we switched to SSH
                assert "ghp_mock_token" not in secrets_content  # noqa: S105
                assert "gsk_mock_groq_key" in secrets_content

                # Check SSH Key
                ssh_key_content = z.read(".agent/ssh/id_rsa").decode("utf-8")
                assert "OPENSSH PRIVATE KEY" in ssh_key_content

                # Check Content: Project
                project_content = z.read(".agent/project.yaml").decode("utf-8")
                assert "id: my-awesome-agent" in project_content
                assert "git_repo: https://github.com/test/repo.git" in project_content

                # Check Content: Tasks
                tasks_content = z.read(".agent/TASKS.md").decode("utf-8")
                assert "Task A" in tasks_content
                assert "Task B" in tasks_content

            # --- Verification: UI Update ---
            # The 'next-steps' div should be visible
            assert page.locator("#next-steps").is_visible()

            # The mkdir command should be correct
            mkdir_text = page.locator("#next-step-mkdir").inner_text()
            assert "mkdir my-awesome-agent && cd my-awesome-agent" in mkdir_text

            # The final command should be populated
            cmd_text = page.locator("#final-command").inner_text()
            assert "docker run" in cmd_text
            assert "blondie:latest run" in cmd_text
            assert "/root/.ssh/id_rsa:ro" in cmd_text

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
git_repo: https://github.com/loaded/project.git
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
            assert page.input_value("#project-id") == "loaded-project-id"
            assert page.input_value("#git-repo-url") == "https://github.com/loaded/project.git"
            assert page.input_value("#openai-key") == "sk-loaded-openai"
            assert page.input_value("#anthropic-key") == "sk-loaded-anthropic"
            # HTTPS is default, so token input should be visible and populated
            assert page.input_value("#github-token") == "ghp_loaded_token"
            assert page.input_value("#project-goal") == "Loaded Goal"
            assert page.input_value("#deployment-target") == "vercel"

        finally:
            browser.close()
