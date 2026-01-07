"""
Integration tests for Replicate image editing.

These tests make real API calls and cost money. Run explicitly with:
    RUN_INTEGRATION_TESTS=1 uv run pytest tests/integration/ -v

Requires environment variables:
    - OPENAI_API_KEY
    - REPLICATE_API_TOKEN
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import pytest

# Skip all tests in this module unless explicitly running integration tests
pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_INTEGRATION_TESTS') != '1',
    reason='Integration tests skipped. Set RUN_INTEGRATION_TESTS=1 to run.',
)


@pytest.fixture
def openai_client():
    from openai import OpenAI
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        pytest.skip('OPENAI_API_KEY not set')
    return OpenAI(api_key=api_key)


@pytest.fixture
def replicate_token():
    token = os.environ.get('REPLICATE_API_TOKEN')
    if not token:
        pytest.skip('REPLICATE_API_TOKEN not set')
    return token


@pytest.mark.asyncio
async def test_dalle_generate_and_replicate_edit(openai_client, replicate_token):
    """Generate image with DALL-E, then edit with Replicate."""
    import httpx
    import replicate

    # Step 1: Generate a simple image with DALL-E
    print('\n[1/3] Generating image with DALL-E 2...')
    response = openai_client.images.generate(
        model='dall-e-2',
        prompt='a simple red apple on white background',
        size='256x256',
        n=1,
    )
    image_url = response.data[0].url
    assert image_url, 'DALL-E should return image URL'
    print(f'  Generated: {image_url[:80]}...')

    # Step 2: Download the image
    print('[2/3] Downloading generated image...')
    async with httpx.AsyncClient() as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        image_bytes = resp.content
    assert len(image_bytes) > 1000, 'Image should have reasonable size'
    print(f'  Downloaded {len(image_bytes)} bytes')

    # Step 3: Edit with Replicate instruct-pix2pix
    print('[3/3] Editing with Replicate instruct-pix2pix...')
    import base64
    from config import Config

    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    data_uri = f'data:image/png;base64,{image_b64}'

    output = await replicate.async_run(
        Config.REPLICATE_MODEL_EDIT,
        input={
            'image': data_uri,
            'prompt': 'make the apple green',
        },
    )
    result_url = output[0] if isinstance(output, list) else str(output)
    assert result_url, 'Replicate should return result URL'
    assert result_url.startswith('http'), f'Expected URL, got: {result_url}'
    print(f'  Edited: {result_url[:80]}...')
    print('\nIntegration test passed!')


@pytest.mark.asyncio
async def test_replicate_remove_background(replicate_token):
    """Test background removal with a simple generated image."""
    import httpx
    import replicate
    import base64
    from config import Config

    # Use a public test image
    test_image_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Red_Apple.jpg/800px-Red_Apple.jpg'

    print('\n[1/2] Downloading test image...')
    async with httpx.AsyncClient() as client:
        resp = await client.get(test_image_url)
        resp.raise_for_status()
        image_bytes = resp.content
    print(f'  Downloaded {len(image_bytes)} bytes')

    print('[2/2] Removing background with Replicate...')
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    data_uri = f'data:image/jpeg;base64,{image_b64}'

    output = await replicate.async_run(
        Config.REPLICATE_MODEL_REMOVE_BG,
        input={'image': data_uri},
    )
    result_url = str(output)
    assert result_url, 'Replicate should return result URL'
    assert result_url.startswith('http'), f'Expected URL, got: {result_url}'
    print(f'  Result: {result_url[:80]}...')
    print('\nBackground removal test passed!')
