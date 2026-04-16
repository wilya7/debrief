# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""BUG-AUDIT-14 regression tests — GUTTED by BUG-AUDIT-31.

All 10 tests exercised ``main_prepare``'s template injection for the
stylist agent. ``main_prepare`` was deleted in BUG-AUDIT-31 (dead at
runtime — zero external callers). The prepare-time injection BUG-AUDIT-14
documented was structurally correct but operationally meaningless in the
consultant-orchestrated model.

See spec/stakeholder_spec.md Bug Catalog entries BUG-AUDIT-14 and
BUG-AUDIT-31.
"""
