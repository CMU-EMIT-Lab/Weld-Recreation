; Weave Weld Demo
; Purpose: Simulate a simple manual weave pattern by stepping side-to-side along a path.
; Units: mm, Feed rates: mm/min

; Approach to weave start area
G0 X150.0 Y-200.0 Z150.0

; Plunge to start point
G1 X150.0 Y-200.0 Z38.0 F5000

; Weave pass step 1 (zig)
G1 X170.0 Y-205.0 Z38.0 F8000

; Weave pass step 2 (zag)
G1 X190.0 Y-195.0 Z38.0 F8000

; Weave pass step 3 (zig)
G1 X210.0 Y-205.0 Z38.0 F8000

; Weave pass step 4 (zag)
G1 X230.0 Y-195.0 Z38.0 F8000

; Weave pass step 5 (zig)
G1 X250.0 Y-205.0 Z38.0 F8000

; Weave pass step 6 (zag to end)
G1 X270.0 Y-200.0 Z38.0 F8000

; Retract Z
G0 X270.0 Y-200.0 Z150.0

; Return home
G28
