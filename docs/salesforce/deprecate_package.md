# DeletePackage Task

## Overview

The `delete_package` task deletes a Salesforce Package2 (2GP package) and its associated Package2Version records. Before deleting, the task performs validation checks to ensure the operation is safe and allowed.

## Task Name

```
delete_package
```

## Basic Usage

```bash
# Uses default devhub if no org is specified
cci task run delete_package --package MyPackage

# Or specify an org explicitly
cci task run delete_package --org devhub --package MyPackage
```

## Options

### `package`
- **Type**: `str` (required)
- **Description**: The Package2 Id (starting with `0Ho...`) or Name to delete
- **Examples**:
  ```bash
  # Delete by Package2 Id
  cci task run delete_package --package 0Ho000000000000AAA

  # Delete by package name
  cci task run delete_package --package MyPackage
  ```

### `no_prompt`
- **Type**: `bool`
- **Default**: `False`
- **Description**: Standard CumulusCI option available to all tasks. If `True`, the task will not prompt for confirmation before deleting. Useful for automated scripts and CI/CD pipelines.
- **Example**:
  ```bash
  cci task run delete_package --package MyPackage --no_prompt True
  ```

## Behavior

### Default Dev Hub Usage

If no org is specified with the `--org` option, the task will automatically use the default devhub service configured in your CumulusCI project. This makes it convenient to delete packages without explicitly specifying the devhub org each time.

### Validation Checks

The task performs the following validation checks before deleting:

1. **Dev Hub Validation**: Verifies that the org is a Dev Hub with 2nd-generation packaging enabled (validated when querying Package2)
2. **Package Lookup**: Finds the package by Id or Name in the dev hub org
3. **Version Check**: Identifies all non-deprecated Package2Version records
4. **Deletion Rules**: Validates that the package and versions can be deleted

### Deletion Rules

The task follows these rules when deleting:

- **All non-deprecated Package2Version records** will be deleted first
- **Cannot delete 2GP Managed packages that are released** (IsReleased = True)
- **Unlocked packages** can always be deleted
- **Managed packages** can be deleted only if none of their versions are released

### Execution Flow

1. **Find Package**: Queries for the package by Id or Name in the dev hub org (uses default devhub if no org specified)
2. **Get Versions**: Retrieves all non-deprecated Package2Version records
3. **Validate Versions**: Ensures no released Managed package versions exist
4. **User Confirmation**: Prompts for confirmation (unless `no_prompt=True`)
5. **Delete Versions**: Updates all Package2Version records with `IsDeprecated = True`
6. **Delete Package**: Updates the Package2 record with `IsDeprecated = True`

### Error Handling

The task will fail with an error if:

- The org is not a Dev Hub
- The package is not found
- Multiple packages exist with the same name (must use Package2 Id instead)
- A released Managed package version exists
- Deletion of Package2Version records fails (prevents package deletion)
- Deletion of Package2 fails

## Usage Examples

### Delete Package by Id

```bash
cci task run delete_package --package 0Ho000000000000AAA
```

### Delete Package by Name

```bash
cci task run delete_package --package MyTestPackage
```

### Delete Without Confirmation Prompt

```bash
cci task run delete_package --package MyPackage --no_prompt True
```

### Delete Package with Multiple Versions

When a package has multiple versions, the task will:
1. List all versions that will be deleted
2. Prompt for confirmation showing version details
3. Delete all versions before deleting the package

```bash
cci task run delete_package --package MyPackage
```

**Example output**:
```
Found package: MyPackage (Id: 0Ho000000000000AAA, Type: Unlocked)
Found 3 non-deleted version(s)
This will delete package 'MyPackage' and 3 version(s):
  - 05i000000000001AAA (v1.0.0)
  - 05i000000000002AAA (v1.1.0)
  - 05i000000000003AAA (v1.2.0)
Continue? [y/N]:
```

### Using Default Dev Hub

The task automatically uses the default devhub service if no org is specified:

```bash
# Uses default devhub automatically
cci task run delete_package --package MyPackage

# Equivalent to explicitly specifying devhub
cci task run delete_package --org devhub --package MyPackage
```

## Limitations

1. **Released Managed Packages**: Cannot delete 2GP Managed packages that have released versions. You must first deprecate or delete the released versions before deleting the package.

2. **Multiple Packages with Same Name**: If multiple packages exist with the same name, you must use the Package2 Id instead of the name.

3. **Dev Hub Required**: The task requires a Dev Hub org with 2nd-generation packaging enabled.

4. **Version Deletion Failure**: If any Package2Version deletion fails, the entire task fails and the Package2 will not be deleted.

## Error Messages

### Package Not Found
```
Package 'MyPackage' not found
```

**Solution**: Verify the package name or Id is correct and exists in the Dev Hub org.

### Multiple Packages Found
```
Multiple packages found with name 'MyPackage'. Please use Package2 Id instead.
```

**Solution**: Use the Package2 Id (starting with `0Ho...`) instead of the name.

### Dev Hub Not Enabled
```
This org does not have a Dev Hub with 2nd-generation packaging enabled.
Make sure you are using the correct org and/or check the Dev Hub settings in Setup.
```

**Solution**: Ensure you're using a Dev Hub org and that 2nd-generation packaging is enabled in Setup.

### Cannot Delete Released Managed Package
```
Cannot delete released Managed package version: 04t000000000000AAA
```

**Solution**: You cannot delete released Managed package versions. Consider deprecating the package versions first, or if they're already released, you may need to contact Salesforce support.

### Version Deletion Failed
```
Failed to delete 1 Package2Version record(s):
  - 04t000000000000AAA: Update failed
```

**Solution**: Check the error message for details. The Package2 will not be deleted if version deletion fails.

## Best Practices

1. **Use Package2 Id in Scripts**: When automating, use Package2 Id instead of name to avoid ambiguity
2. **Review Versions First**: Check what versions exist before deleting to understand the impact
3. **Use `no_prompt` in CI/CD**: Set `no_prompt=True` in automated pipelines to avoid hanging on prompts (this is a standard CumulusCI option available to all tasks)
4. **Validate Before Deleting**: Ensure no released Managed package versions exist before running the task
5. **Backup Important Packages**: Consider backing up package metadata before deleting important packages
6. **Use Default Dev Hub**: Take advantage of the automatic devhub detection to simplify command-line usage

## Related Tasks

- `create_package_version`: Create new package versions
- `promote_package_version`: Promote package versions to released status
- `getPackageVersion`: Retrieve package version information

## Technical Details

### Tooling API Usage

The task uses the Salesforce Tooling API to:
- Query Package2 records
- Query Package2Version records
- Update Package2 records with `IsDeprecated = True`
- Update Package2Version records with `IsDeprecated = True`

### Package2 Fields Used

- `Id`: Package2 record identifier
- `Name`: Package name
- `ContainerOptions`: Package type (Managed/Unlocked)
- `IsDeprecated`: Deprecation status

### Package2Version Fields Used

- `Id`: Package2Version record identifier
- `Package2Id`: Reference to parent Package2
- `SubscriberPackageVersionId`: Subscriber Package Version Id (04t...)
- `MajorVersion`, `MinorVersion`, `PatchVersion`: Version numbers
- `IsReleased`: Release status
- `IsDeprecated`: Deprecation status

### Dev Hub Configuration

The task automatically uses the default devhub service when no org is specified. The devhub is determined by:
1. Checking for a configured `devhub` service in the project
2. Falling back to the default devhub username from Salesforce CLI (`sf config get target-dev-hub`)

This allows the task to work seamlessly without requiring explicit org specification for most use cases.
