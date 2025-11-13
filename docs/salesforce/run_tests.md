# RunApexTests Task

## Overview

The `run_tests` task executes Apex unit tests using the Salesforce Tooling API and provides comprehensive reporting of test results. This task supports advanced features including test retries for transient failures, dynamic test filtering, code coverage validation, and multiple output formats.

## Task Name

```
run_tests
```

## Basic Usage

```bash
cci task run run_tests
```

## Options

### Test Selection Options

#### `test_name_match`
- **Type**: `ListOfStringsOption` (comma-separated list)
- **Default**: `project__test__name_match` from project config
- **Description**: Pattern(s) to find Apex test classes to run. Use `%` as a wildcard. Supports multiple patterns separated by commas.
- **Example**:
  ```bash
  cci task run run_tests --test_name_match "%Test%,%_TEST%"
  ```

#### `test_name_exclude`
- **Type**: `ListOfStringsOption` (comma-separated list)
- **Default**: `project__test__name_exclude` from project config
- **Description**: Pattern(s) to exclude Apex test classes. Use `%` as a wildcard. Supports multiple patterns separated by commas.
- **Example**:
  ```bash
  cci task run run_tests --test_name_exclude "%LegacyTest%"
  ```

#### `test_suite_names`
- **Type**: `ListOfStringsOption` (comma-separated list)
- **Default**: `project__test__suite__names` from project config
- **Description**: List of test suite names. Only runs test classes that are part of the specified test suites. Cannot be used simultaneously with `test_name_match` (unless `test_name_match` contains `%_TEST%` or `%TEST%`).
- **Example**:
  ```bash
  cci task run run_tests --test_suite_names "SmokeTests,RegressionTests"
  ```

#### `dynamic_filter`
- **Type**: `Optional[str]`
- **Default**: `None`
- **Description**: Defines a dynamic filter to apply to test classes from the org that match `test_name_match`. Supported values:
  - `None` (default): No dynamic filter applied. All test classes from the org that match `test_name_match` are run.
  - `package_only`: Only runs test classes that exist in the default package directory (`force-app/` or `src/`).
  - `delta_changes`: Only runs test classes that are affected by delta changes in the current branch.
- **Example**:
  ```bash
  cci task run run_tests --dynamic_filter package_only
  ```

#### `base_ref`
- **Type**: `Optional[str]`
- **Default**: `None` (uses default branch of repository)
- **Description**: Git reference (branch, tag, or commit) to compare against for delta changes. Only used when `dynamic_filter` is set to `delta_changes`. If not set, uses the default branch of the repository.
- **Example**:
  ```bash
  cci task run run_tests --dynamic_filter delta_changes --base_ref main
  ```

### Namespace Options

#### `namespace`
- **Type**: `Optional[str]`
- **Default**: `project__package__namespace` from project config
- **Description**: Salesforce project namespace. Used to filter test classes by namespace.
- **Example**:
  ```bash
  cci task run run_tests --namespace th_dev
  ```

#### `managed`
- **Type**: `bool`
- **Default**: `False`
- **Description**: If `True`, searches for tests in the namespace only. Defaults to `False`.
- **Example**:
  ```bash
  cci task run run_tests --managed True
  ```

### Retry Options

#### `retry_failures`
- **Type**: `ListOfRegexPatternsOption` (list of regular expressions)
- **Default**: `[]`
- **Description**: A list of regular expression patterns to match against test failures. If failures match, the failing tests are retried in serial mode. Useful for handling transient errors like row locks.
- **Example**:
  ```bash
  cci task run run_tests --retry_failures "unable to obtain exclusive access" "UNABLE_TO_LOCK_ROW"
  ```

#### `retry_always`
- **Type**: `bool`
- **Default**: `False`
- **Description**: By default, all failures must match `retry_failures` patterns to perform a retry. Set `retry_always` to `True` to retry all failed tests if any failure matches the retry patterns. This is helpful when underlying row locking errors are masked by custom exceptions.
- **Example**:
  ```bash
  cci task run run_tests --retry_failures "UNABLE_TO_LOCK_ROW" --retry_always True
  ```

### Code Coverage Options

#### `required_org_code_coverage_percent`
- **Type**: `PercentageOption` (integer or percentage string)
- **Default**: `0`
- **Description**: Require at least X percent code coverage across the org following the test run. Can be specified as an integer (e.g., `75`) or percentage string (e.g., `75%`).
- **Example**:
  ```bash
  cci task run run_tests --required_org_code_coverage_percent 75
  ```

#### `required_per_class_code_coverage_percent`
- **Type**: `PercentageOption` (integer or percentage string)
- **Default**: `0`
- **Description**: Require at least X percent code coverage for every class in the org. Can be specified as an integer (e.g., `75`) or percentage string (e.g., `75%`).
- **Example**:
  ```bash
  cci task run run_tests --required_per_class_code_coverage_percent 80
  ```

