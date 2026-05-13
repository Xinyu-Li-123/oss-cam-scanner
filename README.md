# OSS Cam Scanner

A desktop document scanner for photos. It finds the document region, lets you adjust the four corners, applies a scan-style filter, and saves the result as an image.

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
4. Choose one filter: original, no shadow, lighten, or enhance.
5. Save the processed PNG or JPEG, then continue to the next image.

The filters avoid hard black-and-white thresholding so dark regions and graphics from the original image are preserved.

## Feature

### Image Filter

- original: Keeps the perspective-corrected document unchanged.
- no shadow: Reduces uneven lighting and page shadows while preserving dark text and graphics.
- lighten: Brightens the document with a mild tone lift for dim photos.
- enhance: Improves local contrast and sharpness for a cleaner scanned look.
