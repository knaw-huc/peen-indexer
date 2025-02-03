class SearchResultItem:

    def __init__(self, values: dict[str, any]):
        self.values = values

    def __str__(self) -> str:
        return self.values.__str__()

    def path(self, path: str) -> any:
        result = self.values
        for step in path.split('.'):
            if step in result:
                result = result[step]
            else:
                return None
        return result

    def first_target_with_selector(self, text_type: str) -> dict[str, any]:
        for target in self.path('target'):
            if 'type' in target and target['type'] == text_type and 'selector' in target:
                return target

    def first_target_without_selector(self, text_type: str) -> dict[str, any]:
        for target in self.path('target'):
            if 'type' in target and target['type'] == text_type and 'selector' not in target:
                return target
