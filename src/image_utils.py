import io
import logging

import numpy as np
from PIL import Image


logger = logging.getLogger(__name__)


def create_mask_from_comparison(
    original_bytes: bytes,
    marked_bytes: bytes,
    threshold: int = 30,
    min_region_size: int = 100,
) -> bytes:
    """
    Create a mask by comparing original and marked images.

    The mask is a PNG with:
    - Transparent (alpha=0) pixels where user drew (areas to edit)
    - Opaque pixels (alpha=255) where images are similar (areas to keep)

    Args:
        original_bytes: PNG bytes of original image
        marked_bytes: PNG bytes of image with user markings
        threshold: Color difference threshold (0-255) to detect changes
        min_region_size: Minimum pixel count for a valid marking region

    Returns:
        PNG bytes of the mask image (RGBA format, 512x512)

    Raises:
        ValueError: If no significant marked areas are detected
    """
    logger.debug(
        'Creating mask: original_size=%d, marked_size=%d, threshold=%d',
        len(original_bytes), len(marked_bytes), threshold
    )

    # Load images
    original = Image.open(io.BytesIO(original_bytes)).convert('RGB')
    marked = Image.open(io.BytesIO(marked_bytes)).convert('RGB')

    # Resize both to 512x512 (DALL-E 2 requirement)
    original = original.resize((512, 512), Image.Resampling.LANCZOS)
    marked = marked.resize((512, 512), Image.Resampling.LANCZOS)

    # Convert to numpy arrays
    orig_arr = np.array(original).astype(np.float32)
    mark_arr = np.array(marked).astype(np.float32)

    # Compute per-pixel Euclidean distance in RGB space
    diff = np.sqrt(np.sum((orig_arr - mark_arr) ** 2, axis=2))

    # Create mask: 0 where different (transparent = edit), 255 where similar (opaque = keep)
    mask_alpha = np.where(diff > threshold, 0, 255).astype(np.uint8)

    # Check if any edit areas were detected
    transparent_pixels = np.sum(mask_alpha == 0)
    logger.debug('Detected %d transparent pixels (edit areas)', transparent_pixels)

    if transparent_pixels < min_region_size:
        raise ValueError(
            f'Could not detect marked areas. Found only {transparent_pixels} different pixels. '
            'Please draw more clearly over the areas you want to edit.'
        )

    # Create RGBA mask image (RGB can be anything, alpha matters for DALL-E)
    mask_rgb = np.zeros((512, 512, 3), dtype=np.uint8)
    mask_rgba = np.dstack([mask_rgb, mask_alpha])

    mask_image = Image.fromarray(mask_rgba, mode='RGBA')

    # Save to bytes
    buffer = io.BytesIO()
    mask_image.save(buffer, format='PNG')
    result = buffer.getvalue()

    logger.info(
        'Mask created: size=%d bytes, edit_pixels=%d (%.1f%%)',
        len(result), transparent_pixels, transparent_pixels / (512 * 512) * 100
    )

    return result


def prepare_image_for_dalle(image_bytes: bytes) -> bytes:
    """
    Prepare any image for DALL-E 2 edit API.

    Converts to RGBA PNG and resizes to 512x512.

    Args:
        image_bytes: Raw image bytes (any format PIL supports)

    Returns:
        PNG bytes ready for DALL-E 2 (RGBA, 512x512)
    """
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert('RGBA')
    image = image.resize((512, 512), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    result = buffer.getvalue()

    logger.debug('Image prepared for DALL-E: size=%d bytes', len(result))

    return result
