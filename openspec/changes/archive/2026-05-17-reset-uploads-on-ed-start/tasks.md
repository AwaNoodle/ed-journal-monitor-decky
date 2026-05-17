## 1. Tests — EDDNSubmitter.reset_stats()

- [x] 1.1 Add `test_reset_stats_clears_all_counters` — submit a success and failure, call `reset_stats()`, verify `get_stats()` returns all zeros/None
- [x] 1.2 Add `test_reset_stats_is_idempotent` — call `reset_stats()` twice on a fresh submitter, verify no error and stats remain zeroed

## 2. Tests — set_ed_running reset behavior

- [x] 2.1 Update `test_set_ed_running_true` — expect 2 emitted events (`status_update` with zeroed stats, then `ed_state_change`)
- [x] 2.2 Add `test_set_ed_running_true_resets_submitter_stats` — set up plugin with non-zero submitter counts, call `set_ed_running(True)`, verify `reset_stats()` was called
- [x] 2.3 Add `test_set_ed_running_true_emits_status_update` — call `set_ed_running(True)`, verify `status_update` is emitted with zeroed counts
- [x] 2.4 Add `test_set_ed_running_false_does_not_reset_stats` — set up plugin with non-zero counts, call `set_ed_running(False)`, verify `reset_stats()` was NOT called
- [x] 2.5 Run full test suite — all 349+ existing tests must still pass

## 3. Implementation — EDDNSubmitter.reset_stats()

- [x] 3.1 Add `reset_stats()` method to `EDDNSubmitter` that sets `_success_count = 0`, `_fail_count = 0`, `_last_upload_time = None`, `_last_upload_event = None`

## 4. Implementation — Plugin.set_ed_running() integration

- [x] 4.1 Modify `set_ed_running()` in `main.py` to call `self.submitter.reset_stats()` when `enabled is True` (with null guard on `self.submitter`)
- [x] 4.2 Emit `status_update` with zeroed stats after reset, before the existing `ed_state_change` emit
- [x] 4.3 Run full test suite — all tests must pass
