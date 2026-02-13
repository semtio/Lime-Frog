from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ToolModule:
	name: str
	label: str
	title: str
	description: str
	path: str

	def to_dict(self) -> Dict[str, str]:
		return {
			"name": self.name,
			"label": self.label,
			"title": self.title,
			"description": self.description,
			"path": self.path,
		}


_REGISTRY: Dict[str, ToolModule] = {}


def register_module(
	name: str,
	label: str,
	title: str,
	description: str,
	path: str,
) -> None:
	_REGISTRY[name] = ToolModule(
		name=name,
		label=label,
		title=title,
		description=description,
		path=path,
	)


def get_registered_modules() -> List[ToolModule]:
	return list(_REGISTRY.values())


def get_module(name: str) -> Optional[ToolModule]:
	return _REGISTRY.get(name)


def get_default_module() -> Optional[ToolModule]:
	return _REGISTRY.get("seo_checker") or next(iter(_REGISTRY.values()), None)
