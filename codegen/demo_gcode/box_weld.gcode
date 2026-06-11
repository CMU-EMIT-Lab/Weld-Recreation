; Box Weld Demo
; Purpose: Continuous rectangular loop weld.
; Units: mm, Feed rates: mm/min

; Safe approach above the box start corner
G0 X300.0 Y300.0 Z150.0

; Plunge to the start corner (bottom-left)
G1 X300.0 Y300.0 Z15.0 F6000

; Weld segment 1: bottom edge (move +X)
G1 X450.0 Y300.0 Z15.0 F9000

; Weld segment 2: right edge (move +Y)
G1 X450.0 Y450.0 Z15.0 F9000

; Weld segment 3: top edge (move -X)
G1 X300.0 Y450.0 Z15.0 F9000

; Weld segment 4: left edge (move -Y, closing the box)
G1 X300.0 Y300.0 Z15.0 F9000

; Retract vertically
G0 X300.0 Y300.0 Z150.0

; Return home
G28