#### `required_individual_class_code_coverage_percent`
- **Type**: `MappingIntOption` (mapping of class names to percentages)
- **Default**: `{}`
- **Description**: Mapping of class names to their minimum coverage percentage requirements. Takes priority over `required_per_class_code_coverage_percent` for specified classes. Format: `ClassName1:90%,ClassName2:85` or `ClassName1:90,ClassName2:85`.
- **Example**:
  ```bash
  cci task run run_tests --required_individual_class_code_coverage_percent "AccountHandler:90%,ContactService:85"
  ```

### Output Options

#### `junit_output`
- **Type**: `Optional[str]`
- **Default**: `test_results.xml`
- **Description**: File name for JUnit XML output. Set to empty string to disable JUnit output.
- **Example**:
  ```bash
  cci task run run_tests --junit_output custom_results.xml
  ```

#### `json_output`
- **Type**: `Optional[str]`
- **Default**: `test_results.json`
- **Description**: File name for JSON output. Set to empty string to disable JSON output.
- **Example**:
  ```bash
  cci task run run_tests --json_output custom_results.json
  ```

#### `verbose`
- **Type**: `bool`
- **Default**: `False`
- **Description**: By default, only failures get detailed output. Set `verbose` to `True` to see all passed test methods.
- **Example**:
  ```bash
  cci task run run_tests --verbose True
  ```

### Polling Options

#### `poll_interval`
- **Type**: `int`
- **Default**: `1`
- **Description**: Seconds to wait between polling for Apex test results.
- **Example**:
  ```bash
  cci task run run_tests --poll_interval 2
  ```

## Dynamic Filter Behavior

### `package_only` Filter

When `dynamic_filter` is set to `package_only`, the task:

1. **Scans the default package directory** (`force-app/` or `src/`) for Apex class files (`.cls` files)
2. **Filters test classes** to only include those that exist as files in the package directory
3. **Excludes test classes** that exist in the org but are not present in the local package directory

**Use Case**: Useful when you want to run tests only for classes that are part of your current package, excluding tests from installed managed packages or other sources.

**Example**:
```bash
cci task run run_tests --dynamic_filter package_only --test_name_match "%Test%"
```

**Behavior**:
- If `AccountTest` exists in `force-app/main/default/classes/AccountTest.cls`, it will be included
- If `ManagedPackageTest` exists in the org but not in your package directory, it will be excluded
- The task logs how many test classes were excluded

### `delta_changes` Filter

When `dynamic_filter` is set to `delta_changes`, the task:

1. **Identifies changed files** by comparing the current branch against a base reference:
   - Gets committed changes compared to `base_ref` (or default branch if not specified)
   - Gets uncommitted changes in the working directory
   - Monitors changes in `force-app/` and `src/` directories
   - Tracks changes to `.cls`, `.flow-meta.xml`, and `.trigger` files

2. **Extracts affected class names** from the changed files

3. **Determines which test classes to run** based on:
   - **Direct match**: Test class name matches a changed class name
   - **Naming patterns**: Test classes that follow common naming conventions:
     - `Account.cls` changed → `AccountTest.cls` runs
     - `MyService.cls` changed → `MyServiceTest.cls` runs
     - `AccountHandler.cls` changed → `AccountHandlerTest.cls` runs
     - Patterns supported:
       - `{ClassName}Test`
       - `Test{ClassName}`
       - `{ClassName}_*`
       - `Test{ClassName}_*`

4. **Runs only affected test classes**

**Use Case**: Ideal for CI/CD pipelines where you want to run only tests affected by changes in a pull request or feature branch, significantly reducing test execution time.

**Example**:
```bash
cci task run run_tests --dynamic_filter delta_changes --base_ref main
```

**Behavior**:
- Compares current branch against `main` branch
- Identifies all changed Apex classes, triggers, and flows
- Runs tests for:
  - Direct matches (if `Account.cls` changed and `AccountTest.cls` exists)
  - Pattern matches (if `AccountHandler.cls` changed, runs `AccountHandlerTest.cls`)
- If no git repository is found, falls back to running all test classes
- If no changed files are found, returns empty result (no tests run)

**Important Notes**:
- Requires a git repository to be present
- Works with both committed and uncommitted changes
- Case-insensitive matching for class names
- If `base_ref` is not specified, uses the repository's default branch

## Code Coverage Validation

The task supports three levels of code coverage validation:

1. **Organization-wide coverage**: Validates that the overall code coverage meets a minimum threshold
2. **Per-class coverage**: Validates that every class meets a minimum coverage threshold
3. **Individual class coverage**: Validates specific classes against custom thresholds (takes priority over per-class requirements)

**Example with multiple coverage requirements**:
```bash
cci task run run_tests \
  --required_org_code_coverage_percent 75 \
  --required_per_class_code_coverage_percent 80 \
  --required_individual_class_code_coverage_percent "CriticalService:95%,AccountHandler:90%"
```

**Note**: Code coverage checks are skipped if the namespace is installed as a managed package in the org.

## Test Retry Mechanism

