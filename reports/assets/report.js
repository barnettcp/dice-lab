/* ============================================================
   DiceLab Benchmark Report – JavaScript
   ============================================================
   Managed separately from build_report.py for easier editing.
   The build script reads this file and inlines it into the HTML
   so the final report remains a single self-contained file.
   ============================================================ */

/**
 * switchPanel(prefix, value)
 *
 * Generic panel-switcher used by every dropdown in the report.
 * Hides all <div> elements whose id starts with `prefix + "-"` and then
 * reveals only the one whose id is `prefix + "-" + value`.
 *
 * This single function drives both the cross-language workload dropdown
 * (prefix = "xwl") and the per-language language/histogram dropdowns.
 */
function switchPanel(prefix, value) {
    // Collect all sibling panels for this group and deactivate them.
    document.querySelectorAll('[id^="' + prefix + '-"]').forEach(function(el) {
        el.classList.remove('active');
    });
    // Activate the selected panel.
    var target = document.getElementById(prefix + '-' + value);
    if (target) {
        // Make the panel part of layout (display:block) but invisible
        // so Plotly can measure container width without a visible flash.
        target.classList.add('active', 'resizing');
        target.querySelectorAll('.js-plotly-plot').forEach(function(plot) {
            Plotly.Plots.resize(plot);
        });
        // Allow one frame for the resize to land, then fade in.
        requestAnimationFrame(function() {
            target.classList.remove('resizing');
        });
    }
}

/**
 * Resize Plotly charts inside a <details> element when it is toggled open.
 * Without this, charts rendered inside a collapsed <details> have zero width
 * and appear broken when the user expands the section.
 */
document.addEventListener('toggle', function(e) {
    if (e.target.tagName === 'DETAILS' && e.target.open) {
        e.target.querySelectorAll('.js-plotly-plot').forEach(function(plot) {
            Plotly.Plots.resize(plot);
        });
    }
}, true);
