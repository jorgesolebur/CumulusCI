#!/usr/bin/env python3
"""Simple test runner for SFDmu tests."""

import os
import sys
import tempfile
from unittest import mock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from cumulusci.tasks.salesforce.tests.util import create_task
from cumulusci.tasks.sfdmu.sfdmu import SfdmuTask


def test_create_execute_directory():
    """Test _create_execute_directory creates directory and copies files."""
    with tempfile.TemporaryDirectory() as base_dir:
        # Create test files
        export_json = os.path.join(base_dir, "export.json")
        test_csv = os.path.join(base_dir, "test.csv")
        test_txt = os.path.join(base_dir, "test.txt")  # Should not be copied

        with open(export_json, "w") as f:
            f.write('{"test": "data"}')
        with open(test_csv, "w") as f:
            f.write("col1,col2\nval1,val2")
        with open(test_txt, "w") as f:
            f.write("text file")

        # Create subdirectory (should not be copied)
        subdir = os.path.join(base_dir, "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "file.txt"), "w") as f:
            f.write("subdir file")

        task = create_task(
            SfdmuTask, {"source": "dev", "target": "qa", "path": base_dir}
        )

        execute_path = task._create_execute_directory(base_dir)

        # Check that execute directory was created
        assert os.path.exists(execute_path)
        assert execute_path == os.path.join(base_dir, "execute")

        # Check that files were copied
        assert os.path.exists(os.path.join(execute_path, "export.json"))
        assert os.path.exists(os.path.join(execute_path, "test.csv"))
        assert not os.path.exists(
            os.path.join(execute_path, "test.txt")
        )  # Not a valid file type
        assert not os.path.exists(os.path.join(execute_path, "subdir"))  # Not a file

        # Check file contents
        with open(os.path.join(execute_path, "export.json"), "r") as f:
            assert f.read() == '{"test": "data"}'
        with open(os.path.join(execute_path, "test.csv"), "r") as f:
            assert f.read() == "col1,col2\nval1,val2"

        print("✅ test_create_execute_directory passed")


def test_inject_namespace_tokens_csvfile_target():
    """Test that namespace injection is skipped when both source and target are csvfile."""
    with tempfile.TemporaryDirectory() as execute_dir:
        # Create test files
        test_json = os.path.join(execute_dir, "test.json")
        with open(test_json, "w") as f:
            f.write('{"field": "%%%NAMESPACE%%%Test"}')

        # Create export.json file
        export_json_path = os.path.join(execute_dir, "export.json")
        with open(export_json_path, "w") as f:
            f.write('{"test": "data"}')

        task = create_task(
            SfdmuTask, {"source": "csvfile", "target": "csvfile", "path": execute_dir}
        )

        # Should not raise any errors and files should remain unchanged
        task._inject_namespace_tokens(execute_dir, None, None)

        # Check that file content was not changed
        with open(test_json, "r") as f:
            assert f.read() == '{"field": "%%%NAMESPACE%%%Test"}'

        print("✅ test_inject_namespace_tokens_csvfile_target passed")


def test_inject_namespace_tokens_managed_mode():
    """Test namespace injection in managed mode."""
    with tempfile.TemporaryDirectory() as execute_dir:
        # Create test files with namespace tokens
        test_json = os.path.join(execute_dir, "test.json")
        test_csv = os.path.join(execute_dir, "test.csv")

        with open(test_json, "w") as f:
            f.write(
                '{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}'
            )
        with open(test_csv, "w") as f:
            f.write("Name,%%%NAMESPACE%%%Field\nTest,Value")

        # Create filename with namespace token
        filename_with_token = os.path.join(execute_dir, "___NAMESPACE___test.json")
        with open(filename_with_token, "w") as f:
            f.write('{"test": "data"}')

        # Create export.json file
        export_json_path = os.path.join(execute_dir, "export.json")
        with open(export_json_path, "w") as f:
            f.write('{"test": "data"}')

        task = create_task(
            SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
        )

        # Mock the project config namespace
        task.project_config.project__package__namespace = "testns"

        mock_org_config = mock.Mock()
        mock_org_config.namespace = "testns"

        # Mock determine_managed_mode to return True
        with mock.patch(
            "cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode", return_value=True
        ):
            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

        # Check that namespace tokens were replaced in content
        with open(test_json, "r") as f:
            content = f.read()
            assert "testns__Test" in content
            assert "testns__Value" in content

        with open(test_csv, "r") as f:
            content = f.read()
            assert "testns__Field" in content

        # Check that filename token was replaced
        expected_filename = os.path.join(execute_dir, "testns__test.json")
        assert os.path.exists(expected_filename)
        assert not os.path.exists(filename_with_token)

        print("✅ test_inject_namespace_tokens_managed_mode passed")


def test_inject_namespace_tokens_unmanaged_mode():
    """Test namespace injection in unmanaged mode."""
    with tempfile.TemporaryDirectory() as execute_dir:
        # Create test files with namespace tokens
        test_json = os.path.join(execute_dir, "test.json")
        with open(test_json, "w") as f:
            f.write(
                '{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}'
            )

        # Create export.json file
        export_json_path = os.path.join(execute_dir, "export.json")
        with open(export_json_path, "w") as f:
            f.write('{"test": "data"}')

        task = create_task(
            SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
        )

        # Mock the project config namespace
        task.project_config.project__package__namespace = "testns"

        mock_org_config = mock.Mock()
        mock_org_config.namespace = "testns"

        # Mock determine_managed_mode to return False
        with mock.patch(
            "cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode", return_value=False
        ):
            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

        # Check that namespace tokens were replaced with empty strings
        with open(test_json, "r") as f:
            content = f.read()
            assert "Test" in content  # %%NAMESPACE%% removed
            assert "Value" in content  # %%NAMESPACED_ORG%% removed
            assert "%%%NAMESPACE%%%" not in content
            assert "%%%NAMESPACED_ORG%%%" not in content

        print("✅ test_inject_namespace_tokens_unmanaged_mode passed")


def main():
    """Run all tests."""
    print("Running SFDmu tests...")

    try:
        test_create_execute_directory()
        test_inject_namespace_tokens_csvfile_target()
        test_inject_namespace_tokens_managed_mode()
        test_inject_namespace_tokens_unmanaged_mode()

        print("\n🎉 All tests passed!")
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
