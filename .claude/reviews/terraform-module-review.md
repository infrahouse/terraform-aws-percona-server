# Terraform Module Review: Percona Server Version Selection

**Module:** `terraform-aws-percona-server`
**Review Date:** 2026-03-01
**Diff Reviewed:** `.claude/reviews/pr-changes.diff`

---

## Summary

This changeset introduces the ability to select a specific Percona Server version (8.0 or 8.4) when deploying
the cluster. It adds a new `percona_server_version` variable with validation, passes the version through to
both cloud-init (Puppet custom facts) and EC2 instance tags, expands the test matrix to cover both version
tracks, and applies several robustness fixes to the Makefile and test harness.

---

## Changes Analyzed

### 1. New Variable: `percona_server_version` (variables.tf)

**What changed:** A new nullable string variable with a HEREDOC description and regex validation block.

**Assessment: GOOD**

- The variable follows coding standards: uses `type = string`, provides a descriptive HEREDOC description,
  defaults to `null`, and includes a validation block.
- The validation correctly uses the ternary pattern (`var.percona_server_version == null ? true : ...`) to
  handle nullable variables, as required by the coding standard's "CRITICAL" note on validation blocks.
- The regex `^(latest|8\\.[04]\\..+)$` correctly matches:
  - `"latest"` -- latest 8.4 track
  - `"8.0.x"` and `"8.4.x"` version strings
- The error message explains what went wrong and provides examples of correct values.

**Minor observations:**

- The regex character class `[04]` permits only `8.0.x` and `8.4.x`, which is appropriate since Percona
  Server only offers these two major tracks. If a future `8.8.x` or `9.x` line appears, the regex will need
  updating, but that is an acceptable maintenance tradeoff versus being overly permissive now.
- The regex `.+` suffix allows any characters after the major.minor prefix (e.g., `8.0.45-36-1.noble`).
  This is intentional per the description, which states that both short and full apt version strings are
  accepted. However, it also means a clearly invalid value like `"8.0."` (trailing dot, no version) would
  pass validation. The practical risk is negligible since Puppet/apt would fail clearly on such input.

### 2. Cloud-Init Fact Propagation (cloud_init.tf)

**What changed:** Added `server_version` to the `percona` custom facts map:
```hcl
server_version = var.percona_server_version != null ? var.percona_server_version : ""
```

**Assessment: GOOD**

- Uses empty string as the null-safe fallback, which is appropriate for Puppet facts -- Puppet can check
  for empty string to determine "use default behavior."
- Placement is correct: the value is inside the module-managed `percona` fact map, before the
  `lookup(var.puppet_custom_facts, "percona", {})` merge, meaning a user can still override
  `server_version` via `puppet_custom_facts` if needed. This follows the existing deep-merge convention
  documented in the variable description.
- Consistent with how other facts (e.g., `vpc_cidr`, `credentials_secret`) are passed.

### 3. Instance Tags (locals.tf)

**What changed:** Added `"percona:server_version"` to `local.instance_tags`:
```hcl
"percona:server_version" = var.percona_server_version != null ? var.percona_server_version : ""
```

**Assessment: GOOD**

- Follows the existing `percona:*` tag naming convention used for all other Puppet facts passed via
  instance metadata tags.
- Since the ASG has `triggers = ["tag"]` in its `instance_refresh` block (main.tf line 102), changing
  `percona_server_version` will trigger a rolling instance refresh. This is explicitly documented in the
  variable description and is the correct behavior for safe rolling upgrades.
- The null-to-empty-string conversion is consistent with `cloud_init.tf`.

### 4. Makefile Quoting Fix

**What changed:** `TEST_SELECTOR` is now quoted in the `-k` flag for both `test-keep` and `test-clean`:
```makefile
-k "$(TEST_SELECTOR)" \
```

**Assessment: GOOD**

- This is a necessary bug fix. Without quoting, a selector like `"percona-8.0 and aws-6"` would be
  split by the shell into separate arguments, causing pytest to misinterpret the `-k` filter.
- With the new test parametrization adding `percona-8.0`/`percona-8.4` IDs alongside `aws-5`/`aws-6`,
  compound selectors using `and` become essential (e.g., `TEST_SELECTOR="percona-8.0 and aws-6"`).
- The default `TEST_SELECTOR ?= aws-6` (a single word) would have worked without quotes, but the fix
  is forward-compatible and correct.

### 5. Test Data: Root Module (test_data/percona-server/)

**What changed:**

- `main.tf`: Added `percona_server_version = var.percona_server_version` to the module call, with
  alignment reformatting.
- `variables.tf`: Added the pass-through variable with `default = null`.

**Assessment: GOOD**

- The test root module correctly passes the version through as a variable, allowing the test to set it
  via `terraform.tfvars`.
- The variable definition is minimal and appropriate for a test fixture -- the real validation lives
  in the module's `variables.tf`.
- Alignment reformatting in `main.tf` is clean and consistent.

### 6. Test Expansion (tests/test_module.py)

**What changed:**

1. **New parametrization:** Added `percona_server_version` parameter with values `[None, "8.4.7-7"]` and
   IDs `["percona-8.0", "percona-8.4"]`.
2. **Conditional tfvars writing:** Only writes `percona_server_version` to `terraform.tfvars` when the
   value is not `None`.
3. **Idempotent user creation:** Changed `CREATE USER` to `CREATE USER IF NOT EXISTS`.
4. **Idempotent Sakila loading:** Added `wget -qN` (timestamping), `DROP DATABASE IF EXISTS sakila`
   before schema load.

