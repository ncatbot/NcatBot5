Auto release notes generator

Usage

- The workflow triggers on tag pushes matching `v*` (e.g. `v1.0.0`).
- The generator builds a changelog from commits since the previous tag and preserves a user-editable block between:

  <!-- BEGIN USER CUSTOM DESCRIPTION -->
  ...your custom text...
  <!-- END USER CUSTOM DESCRIPTION -->

- To test locally:
  TAG_NAME=v1.0.0 GITHUB_REPOSITORY=owner/repo python scripts/generate_release_notes.py --dry-run

Notes

- The script uses `GITHUB_TOKEN` to create/update releases when `--apply` is passed or when run in GitHub Actions.
