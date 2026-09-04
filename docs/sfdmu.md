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

## Execute Directory Behavior

The task creates an `execute` directory under your dataset path and runs SFDMU with `-p <dataset>/execute`.

It copies:

- Root-level `.json` and `.csv` files from the dataset directory
- The `objectset_source` directory tree (only `.json` and `.csv` files)

It does not copy unrelated directories such as `target` or other custom folders.

## Multiple Object Sets (`objectset_source`)

When your `export.json` uses multiple object sets and separate CSV files per object set, set:

```json
"useSeparatedCSVFiles": true
```

With this setting:

- Object set 1 CSV files are read from the dataset root
- Object set N (N >= 2) CSV files are read from `objectset_source/object-set-N`

Example layout:

```text
datasets/testData/
  export.json
  Account.csv
  objectset_source/
    object-set-2/
      Account.csv
      Identifier.csv
    object-set-3/
      HealthcareProvider.csv
```

If `useSeparatedCSVFiles` is not set (or is `false`), SFDMU reuses root CSVs for all object sets and does not read `objectset_source/object-set-N` CSVs.

## Export Copy-Back Behavior (`target=csvfile`)

For org-to-CSV exports (`--target csvfile`), after SFDMU finishes:

- Namespace token post-processing is applied to CSV content and CSV filenames
- Processed CSV files are copied back from `execute` to the dataset path
- Relative paths are preserved:
  - `execute/Account.csv` -> `<dataset>/Account.csv`
  - `execute/objectset_source/object-set-2/Account.csv` -> `<dataset>/objectset_source/object-set-2/Account.csv`

Before copy-back, existing CSVs are removed only from:

- Dataset root (`<dataset>/*.csv`)
- `objectset_source` subfolders (`<dataset>/objectset_source/**/*.csv`)

The `execute` directory is never used as a copy-back target and remains a working directory.

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
