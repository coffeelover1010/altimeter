# Survey test build: 2026-11-10

New Lua 5.1 checks cover cardinal targets and metre conversion, rotating-map
projection, circle clipping, contour intersections and missing vertices,
opening/closing and dragging, slider updates, build mismatch, missing facing,
missing terrain, city/manual hiding, off-map points, bounded contour strokes,
and contour caching. These are offline checks, not live-client validation.

Live acceptance for 0.3.0-test:

1. `/reload` outside a capital, then click the gauge. Confirm the two sliders,
   remote reading and minimap grid/cyan cross appear. `/altitude survey` is an
   alternative toggle.
2. Set distance to zero: the value should match the closed-panel reading.
   Set 50 m and direction zero; turn your character and verify the cross moves
   ahead. Rotate only the camera: the sample should stay tied to the character.
3. Adjust both sliders, minimap zoom and rotating-minimap mode. Check the grid
   stays aligned and the cyan cross matches the direction. A distant sample
   beyond the minimap must be labelled, not shown as a false edge cross.
4. Enable contours on a hillside. Check gold lines and responsiveness while
   walking/turning. Disable them to compare performance. Their coarse mesh is
   approximate; they are not a replacement for the exact point reading.
5. Close the controls, drag the gauge, hide it and enter a capital. Confirm no
   minimap overlay remains when hidden; closing controls restores local height.
6. Test an ocean target: DEPTH must describe that point's seabed depth while
   the panel's height difference still compares terrain elevations.

The minimap scale uses C_Minimap.GetViewRadius when available, then the installed
HereBeDragons-Pins view accessor, then standard zoom diameters if indoor/outdoor
zoom is unambiguous. It does not change the user's zoom to resolve ambiguity.
Custom minimap shapes use a conservative inscribed circle for clipping.
