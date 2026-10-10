"""Network statistics using the same disruption selection as the calendar."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from src.domain.disruptions import DisruptionDetail
from src.domain.lines import ALL_CODES, LINE_REGISTRY


class CategoryCount(BaseModel):
    type: str
    count: int


class LineStatistics(BaseModel):
    code: str
    name: str
    mode: str
    color: str
    text_color: str
    disruption_count: int | None


class DisruptionStatistics(BaseModel):
    generated_at: str
    total_disruptions: int
    total_lines: int
    lines_with_disruptions: int
    lines_without_disruptions: int
    failed_lines: list[str]
    lines: list[LineStatistics]
    effects: list[CategoryCount]
    causes: list[CategoryCount]


def build_statistics(
    disruptions_by_line: dict[str, list[DisruptionDetail] | None],
    now: datetime,
) -> DisruptionStatistics:
    paris_now = now.astimezone(ZoneInfo("Europe/Paris")).replace(tzinfo=None)
    unique: dict[str, DisruptionDetail] = {}
    lines = []
    failed_lines = []
    with_disruptions = 0
    without_disruptions = 0

    for code in ALL_CODES:
        info = LINE_REGISTRY[code]
        disruptions = disruptions_by_line[code]
        count = None
        if disruptions is None:
            failed_lines.append(code)
        else:
            active = {
                d.impact_id: d
                for d in disruptions
                if any(datetime.fromisoformat(p.date_fin) >= paris_now for p in d.periods)
            }
            count = len(active)
            unique.update(active)
            if count:
                with_disruptions += 1
            else:
                without_disruptions += 1
        lines.append(LineStatistics(
            code=code, name=info.name, mode=info.mode,
            color=info.color, text_color=info.text_color,
            disruption_count=count,
        ))

    # Stable ties follow the registry order; unavailable lines appear last.
    lines.sort(key=lambda line: -(line.disruption_count if line.disruption_count is not None else -1))

    def categories(values: list[str]) -> list[CategoryCount]:
        counts = Counter(value or "unknown" for value in values)
        return [
            CategoryCount(type=key, count=count)
            for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    return DisruptionStatistics(
        generated_at=now.isoformat(),
        total_disruptions=len(unique),
        total_lines=len(ALL_CODES),
        lines_with_disruptions=with_disruptions,
        lines_without_disruptions=without_disruptions,
        failed_lines=failed_lines,
        lines=lines,
        effects=categories([d.effect for d in unique.values()]),
        causes=categories([d.cause for d in unique.values()]),
    )
