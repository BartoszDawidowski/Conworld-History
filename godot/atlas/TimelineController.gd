extends Node
class_name TimelineController
## Monthly climate controls for temperature / precipitation map modes.

signal month_changed(month: int)

var month: int = 1
var months: int = 12


func set_months(n: int) -> void:
	months = maxi(1, n)
	month = clampi(month, 1, months)


func set_month(m: int) -> void:
	month = clampi(m, 1, months)
	month_changed.emit(month)


func next_month() -> void:
	set_month(month + 1 if month < months else 1)


func prev_month() -> void:
	set_month(month - 1 if month > 1 else months)