The task supports automatic retry of failed tests that match specific error patterns. This is particularly useful for handling transient errors like row locks in parallel test execution.

### Retry Behavior

**Default behavior** (`retry_always: False`):
- All failures must match at least one pattern in `retry_failures`
- Only matching failures are retried individually in serial mode

**With `retry_always: True`**:
- If any failure matches a retry pattern, all failed tests are retried
- Useful when custom exceptions mask underlying row locking errors

### Recommended Configuration

```yaml
retry_failures:
  - "unable to obtain exclusive access to this record"
  - "UNABLE_TO_LOCK_ROW"
  - "connection was cancelled here"
retry_always: True
```

**Example**:
```bash
cci task run run_tests \
  --retry_failures "UNABLE_TO_LOCK_ROW" "unable to obtain exclusive access" \
  --retry_always True
```

## Output Formats

### JUnit XML Output

The task generates a JUnit-compatible XML file (default: `test_results.xml`) that can be consumed by CI/CD systems and test reporting tools.

**Format**:
```xml
<testsuite tests="10">
  <testcase classname="AccountTest" name="testAccountCreation" time="150">
    <failure type="failed" message="Assertion failed">
      <![CDATA[Stack trace here]]>
    </failure>
  </testcase>
  ...
</testsuite>
```

### JSON Output

The task generates a detailed JSON file (default: `test_results.json`) with comprehensive test result information including:
- Class name and method name
- Outcome (Pass, Fail, CompileFail, Skip)
- Error messages and stack traces
- Test execution statistics (SOQL queries, DML statements, CPU time, etc.)
- Test timestamps

**Example JSON structure**:
```json
[
  {
    "ClassName": "AccountTest",
    "Method": "testAccountCreation",
    "Outcome": "Pass",
    "Message": "",
    "StackTrace": "",
    "Stats": {
      "duration": 150,
      "TESTING_LIMITS: Number of SOQL queries": {
        "used": 5,
        "allowed": 100
      }
    }
  }
]
```

## Usage Examples

### Basic Test Run
```bash
cci task run run_tests
```

### Run Tests Matching Pattern
```bash
cci task run run_tests --test_name_match "%Test%"
```

### Run Tests with Exclusions
```bash
cci task run run_tests \
  --test_name_match "%Test%" \
  --test_name_exclude "%LegacyTest%,%OldTest%"
```

### Run Tests from Test Suites
```bash
cci task run run_tests --test_suite_names "SmokeTests,RegressionTests"
```

### Run Only Package Tests
```bash
cci task run run_tests --dynamic_filter package_only
```

### Run Tests for Delta Changes
```bash
cci task run run_tests --dynamic_filter delta_changes --base_ref main
```

### Run Tests with Code Coverage Requirements
```bash
cci task run run_tests \
  --required_org_code_coverage_percent 75 \
  --required_per_class_code_coverage_percent 80
```

### Run Tests with Retry Configuration
```bash
cci task run run_tests \
  --retry_failures "UNABLE_TO_LOCK_ROW" \
  --retry_always True
```

### Verbose Output
```bash
cci task run run_tests --verbose True
```

### Custom Output Files
```bash
cci task run run_tests \
  --junit_output custom_junit.xml \
  --json_output custom_json.json
```

### Complete Example
```bash
cci task run run_tests \
  --test_name_match "%Test%" \
  --test_name_exclude "%LegacyTest%" \
  --dynamic_filter delta_changes \
  --base_ref main \
  --required_org_code_coverage_percent 75 \
  --required_per_class_code_coverage_percent 80 \
  --retry_failures "UNABLE_TO_LOCK_ROW" \
  --retry_always True \
  --verbose True
```

## Error Handling

The task raises an `ApexTestException` if:
- Any tests fail (Fail or CompileFail outcomes)
- Code coverage requirements are not met

The task will continue to completion and generate output files even if tests fail, but will exit with an error status.

## Limitations

1. **Managed Package Classes**: When running in managed mode (`managed: True`), symbol tables for managed classes cannot be accessed in Spring '20 and later. Class-level failures for managed classes cannot be retried.

2. **Git Repository**: The `delta_changes` filter requires a git repository. If no repository is found, it falls back to running all test classes.

3. **Test Suite vs Test Name Match**: Cannot use `test_suite_names` and `test_name_match` simultaneously unless `test_name_match` contains `%_TEST%` or `%TEST%`.

4. **Code Coverage**: Code coverage validation is skipped if the namespace is installed as a managed package in the org.

## Best Practices

1. **Use `delta_changes` in CI/CD**: Significantly reduces test execution time by running only affected tests
2. **Configure retry patterns**: Add common transient error patterns to `retry_failures` for more reliable test runs
3. **Set code coverage thresholds**: Enforce minimum coverage requirements to maintain code quality
4. **Use test suites**: Organize tests into suites for different testing scenarios (smoke, regression, etc.)
5. **Monitor test statistics**: Review the JSON output to identify tests that are approaching governor limits

