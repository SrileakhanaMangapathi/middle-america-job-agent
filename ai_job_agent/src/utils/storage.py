import json
from pathlib import Path
from typing import Union


def save_json(data: Union[dict, list], filepath: Union[str, Path]) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def load_json(filepath: Union[str, Path]) -> Union[dict, list]:
    with open(Path(filepath), "r", encoding="utf-8") as fh:
        return json.load(fh)