**Assessment: GOOD with observations**

**Parametrization:**
- The cross-product of AWS provider versions (2) x Percona versions (2) = 4 test cases total. This is a
  significant expansion of the test matrix. Each test deploys real AWS infrastructure (3 EC2 instances,
  NLB, DynamoDB, S3), so CI runtime will roughly double. This is a valid tradeoff for testing a new
  major feature but should be monitored for CI duration impact.
- The test IDs (`percona-8.0`, `percona-8.4`) are clear and work well with the `TEST_SELECTOR` mechanism.

**Idempotency fixes:**
- `CREATE USER IF NOT EXISTS` prevents failures if the test is re-run with `--keep-after` against existing
  infrastructure. This is a good defensive fix.
- `wget -qN` uses HTTP timestamping to avoid re-downloading an unchanged file. Combined with
  `DROP DATABASE IF EXISTS sakila`, this makes the Sakila setup idempotent. Both are good improvements for
  test reliability, especially relevant now that the same infrastructure may be tested across multiple
  parametrized runs.

**Observation on test design:**
- The `None` parameter correctly maps to "don't write percona_server_version to tfvars," which means
  the module defaults to `null`, which means Puppet installs the default 8.0 LTS. This is clean.
- The `"8.4.7-7"` version is hardcoded in the test. If this specific Percona release is removed from
  the repo mirrors, the test will fail. This is acceptable for integration tests (they inherently depend
  on external state), but worth noting.

### 7. README.md Update

**What changed:** Added the new `percona_server_version` variable to the auto-generated terraform-docs table.

**Assessment: GOOD**

- The entry is correctly placed alphabetically in the variables table.
- The description in the table matches the HEREDOC in `variables.tf` (with HTML `<br/>` formatting from
  terraform-docs).
- This was generated by `terraform-docs` (the `make docs` target), not hand-edited.

---

## Security Assessment

| Area | Status | Notes |
|------|--------|-------|
| Secrets exposure | No issues | No secrets are added or modified |
| IAM permissions | No issues | No IAM changes in this diff |
| Network security | No issues | No security group changes |
| Input validation | Good | Regex validation prevents arbitrary input |
| Supply chain | Acceptable | Version pinning uses Percona's own versioning scheme |

The `percona_server_version` value flows into:
1. EC2 instance tags (metadata) -- not sensitive
2. Puppet custom facts via cloud-init userdata -- not sensitive

No secrets, IAM policies, security group rules, or encryption settings are modified.

---

## Functionality Assessment

| Area | Status | Notes |
|------|--------|-------|
| Version selection | Correct | Null = default 8.0 LTS, explicit = 8.4 or pinned version |
| Rolling upgrades | Correct | Tag change triggers ASG instance refresh via `triggers = ["tag"]` |
| Backward compatibility | Preserved | Default is `null` (same behavior as before this change) |
| Test coverage | Good | Both 8.0 (default) and 8.4 are tested against both AWS provider versions |
| Idempotency | Improved | Test harness now handles re-runs cleanly |

---

## Code Standards Compliance

| Standard | Status | Notes |
|----------|--------|-------|
| Max line length (120) | Compliant | All added lines are within limit |
| Files end with newline | Compliant | Verified in all changed files |
| Snake_case naming | Compliant | `percona_server_version`, `server_version` |
| Terraform variable type | Compliant | Explicit `type = string` |
| Validation ternary pattern | Compliant | Uses `var.x == null ? true : ...` as required |
| HEREDOC for long descriptions | Compliant | Variable description uses `<<-EOT` |
| InfraHouse registry | N/A | No new module dependencies added |
| Exact version pinning | N/A | No module version changes |
| IAM data source policy | N/A | No IAM changes |
| Error message quality | Good | Includes what's wrong and how to fix |

---

## Potential Issues and Risks

### Low Risk

1. **Regex allows minimal versions like `"8.0."` or `"8.4.a"`:** The `.+` suffix is permissive. In practice,
   these would fail at Puppet/apt level with a clear error, so the risk is minimal. A stricter regex like
   `^(latest|8\.[04]\.\d+.*)$` could enforce a numeric component after the minor version, but this adds
   marginal value.

2. **Test matrix doubling:** CI runtime will approximately double with 4 test combinations instead of 2.
   Each test provisions a 3-node Percona cluster with full Puppet bootstrap (~15 minutes per run). Monitor
   CI job duration after merge.

3. **Hardcoded test version `"8.4.7-7"`:** If Percona removes this specific package version from their
   apt repository, the `percona-8.4` test variant will fail. This is inherent to integration tests and
   can be addressed by updating the version string when needed.

### No Risk

4. **Backward compatibility:** The default value is `null`, and the null-to-empty-string conversion in
   both `cloud_init.tf` and `locals.tf` means existing deployments that do not set this variable will see
   no change in behavior (empty string = Puppet installs default 8.0).

---

## Verdict

**APPROVE** -- This is a clean, well-structured feature addition that follows InfraHouse coding standards
consistently. The variable design (nullable with validation), fact propagation (both cloud-init and instance
tags), rolling upgrade trigger mechanism, and expanded test coverage are all implemented correctly. The
Makefile quoting fix and test idempotency improvements are valuable secondary fixes. No security concerns.
The only items to monitor post-merge are CI duration and the hardcoded Percona 8.4 version in tests.