# Codebase architecture

This doc explains the architecture design of oss-cam-scanner.

## Layers

We divide the app into multiple layers, and use signals to communicates between layers.

Stores own mutable application facts. `DocumentStore` owns imported items and current selection, `PreviewState` owns selected filters and the current preview image, and `ExportState` owns export order and PDF page-size choice.

Controllers provides high-level methods to mutate the stores and hide implementation details. They are initialized with stores, and expose public methods of how the stores should be modified. For example, `PreviewController.rotate_current` will rotate the currently selected document in `DocumentStore`. Pages should not directly modify stores, and should only do it via controllers.

Pages and widgets render UI and emit user-intent signals. Examples are `AdjustPage`, `PreviewPage`, `ExportPage`, `DocumentCanvas`, and `ImageListView`. They should not perform image processing, export files, or own workflow state.

Binders connect pages to stores and controllers. They keep page-specific signal wiring out of `ScannerWindow`, translate controller results into higher-level outcomes, and update pages when state changes.

And finally, `ScannerWindow` is the composition root. It creates stores, controllers, pages, binders, the toolbar, and the stacked page layout. It owns app-level concerns: file dialogs, message boxes, startup paths, and navigation between pages.

## Common flows

### Import images

1. The user clicks "Open Images" in the toolbar or empty page.
2. `ScannerWindow` opens a file dialog and passes selected paths to `ImportController`.
3. `ImportController` reads each image, detects document corners, creates `ImageItem` objects, and inserts successful items into `DocumentStore`.
4. `DocumentStore` emits item/selection signals.
5. `ImageListBinder` refreshes `ImageListView`.
6. `ScannerWindow` selects the first imported image and shows `AdjustPage`.
7. Failed imports are reported by `ScannerWindow` with message boxes.

### Edit corners and preview

1. The user drags a corner handle on `DocumentCanvas`.
2. `DocumentCanvas` emits `polygon_changed`; `AdjustPage` forwards it.
3. `AdjustPageBinder` calls `EditController.set_current_polygon`.
4. `EditController` updates `DocumentStore` and clears stale preview state.
5. The user clicks "Preview".
6. `AdjustPageBinder` calls `EditController.prepare_current_preview`.
7. `EditController` orders the points, warps the image, updates item status, and returns a result.
8. On success, `ScannerWindow` switches to `PreviewPage`; `PreviewPageBinder` asks `PreviewController` to render the filtered preview.

### Apply filters or rotate

1. The user changes a filter checkbox or clicks a rotate button on `PreviewPage`.
2. `PreviewPageBinder` calls `PreviewController`.
3. `PreviewController` applies filters, applies rotation, and stores the preview image in `PreviewState`.
4. `PreviewState` emits `preview_image_changed`.
5. `PreviewPageBinder` updates `PreviewPage`, which redraws the preview label.

### Save and next

1. The user clicks "Save And Next".
2. `PreviewPageBinder` calls `PreviewController.save_current_and_select_next`.
3. `PreviewController` ensures a preview image exists, copies it into the current `ImageItem`, marks the item saved, and asks `DocumentStore` for the next unsaved index.
4. `DocumentStore` emits item and saved-item signals.
5. `ImageListBinder` refreshes the sidebar status.
6. `PreviewPageBinder` emits the next index.
7. `ScannerWindow` selects that item and shows `AdjustPage`.

### Export

1. The user opens the export page.
2. `ScannerWindow` asks `ExportPageBinder` to sync saved items.
3. `ExportState` preserves existing export order, removes unsaved pages, and appends newly saved pages.
4. `ExportPageBinder` updates `ExportPage` with saved pages, thumbnails, order, and PDF page-size label.
5. When the user chooses an export action, `ExportPageBinder` asks `ScannerWindow` for a destination path.
6. `ScannerWindow` opens the file or directory dialog and passes the chosen path back to `ExportPageBinder`.
7. `ExportPageBinder` calls `ExportController`, which writes files through `core.io`.
8. `ScannerWindow` shows the completion or failure message.

## How to add new features under this architecture

New behavior should follow this rule: pages display, binders wire, controllers operate, stores remember, core computes, and `ScannerWindow` navigates.
