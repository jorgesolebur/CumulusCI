# CumulusCI Plus Release Process

This document outlines the process for creating a new release of CumulusCI Plus. The release process is mostly automated using GitHub Actions.

## Release Process Overview

The release process is triggered when a pull request is merged into the `main` branch. A GitHub Actions workflow automates version bumping, changelog generation, and publishing to PyPI.

There are three main GitHub Actions workflows involved in the release process:

1.  **`pr-labeler.yml`**: This workflow runs on every new pull request to add a `semver:dev` label if no other `semver:*` label is present. This ensures that every PR has a version bump indicator.
2.  **`pre-release.yml`**: This workflow is triggered when a pull request is merged into `main`. It determines the version bump based on the PR's labels, creates a new release branch, generates a changelog, and creates a pull request for the release. Once that PR is merged, it triggers the `release.yml` workflow.
3.  **`release.yml`**: This workflow is triggered by the `pre-release.yml` workflow (or manually). It builds the project, publishes the new version to PyPI, and creates a GitHub release.

## Versioning

The version number is determined by the labels on the pull request. The following labels are used to determine the version bump:

-   `semver:major`: Bumps the major version (e.g., `3.0.0` -> `4.0.0`).
-   `semver:minor`: Bumps the minor version (e.g., `3.1.0` -> `3.2.0`).
-   `semver:patch`: Bumps the patch version (e.g., `3.1.1` -> `3.1.2`).
-   `semver:beta`: Creates a beta release (e.g., `3.1.2` -> `3.1.3b1`).
-   `semver:alpha`: Creates an alpha release (e.g., `3.1.2` -> `3.1.3a1`).
-   `semver:preview`: Creates a preview release (e.g., `3.1.2` -> `3.1.3rc1`).
-   `semver:dev`: Bumps the dev version (e.g., `3.1.2` -> `3.1.3.dev1`).

If a pull request does not have a `semver:*` label, the `pr-labeler.yml` workflow will automatically add the `semver:dev` label.

## The `pre-release.yml` Workflow

This workflow is defined in `.github/workflows/pre-release.yml` and is triggered when a pull request is closed and merged into the `main` branch.

The workflow performs the following steps:

1.  **Checkout Code**: Checks out the repository.
2.  **Set up Python**: Sets up a Python environment.
3.  **Install build tool**: Installs `hatch`.
4.  **Determine Version Bump**: Determines the version bump based on the labels of the merged pull request.
5.  **Bump version**: Bumps the version in `cumulusci/__about__.py` using `hatch`.
6.  **Generate release notes**: Generates release notes using `gh release generate-notes` and updates `docs/history.md`.
7.  **Lint history**: Lints the `docs/history.md` file.
8.  **Commit version and changelog**: Commits the updated version and changelog to a new branch named `release-<new_version>`.
9.  **Create and Merge Release PR**: Creates a new pull request with the release changes and merges it.
10. **Call Release Workflow**: Triggers the `release.yml` workflow.

## The `release.yml` Workflow

This workflow is defined in `.github/workflows/release.yml`. It can be triggered manually or by the `pre-release.yml` workflow.

The workflow performs the following steps:

1.  **Checkout Code**: Checks out the repository.
2.  **Set up Python**: Sets up a Python environment.
3.  **Install build tools**: Installs `hatch` and other build dependencies.
4.  **Check version type**: Checks if the current version is a publishable release (not a dev, alpha, or beta release).
5.  **Build source tarball and binary wheel**: Builds the project using `hatch`.
6.  **Upload to PyPI**: Publishes the new version to PyPI.
7.  **Create release**: Creates a new GitHub release with the changelog and artifacts.

## The `pr-labeler.yml` Workflow

This workflow is defined in `.github/workflows/pr-labeler.yml`. It is triggered when a new pull request is opened.

The workflow performs the following steps:

1.  **Checkout Code**: Checks out the repository.
2.  **Add semver:dev label**: If no other `semver:*` label exists on the PR, it adds the `semver:dev` label.

## Manual Release Trigger

While the process is mostly automated, a release can be triggered manually by pushing a change to `cumulusci/__about__.py` on the `main` branch, or by manually running the "Publish and release CumulusCI" workflow from the Actions tab in GitHub.
