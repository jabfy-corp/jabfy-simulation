# Contributing

## Before You Start

Every contribution must be tied to an existing issue. If no issue exists for your change, open one first.

## Branch Naming

```
sim-<issue-number>-<short-description>
```

Example: `sim-1-motion-sensor-device`

## Commit Naming

```
<type>: <description>
```

| Type | Use for |
|---|---|
| `feat` | New feature or device type |
| `fix` | Bug fix |
| `chore` | Maintenance / tooling / CI |
| `docs` | Documentation only |
| `refractor` | Refactoring (no functional change) |
| `test` | Tests only |

## Pull Requests

Use `Closes #<issue-number>` in the PR body. PRs without a linked issue will fail validation.

## Release Naming

Tag format: `Year.MonthDay.Version` (version starts at 0)
Example: `2026.903.0`
