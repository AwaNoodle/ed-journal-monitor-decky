## 1. Backend

- [x] 1.1 Remove `_last_upload_time` and `_last_upload_event` instance variables from `Submitter.__init__` in `src/modules/submitter.py`
- [x] 1.2 Remove the two lines that set those fields after a successful upload in `Submitter._submit`
- [x] 1.3 Remove `last_upload_time` and `last_upload_event` keys from the dict returned by `Submitter.get_status`
- [x] 1.4 Remove the lines that reset those fields in `Submitter.reset_stats`

## 2. TypeScript Types

- [x] 2.1 Remove `last_upload_time: string | null` and `last_upload_event: string | null` from the `PluginStatus` interface in `src/types.d.ts`
- [x] 2.2 Remove the same two fields from the `StatusUpdate` interface in `src/types.d.ts`

## 3. Frontend

- [x] 3.1 Remove `lastUpload` and `lastUploadEvent` state declarations from `Content.tsx`
- [x] 3.2 Remove the lines in the `status_update` event handler that call `setLastUpload` and `setLastUploadEvent`
- [x] 3.3 Remove the lines in the `upload_success` event handler that call `setLastUploadEvent`
- [x] 3.4 Remove both `PanelSectionRow` blocks for "Last Upload" (the populated branch and the "No uploads yet" branch) from the JSX in `Content.tsx`
