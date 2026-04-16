# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 4 routing tests — GUTTED by BUG-AUDIT-31.

All test classes in this file exercised functions that were deleted
from ``src/unit_4/routing.py`` in BUG-AUDIT-31 (the dead-machinery
pruning pass). Every function in routing.py was dead at runtime —
zero external callers in commands/, hooks/, agents/, or bin/.

Deleted test classes and approximate test counts:
- TestResolveAction (~20 tests)
- TestMainRouting (~12 tests)
- TestCheckG32MachineGate (~8 tests)
- TestValidateGateResponse (~15 tests)
- TestPerformSnapshot (~4 tests)
- TestHandleRedGreenTransition (~25 tests)
- TestMainUpdateState (~30 tests)
- TestConsumeGateData (4 tests — already deleted in BUG-AUDIT-30)
- TestMainPrepare (~20 tests)
- TestAssembleTaskPrompt (~8 tests)
- TestProposePresentationFolderName (~6 tests)
- TestPromoteStyleDraft (~10 tests)
- TestMergeApprovalPayload (~8 tests)

See spec/stakeholder_spec.md Bug Catalog entry BUG-AUDIT-31.
"""
