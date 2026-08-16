extends RefCounted
class_name SimulationProtocol
## NDJSON protocol parser (architecture §9).

static func parse_line(line: String) -> Dictionary:
	var text := line.strip_edges()
	if text.is_empty():
		return {}
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		push_warning("Invalid NDJSON object: %s" % text)
		return {}
	if not data.has("event"):
		push_warning("NDJSON missing event: %s" % text)
		return {}
	return data
