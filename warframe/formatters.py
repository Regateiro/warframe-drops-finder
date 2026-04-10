from collections import defaultdict

from .models import DropResult


def format_results(results: list[DropResult], max_results: int = 20) -> None:
    if not results:
        print("No results found.")
        return

    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for result in results:
        key = (result.item_name, result.location, result.mission_type)
        if result.rotation not in grouped[key] or grouped[key][result.rotation] < result.chance:
            grouped[key][result.rotation] = result.chance

    sorted_groups = sorted(grouped.items(), key=lambda x: max(x[1].values()), reverse=True)

    width_item = max(len("Item"), max(len(k[0]) for k, _ in sorted_groups))
    width_location = max(len("Location"), max(len(k[1]) for k, _ in sorted_groups))
    width_type = max(len("Type"), max(len(k[2]) for k, _ in sorted_groups))
    width_rotations = max(
        len("Rotations"),
        max(len(", ".join(f"{rot}:{chance:.2f}%" for rot, chance in sorted(rots.items()))) for _, rots in sorted_groups),
    )

    header = f"{'Item':<{width_item}} | {'Location':<{width_location}} | {'Type':<{width_type}} | {'Rotations':<{width_rotations}}"
    rows = []
    for (item, location, mission_type), rotations in sorted_groups[:max_results]:
        rot_str = ", ".join(f"{rot}:{chance:.2f}%" for rot, chance in sorted(rotations.items()))
        rows.append(f"{item:<{width_item}} | {location:<{width_location}} | {mission_type:<{width_type}} | {rot_str:<{width_rotations}}")

    max_line_len = max(len(header), max(len(r) for r in rows) if rows else 0)

    print(f"\nFound {len(results)} drops across {len(sorted_groups)} locations. Showing best {max_results}:\n")
    print(header)
    print("-" * max_line_len)
    for row in rows:
        print(row)


def format_multi_results(results: list[DropResult], queries: list[str], max_results: int = 20) -> None:
    if not results:
        print("No results found.")
        return

    by_location: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for result in results:
        key = (result.location, result.mission_type)
        display_name = result.item_name.replace(" Relic", "")
        if result.rotation not in by_location[key][display_name] or by_location[key][display_name][result.rotation] < result.chance:
            by_location[key][display_name][result.rotation] = result.chance

    def location_score(entry: tuple) -> tuple[int, float]:
        _, items_dict = entry
        best_chance = max(c for v in items_dict.values() for c in v.values())
        return len(items_dict), best_chance

    sorted_locations = sorted(by_location.items(), key=location_score, reverse=True)

    item_columns = sorted(set(r.item_name.replace(" Relic", "") for r in results))

    width_num = 3
    width_location = max(len("Location"), max(len(k[0]) for k, _ in sorted_locations))
    width_type = max(len("Type"), max(len(k[1]) for k, _ in sorted_locations))
    width_item = max(len(item) for item in item_columns) if item_columns else 10
    for _, items_dict in sorted_locations:
        for _, rotations in items_dict.items():
            if rotations:
                best_rot = max(rotations.items(), key=lambda x: x[1])
                width_item = max(width_item, len(f"{best_rot[0]}:{best_rot[1]:.2f}%"))

    header_parts = [f"{'#':<{width_num}}", f"{'Location':<{width_location}}", f"{'Type':<{width_type}}"]
    for item in item_columns:
        header_parts.append(f"{item:<{width_item}}")
    header = " | ".join(header_parts)

    rows = []
    for idx, ((location, mission_type), items_dict) in enumerate(sorted_locations[:max_results], 1):
        row_parts = [f"{idx:<{width_num}}", f"{location:<{width_location}}", f"{mission_type:<{width_type}}"]
        for item in item_columns:
            if item in items_dict:
                rotations = items_dict[item]
                best_rot = max(rotations.items(), key=lambda x: x[1])
                row_parts.append(f"{best_rot[0]}:{best_rot[1]:.2f}%".ljust(width_item))
            else:
                row_parts.append("-".ljust(width_item))
        rows.append(" | ".join(row_parts))

    max_line_len = max(len(header), max(len(r) for r in rows) if rows else 0)
    sep = "-" * max_line_len

    print(f"\nFound {len(results)} drops across {len(sorted_locations)} locations. Showing best {max_results}:\n")
    print(header)
    print(sep)
    for row in rows:
        print(row)
