; Multi-pass Linear Weld Demo
; Purpose: Perform two parallel linear weld passes along the X axis.
; Units: mm, Feed rates: mm/min

; Safe approach to start area
G0 X100.0 Y100.0 Z150.0

; Plunge to start of first weld pass
G1 X100.0 Y100.0 Z10.0 F6000

; First weld pass (100mm length along X)
G1 X200.0 Y100.0 Z10.0 F12000

; Lift tool for rapid move
G0 X200.0 Y100.0 Z50.0

; Rapid to start of second weld pass (parallel, offset by 10mm in Y)
G0 X100.0 Y110.0 Z50.0

; Plunge to start of second weld pass
G1 X100.0 Y110.0 Z10.0 F6000

; Second weld pass (100mm length along X)
G1 X200.0 Y110.0 Z10.0 F12000

; Retract to safe height
G0 X200.0 Y110.0 Z150.0

; Safe return home
G28
