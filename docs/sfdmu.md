# SFDmu Task

This task provides integration between CumulusCI and SFDmu (Salesforce Data Migration Utility) with namespace injection support.

## Usage

```bash
cci task run sfdmu --source dev --target qa --path /path/to/sfdmu/folder
```

## Options

- `source`: Source org name (CCI org name like dev, beta, qa, etc.) or 'csvfile'
- `target`: Target org name (CCI org name like dev, beta, qa, etc.) or 'csvfile'  
- `path`: Path to folder containing export.json and other CSV files

## Features

- **Org Validation**: Validates that source and target CCI orgs exist
- **Namespace Injection**: Automatically injects namespace tokens into JSON and CSV files
- **File Processing**: Copies files to an execute directory and processes namespace tokens
- **Real-time Output**: Streams SFDmu command output in real-time
- **Error Handling**: Returns appropriate errors if SFDmu command fails

## Requirements

- SFDmu must be installed and available in PATH
- Source folder must contain `export.json`
- Valid CCI org configurations for source and target (unless using 'csvfile')

## Namespace Token Support

The task supports the following namespace tokens:
- `%%%NAMESPACE%%%` - Replaced with namespace prefix
- `%%%NAMESPACED_ORG%%%` - Replaced with namespaced org prefix
- `___NAMESPACE___` - Replaced in filenames
- `___NAMESPACED_ORG___` - Replaced in filenames

## Example

```bash
# Migrate data from dev org to qa org
cci task run sfdmu --source dev --target qa --path datasets/migration

# Migrate data from CSV files to dev org
cci task run sfdmu --source csvfile --target dev --path datasets/csv_data
```
