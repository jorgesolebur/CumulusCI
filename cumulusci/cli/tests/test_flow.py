from unittest import mock

import click
import pytest

from cumulusci.cli.runtime import CliRuntime
from cumulusci.core.config import FlowConfig, OrgConfig
from cumulusci.core.exceptions import CumulusCIException, FlowNotFoundError
from cumulusci.core.flowrunner import FlowCoordinator, FlowStepSpec, StepSpec
from cumulusci.tests.util import create_project_config

from .. import flow
from .utils import DummyTask, run_click_command


@mock.patch("cumulusci.cli.flow.CliTable")
def test_flow_list(cli_tbl):
    runtime = mock.Mock()
    runtime.get_available_flows.return_value = [
        {"name": "test_flow", "description": "Test Flow", "group": "Testing"}
    ]
    runtime.universal_config.cli__plain_output = None
    run_click_command(flow.flow_list, runtime=runtime, plain=False, print_json=False)

    cli_tbl.assert_called_with(
        [["Flow", "Description"], ["test_flow", "Test Flow"]],
        "Testing",
    )


@mock.patch("json.dumps")
def test_flow_list_json(json_):
    flows = [{"name": "test_flow", "description": "Test Flow"}]
    runtime = mock.Mock()
    runtime.get_available_flows.return_value = flows
    runtime.universal_config.cli__plain_output = None

    run_click_command(flow.flow_list, runtime=runtime, plain=False, print_json=True)

    json_.assert_called_with(flows)


@mock.patch("click.echo")
def test_flow_info(echo):

    runtime = CliRuntime(
        config={
            "flows": {
                "test": {
                    "steps": {
                        1: {
                            "task": "test_task",
                            "options": {"option_name": "option_value"},
                        }
                    }
                }
            },
            "tasks": {
                "test_task": {
                    "class_path": "cumulusci.cli.tests.test_flow.DummyTask",
                    "description": "Test Task",
                }
            },
        },
        load_keychain=False,
    )

    run_click_command(flow.flow_info, runtime=runtime, flow_name="test")

    echo.assert_called_with(
        "\nFlow Steps\n1) task: test_task [from current folder]\n   options:\n       option_name: option_value"
    )


def test_flow_info__not_found():
    runtime = mock.Mock()
    runtime.get_flow.side_effect = FlowNotFoundError
    with pytest.raises(click.UsageError):
        run_click_command(flow.flow_info, runtime=runtime, flow_name="test")


@mock.patch("cumulusci.cli.flow.group_items")
@mock.patch("cumulusci.cli.flow.document_flow")
def test_flow_doc__no_flows_rst_file(doc_flow, group_items):
    runtime = mock.Mock()
    runtime.universal_config.flows = {"test": {}}
    flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
    runtime.get_flow.return_value = FlowCoordinator(None, flow_config)

    group_items.return_value = {"Group One": [["test flow", "description"]]}

    run_click_command(flow.flow_doc, runtime=runtime)
    group_items.assert_called_once()
    doc_flow.assert_called()


@mock.patch("click.echo")
@mock.patch("cumulusci.cli.flow.load_yaml_data")
def test_flow_doc__with_flows_rst_file(load_yaml_data, echo):
    runtime = CliRuntime(
        config={
            "flows": {
                "Flow1": {
                    "steps": {},
                    "description": "Description of Flow1",
                    "group": "Group1",
                }
            }
        },
    )

    load_yaml_data.return_value = {
        "intro_blurb": "opening blurb for flow reference doc",
        "groups": {
            "Group1": {"description": "This is a description of group1."},
        },
        "flows": {"Flow1": {"rst_text": "Some ``extra`` **pizzaz**!"}},
    }

    run_click_command(flow.flow_doc, runtime=runtime, project=True)

    assert 1 == load_yaml_data.call_count

    expected_call_args = [
        "Flow Reference\n==========================================\n\nopening blurb for flow reference doc\n\n",
        "Group1\n------",
        "This is a description of group1.",
        ".. _Flow1:\n\nFlow1\n^^^^^\n\n**Description:** Description of Flow1\n\nSome ``extra`` **pizzaz**!\n**Flow Steps**\n\n.. code-block:: console\n",
        "",
    ]
    expected_call_args = [mock.call(s) for s in expected_call_args]
    assert echo.call_args_list == expected_call_args


def test_flow_run():
    org_config = mock.Mock(scratch=True, config={})
    runtime = CliRuntime(
        config={
            "flows": {"test": {"steps": {1: {"task": "test_task"}}}},
            "tasks": {
                "test_task": {
                    "class_path": "cumulusci.cli.tests.test_flow.DummyTask",
                    "description": "Test Task",
                }
            },
        },
        load_keychain=False,
    )
    runtime.get_org = mock.Mock(return_value=("test", org_config))
    runtime.get_flow = mock.Mock()

    run_click_command(
        flow.flow_run,
        runtime=runtime,
        flow_name="test",
        org="test",
        delete_org=True,
        debug=False,
        o=[("test_task__color", "blue")],
        no_prompt=True,
    )

    runtime.get_flow.assert_called_once_with(
        "test", options={"test_task": {"color": "blue"}}
    )
    org_config.delete_org.assert_called_once()


