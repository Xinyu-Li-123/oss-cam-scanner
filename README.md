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

## Workflow

1. Open one or more images.
2. Adjust the detected document corners by dragging the four handles.
3. Click Preview.
4. Select zero or more filters: no shadow, lighten, and enhance.
5. Click Save to keep the processed page inside the app, then continue to the next image.
6. Click Export on the last image to write files to disk.

The filters avoid hard black-and-white thresholding so dark regions and graphics from the original image are preserved.

## Feature

### Image Filter

- Select no filters to keep the perspective-corrected document unchanged.
- no shadow: Reduces uneven lighting and page shadows while preserving dark text and graphics.
- lighten: Brightens the document with a mild tone lift for dim photos.
- enhance: Improves local contrast and sharpness for a cleaner scanned look.
- Selected filters are applied in a fixed order, so the order you click them does not change the result.

### Export

- Save keeps processed pages inside the app for the current session.
- Export Images writes one PNG per saved page with a -scan suffix.
- Export PDFs writes one PDF per saved page with a -scan suffix.
- Export Combined PDF writes saved pages into one PDF. Pages start in upload order and can be rearranged before export.
