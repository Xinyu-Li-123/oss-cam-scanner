# OSS Cam Scanner

A desktop document scanner for photos. It finds the document region, lets you adjust the four corners, applies scan-style filters, and exports the result as images or PDFs.

## Install

```bash
uv sync
```

## Run

Open the GUI:

```bash
uv run oss-cam-scanner
```

Open the GUI with example images already queued:

```bash
uv run oss-cam-scanner path/to/image1.jpg path/to/image2.png
```

## Localization

The app uses Qt translation files for UI text. English source strings are the default fallback. Simplified Chinese translations live in:

```bash
src/oss_cam_scanner/translations/oss_cam_scanner_zh_CN.ts
```

Machine translation can be used to prefill missing entries in the TS file. Treat that output as a draft, review it in Qt Linguist, and keep human edits in the TS file.

Review or edit the TS file with Qt Linguist, then compile it for runtime use:

```bash
pyside6-lrelease src/oss_cam_scanner/translations/oss_cam_scanner_zh_CN.ts -qm src/oss_cam_scanner/translations/oss_cam_scanner_zh_CN.qm
```

Large translated documents are stored as one Markdown file per locale under `src/oss_cam_scanner/resources/docs/`.

## Workflow

1. Open one or more images.
2. Adjust the detected document corners by dragging the four handles.
3. Click Preview.
4. Select zero or more filters: no shadow, lighten, and enhance. Rotate the preview left or right if needed.
5. Click Save to keep the processed page inside the app, then continue to the next image.
6. Click Export on the last image to write files to disk.

## Feature

### Image Filter

- Don't select any filter to keep the perspective-corrected document unchanged.
- no shadow: Reduces uneven lighting and page shadows while preserving dark text and graphics.
- lighten: Brightens the document with a mild tone lift for dim photos.
- enhance: Improves local contrast and sharpness for a cleaner scanned look.
- Selected filters are applied in a fixed order, so the order you click them does not change the result.
- Rotate Left and Rotate Right are available during preview/filtering, not during corner adjustment.
- Saved and exported pages include the selected filters and preview rotation.

### Export

- Save keeps processed pages inside the app for the current session.
- Export Images writes one PNG per saved page with a -scan suffix.
- Export PDFs writes one PDF per saved page with a -scan suffix.
- Export Combined PDF writes saved pages into one PDF. Pages start in upload order and can be rearranged before export.
- PDF export supports Auto, A4, Letter, and Fit to image page sizes.
- Auto chooses one page size and orientation from the first saved page in the export order and shows that choice in the UI.
