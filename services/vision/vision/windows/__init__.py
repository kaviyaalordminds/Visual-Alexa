"""Windows-only perception backends (UI tree walking, DPI/monitor
scaling query). Every OS-specific import in this subpackage is lazy
(inside a function/method body, never at module top level) so this
package imports cleanly on non-Windows hosts — identical discipline to
computer_control.windows (docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §4),
carried forward per docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §1.
"""

from __future__ import annotations
