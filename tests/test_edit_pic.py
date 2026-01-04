import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chat_completions import ImageResponse


class TestImageResponseEdit:

    @pytest.mark.asyncio
    async def test_edit_success(self):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(url='https://example.com/edited.png')]

        mock_client = MagicMock()
        mock_client.images.edit = AsyncMock(return_value=mock_response)

        with patch('chat_completions.openai.AsyncOpenAI', return_value=mock_client):
            result = await ImageResponse.edit(b'fake_png_bytes', 'make it red')

        assert result.success is True
        assert result.b64_or_url == 'https://example.com/edited.png'

    @pytest.mark.asyncio
    async def test_edit_bad_request_error(self):
        import openai
        mock_client = MagicMock()
        mock_client.images.edit = AsyncMock(
            side_effect=openai.BadRequestError(
                message='Invalid image',
                response=MagicMock(status_code=400),
                body=None
            )
        )

        with patch('chat_completions.openai.AsyncOpenAI', return_value=mock_client):
            result = await ImageResponse.edit(b'bad_image', 'edit prompt')

        assert result.success is False
        assert 'Не удалось отредактировать' in result.b64_or_url

    @pytest.mark.asyncio
    async def test_edit_rate_limit_error(self):
        import openai
        mock_client = MagicMock()
        mock_client.images.edit = AsyncMock(
            side_effect=openai.RateLimitError(
                message='Rate limit exceeded',
                response=MagicMock(status_code=429),
                body=None
            )
        )

        with patch('chat_completions.openai.AsyncOpenAI', return_value=mock_client):
            result = await ImageResponse.edit(b'png_bytes', 'edit prompt')

        assert result.success is False
        assert 'Рейт-лимит' in result.b64_or_url

    @pytest.mark.asyncio
    async def test_edit_timeout_error(self):
        mock_client = MagicMock()
        mock_client.images.edit = AsyncMock(side_effect=TimeoutError('Connection timed out'))

        with patch('chat_completions.openai.AsyncOpenAI', return_value=mock_client):
            result = await ImageResponse.edit(b'png_bytes', 'edit prompt')

        assert result.success is False
        assert 'Таймаут' in result.b64_or_url

    @pytest.mark.asyncio
    async def test_edit_calls_api_with_correct_params(self):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(url='https://example.com/edited.png')]

        mock_client = MagicMock()
        mock_client.images.edit = AsyncMock(return_value=mock_response)

        image_bytes = b'test_image_data'
        prompt = 'add a rainbow'

        with patch('chat_completions.openai.AsyncOpenAI', return_value=mock_client):
            await ImageResponse.edit(image_bytes, prompt)

        mock_client.images.edit.assert_called_once_with(
            model="dall-e-2",
            image=image_bytes,
            prompt=prompt,
            n=1,
            size="512x512",
        )