def test_flow_run__delete_org_when_error_occurs_in_flow():
    org_config = mock.Mock(scratch=True, config={})
    runtime = CliRuntime(
        config={
            "flows": {"test": {"steps": {1: {"task": "test_task"}}}},
            "tasks": {
                "test_task": {
                    "class_path": "cumulusci.cli.tests.test_flow.DummyTask",
                    "description": "Test Task",
                }
            },
        },
        load_keychain=False,
    )
    runtime.get_org = mock.Mock(return_value=("test", org_config))
    coordinator = mock.Mock()
    coordinator.run.side_effect = CumulusCIException
    runtime.get_flow = mock.Mock(return_value=coordinator)

    with pytest.raises(CumulusCIException):
        run_click_command(
            flow.flow_run,
            runtime=runtime,
            flow_name="test",
            org="test",
            delete_org=True,
            debug=False,
            o=[("test_task__color", "blue")],
            no_prompt=True,
        )

    runtime.get_flow.assert_called_once_with(
        "test", options={"test_task": {"color": "blue"}}
    )
    org_config.delete_org.assert_called_once()


def test_flow_run__option_error():
    org_config = mock.Mock(scratch=True, config={})
    runtime = CliRuntime(config={"noop": {}}, load_keychain=False)
    runtime.get_org = mock.Mock(return_value=("test", org_config))

    with pytest.raises(click.UsageError, match="-o"):
        run_click_command(
            flow.flow_run,
            runtime=runtime,
            flow_name="test",
            org="test",
            delete_org=True,
            debug=False,
            o=[("test_task", "blue")],
            no_prompt=True,
        )


def test_flow_run__delete_non_scratch():
    org_config = mock.Mock(scratch=False)
    runtime = mock.Mock()
    runtime.get_org.return_value = ("test", org_config)

    with pytest.raises(click.UsageError):
        run_click_command(
            flow.flow_run,
            runtime=runtime,
            flow_name="test",
            org="test",
            delete_org=True,
            debug=False,
            o=None,
            no_prompt=True,
        )


@mock.patch("click.echo")
def test_flow_run__org_delete_error(echo):
    org_config = mock.Mock(scratch=True, config={})
    org_config.delete_org.side_effect = Exception
    org_config.save_if_changed.return_value.__enter__ = lambda *args: ...
    org_config.save_if_changed.return_value.__exit__ = lambda *args: ...
    runtime = CliRuntime(
        config={
            "flows": {"test": {"steps": {1: {"task": "test_task"}}}},
            "tasks": {
                "test_task": {
                    "class_path": "cumulusci.cli.tests.test_flow.DummyTask",
                    "description": "Test Task",
                }
            },
        },
        load_keychain=False,
    )
    runtime.get_org = mock.Mock(return_value=("test", org_config))
    DummyTask._run_task = mock.Mock()

    kwargs = {
        "runtime": runtime,
        "flow_name": "test",
        "org": "test",
        "delete_org": True,
        "debug": False,
        "no_prompt": True,
        "o": (("test_task__color", "blue"),),
    }

    run_click_command(flow.flow_run, **kwargs)

    echo.assert_any_call(
        "Scratch org deletion failed.  Ignoring the error below to complete the flow:"
    )


# Tests for new FlowStepSpec and flow skipping functionality


class TestFlowStepSpec:
    """Test the FlowStepSpec class functionality."""

    def test_flowstep_spec_creation(self):
        """Test that FlowStepSpec can be created with proper inheritance."""
        project_config = create_project_config("TestOwner", "TestRepo")

        flow_step = FlowStepSpec(
            task_config={"test": "value"},
            step_num="1.0",
            task_name="test_flow",
            task_class=None,
            project_config=project_config,
            allow_failure=False,
            when="org_config.username == 'test@example.com'",
        )

        assert isinstance(flow_step, StepSpec)
        assert isinstance(flow_step, FlowStepSpec)
        assert flow_step.task_name == "test_flow"
        assert flow_step.when == "org_config.username == 'test@example.com'"
        assert flow_step.task_config == {"test": "value"}


