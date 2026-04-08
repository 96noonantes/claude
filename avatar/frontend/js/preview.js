/**
 * Simple preview - renders parts stacked by depth order on canvas
 */

const Preview = {
    init() {
        // Preview uses the same canvas as editor
    },

    renderParts(parts) {
        // Rendering handled by PartEditor.drawCanvas()
        PartEditor.drawCanvas();
    },

    highlightPart(partId) {
        PartEditor.drawCanvas();
    },
};
