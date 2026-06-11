; UR10e weld path validation test
; Units: mm
; Feed rates: mm/min

; Safe approach
G0 X400.0 Y-400.0 Z180.0

; Move to weld start
G1 X400.0 Y-500.0 Z40.0 F6000

; First weld segment
G1 X600.0 Y-500.0 Z40.0 F6000

; Corner
G1 X600.0 Y-700.0 Z40.0 F5000

; Return diagonal
G1 X450.0 Y-600.0 Z40.0 F5500

; Retract
G0 X450.0 Y-600.0 Z180.0

; Home
G28