class TestEvaluationMethods:
    """Test the evaluation methods for flow and task skipping."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_config = create_project_config("TestOwner", "TestRepo")
        self.org_config = OrgConfig(
            {"username": "test@example.com"}, "test", mock.Mock()
        )
        self.org_config.refresh_oauth_token = mock.Mock()

    def test_evaluate_flow_step_with_true_condition(self):
        """Test _evaluate_flow_step with a condition that evaluates to True."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        step = FlowStepSpec(
            task_config={},
            step_num="1.0",
            task_name="test_flow",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'test@example.com'",
        )

        result = coordinator._evaluate_flow_step(step)
        assert result is True

    def test_evaluate_flow_step_with_false_condition(self):
        """Test _evaluate_flow_step with a condition that evaluates to False."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        step = FlowStepSpec(
            task_config={},
            step_num="1.0",
            task_name="test_flow",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'wrong@example.com'",
        )

        result = coordinator._evaluate_flow_step(step)
        assert result is False

    def test_evaluate_flow_step_without_when_condition(self):
        """Test _evaluate_flow_step without a when condition."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        step = FlowStepSpec(
            task_config={},
            step_num="1.0",
            task_name="test_flow",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when=None,
        )

        result = coordinator._evaluate_flow_step(step)
        assert result is True

    def test_is_task_in_skipped_flow_true(self):
        """Test _is_task_in_skipped_flow returns True when task is in skipped flow."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        skipped_flows_set = {"skipped_flow", "another_flow"}
        task_path = "skipped_flow.sub_task"

        result = coordinator._is_task_in_skipped_flow(task_path, skipped_flows_set)
        assert result is True

    def test_is_task_in_skipped_flow_false(self):
        """Test _is_task_in_skipped_flow returns False when task is not in skipped flow."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        skipped_flows_set = {"skipped_flow", "another_flow"}
        task_path = "normal_flow.sub_task"

        result = coordinator._is_task_in_skipped_flow(task_path, skipped_flows_set)
        assert result is False

    def test_is_task_in_skipped_flow_empty_set(self):
        """Test _is_task_in_skipped_flow with empty skipped flows set."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        skipped_flows_set = set()
        task_path = "any_flow.sub_task"

        result = coordinator._is_task_in_skipped_flow(task_path, skipped_flows_set)
        assert result is False


class TestExpressionCaching:
    """Test Jinja2 expression caching functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_config = create_project_config("TestOwner", "TestRepo")
        self.org_config = OrgConfig(
            {"username": "test@example.com"}, "test", mock.Mock()
        )
        self.org_config.refresh_oauth_token = mock.Mock()

    def test_expression_caching_reuse(self):
        """Test that compiled expressions are cached and reused."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        # Clear any existing cache
        coordinator._expression_cache = {}

        step1 = FlowStepSpec(
            task_config={},
            step_num="1.0",
            task_name="test_flow1",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'test@example.com'",
        )

        step2 = FlowStepSpec(
            task_config={},
            step_num="2.0",
            task_name="test_flow2",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'test@example.com'",
        )

        # First evaluation should compile and cache the expression
        result1 = coordinator._evaluate_flow_step(step1)
        assert result1 is True
        assert len(coordinator._expression_cache) == 1

        # Second evaluation should use cached expression
        result2 = coordinator._evaluate_flow_step(step2)
        assert result2 is True
        assert (
            len(coordinator._expression_cache) == 1
        )  # Still only one cached expression

    def test_expression_caching_different_expressions(self):
        """Test that different expressions are cached separately."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        # Clear any existing cache
        coordinator._expression_cache = {}

        step1 = FlowStepSpec(
            task_config={},
            step_num="1.0",
            task_name="test_flow1",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'test@example.com'",
        )

        step2 = FlowStepSpec(
            task_config={},
            step_num="2.0",
            task_name="test_flow2",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'wrong@example.com'",
        )

        # Evaluate both steps
        coordinator._evaluate_flow_step(step1)
        coordinator._evaluate_flow_step(step2)

        # Should have two different cached expressions
        assert len(coordinator._expression_cache) == 2


class TestPerformanceImprovements:
    """Test that performance improvements work correctly."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_config = create_project_config("TestOwner", "TestRepo")
        self.org_config = OrgConfig(
            {"username": "test@example.com"}, "test", mock.Mock()
        )
        self.org_config.refresh_oauth_token = mock.Mock()

    def test_context_reuse(self):
        """Test that Jinja2 context is reused when possible."""
        flow_config = FlowConfig({"description": "Test Flow", "steps": {}})
        flow_config.project_config = self.project_config
        coordinator = FlowCoordinator(self.project_config, flow_config)
        coordinator.org_config = self.org_config

        # Clear any existing context
        coordinator._jinja2_context = None
        coordinator._context_project_config = None
        coordinator._context_org_config = None

        step = FlowStepSpec(
            task_config={},
            step_num="1.0",
            task_name="test_flow",
            task_class=None,
            project_config=self.project_config,
            allow_failure=False,
            when="org_config.username == 'test@example.com'",
        )

        # First evaluation should create context
        result1 = coordinator._evaluate_flow_step(step)
        assert result1 is True
        assert coordinator._jinja2_context is not None
        assert coordinator._context_project_config == self.project_config
        assert coordinator._context_org_config == self.org_config

        # Second evaluation should reuse context
        original_context = coordinator._jinja2_context
        result2 = coordinator._evaluate_flow_step(step)
        assert result2 is True
        assert coordinator._jinja2_context is original_context  # Same object reused
