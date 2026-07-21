from aiogram.filters import Filter

from config import Config


class ConfigFilter(Filter):
    def __init__(self, method_name: str) -> None:
        self._method_name = method_name

    async def __call__(self, message, config: Config) -> bool:
        method = getattr(config, self._method_name)
        return await method(message)


chat_allowed = ConfigFilter('filter_chat_allowed')
command_enabled = ConfigFilter('filter_command_not_disabled_for_chat')
is_admin = ConfigFilter('filter_is_admin')
summary_enabled = ConfigFilter('filter_summary_enabled')
voice_enabled = ConfigFilter('filter_voice_enabled')
