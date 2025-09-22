# SF Package Commands

This document describes the SF Package Commands classes that provide a generic interface for Salesforce package operations in CumulusCI.

## Overview

The `SfPackageCommands` module provides a comprehensive set of classes for interacting with Salesforce package commands through the SFDX CLI. These classes follow the same pattern as the existing `SfDataCommands` and can be used as CumulusCI tasks.

## Base Classes

### SfPackageCommands

The base class for all package command operations. It provides common functionality for:

-   JSON output handling
-   API version specification
-   Flags directory support
-   Standard logging and error handling

**Options:**

-   `json_output` (bool): Whether to return the result as a JSON object
-   `api_version` (str): API version to use for the command
-   `flags_dir` (str): Import flag values from a directory

## Package Version Commands

### PackageVersionUpdateTask

Updates an existing package version with new attributes.

**Required Options:**

-   `package_id` (str): Package ID or alias to update

**Optional Options:**

-   `version_name` (str): New package version name
-   `version_description` (str): New package version description
-   `branch` (str): New package version branch
-   `tag` (str): New package version tag
-   `installation_key` (str): New installation key for key-protected package

**Example Usage:**

```yaml
tasks:
    update_package_version:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageVersionUpdateTask
        options:
            package_id: "0Ho000000000001"
            version_name: "Updated Version"
            version_description: "Updated description"
            branch: "main"
            tag: "v1.1.0"
            json_output: true
```

### PackageVersionCreateTask

Creates a new package version.

**Required Options:**

-   `package_id` (str): Package ID or alias to create version for

**Optional Options:**

-   `version_name` (str): Package version name
-   `version_description` (str): Package version description
-   `branch` (str): Package version branch
-   `tag` (str): Package version tag
-   `installation_key` (str): Installation key for key-protected package
-   `wait` (int): Number of minutes to wait for the command to complete
-   `code_coverage` (bool): Calculate code coverage for the package version
-   `skip_validation` (bool): Skip validation of the package version

**Example Usage:**

```yaml
tasks:
    create_package_version:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageVersionCreateTask
        options:
            package_id: "0Ho000000000001"
            version_name: "New Version"
            version_description: "New description"
            branch: "main"
            tag: "v1.0.0"
            wait: 10
            code_coverage: true
            json_output: true
```

### PackageVersionListTask

Lists package versions.

**Optional Options:**

-   `package_id` (str): Package ID or alias to list versions for
-   `status` (str): Filter by package version status (Success, Error, InProgress, Queued)
-   `modified` (bool): Show only modified package versions
-   `concise` (bool): Show only the package version ID, version number, and status

**Example Usage:**

```yaml
tasks:
    list_package_versions:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageVersionListTask
        options:
            package_id: "0Ho000000000001"
            status: "Success"
            concise: true
            json_output: true
```

### PackageVersionDisplayTask

Displays details of a specific package version.

**Required Options:**

-   `package_version_id` (str): Package version ID to display

**Optional Options:**

-   `verbose` (bool): Show verbose output

**Example Usage:**

```yaml
tasks:
    display_package_version:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageVersionDisplayTask
        options:
            package_version_id: "04t000000000001"
            verbose: true
            json_output: true
```

### PackageVersionDeleteTask

Deletes a package version.

**Required Options:**

-   `package_version_id` (str): Package version ID to delete

**Optional Options:**

-   `no_prompt_flag` (bool): Don't prompt for confirmation

**Example Usage:**

```yaml
tasks:
    delete_package_version:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageVersionDeleteTask
        options:
            package_version_id: "04t000000000001"
            no_prompt_flag: true
            json_output: true
```

### PackageVersionReportTask

Generates reports for a package version.

**Required Options:**

-   `package_version_id` (str): Package version ID to generate report for

**Optional Options:**

-   `code_coverage` (bool): Generate code coverage report
-   `output_dir` (str): Directory to save the report

**Example Usage:**

```yaml
tasks:
    generate_package_report:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageVersionReportTask
        options:
            package_version_id: "04t000000000001"
            code_coverage: true
            output_dir: "/tmp/reports"
            json_output: true
```

## Package Commands

### PackageCreateTask

Creates a new package.

**Required Options:**

-   `name` (str): Package name

**Optional Options:**

-   `description` (str): Package description
-   `package_type` (str): Package type (Managed, Unlocked)
-   `path` (str): Path to the package directory

**Example Usage:**

```yaml
tasks:
    create_package:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageCreateTask
        options:
            name: "Test Package"
            description: "Test package description"
            package_type: "Managed"
            path: "/tmp/package"
            json_output: true
```

### PackageListTask

Lists packages.

**Optional Options:**

-   `concise` (bool): Show only the package ID, name, and type

**Example Usage:**

```yaml
tasks:
    list_packages:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageListTask
        options:
            concise: true
            json_output: true
```

### PackageDisplayTask

Displays details of a specific package.

**Required Options:**

-   `package_id` (str): Package ID or alias to display

**Optional Options:**

-   `verbose` (bool): Show verbose output

**Example Usage:**

```yaml
tasks:
    display_package:
        class_path: cumulusci.tasks.salesforce.SfPackageCommands.PackageDisplayTask
        options:
            package_id: "0Ho000000000001"
            verbose: true
            json_output: true
```

## Error Handling

All classes inherit error handling from the base `SfPackageCommands` class:

-   **SalesforceDXException**: Raised when JSON parsing fails
-   **Command execution errors**: Logged as errors and re-raised by the sfdx function
-   **Missing required options**: Validated by the CCIOptions framework

## JSON Output

When `json_output` is set to `true`, the command output is parsed as JSON and made available in the `return_values` attribute. This is useful for:

-   Extracting specific information from command results
-   Passing data between tasks in a flow
-   Programmatic processing of command output

## Integration with CumulusCI Flows

These tasks can be integrated into CumulusCI flows:

```yaml
flows:
    package_management:
        steps:
            1:
                task: create_package
                options:
                    name: "My Package"
                    package_type: "Managed"
            2:
                task: create_package_version
                options:
                    package_id: "{{ task.1.return_values.result.packageId }}"
                    version_name: "v1.0.0"
                    branch: "main"
            3:
                task: update_package_version
                options:
                    package_id: "{{ task.1.return_values.result.packageId }}"
                    version_name: "v1.0.1"
                    version_description: "Updated version"
```

## Testing

Comprehensive tests are provided in `test_SfPackageCommands.py` that cover:

-   Basic functionality of all classes
-   Option parsing and argument construction
-   JSON output handling
-   Error conditions
-   Required field validation

Run tests with:

```bash
pytest cumulusci/tasks/salesforce/tests/test_SfPackageCommands.py
```

## Best Practices

1. **Always use JSON output** when you need to extract data from command results
2. **Set appropriate wait times** for long-running operations like package version creation
3. **Use concise output** for listing operations when you only need basic information
4. **Handle errors gracefully** by checking return values and implementing appropriate error handling
5. **Use meaningful version names and descriptions** for better package management
6. **Set up proper Dev Hub configuration** for package operations

## Related Documentation

-   [Salesforce CLI Package Commands Reference](https://developer.salesforce.com/docs/atlas.en-us.sfdx_cli_reference.meta/sfdx_cli_reference/cli_reference_package_commands_unified.htm)
-   [CumulusCI Task Development Guide](https://cumulusci.readthedocs.io/en/latest/tasks.html)
-   [SfDataCommands Documentation](https://github.com/SFDO-Tooling/CumulusCI/blob/main/cumulusci/tasks/salesforce/SfDataCommands.py)
