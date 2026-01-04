import io

import pytest
from PIL import Image

import sys
sys.path.insert(0, 'src')

from image_utils import create_mask_from_comparison, prepare_image_for_dalle


def create_solid_image(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> bytes:
    """Helper to create a solid color test image."""
    img = Image.new('RGB', size, color)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def create_image_with_rectangle(
    bg_color: tuple[int, int, int],
    rect_color: tuple[int, int, int],
    rect_bounds: tuple[int, int, int, int],
    size: tuple[int, int] = (100, 100),
) -> bytes:
    """Helper to create an image with a colored rectangle."""
    img = Image.new('RGB', size, bg_color)
    for x in range(rect_bounds[0], rect_bounds[2]):
        for y in range(rect_bounds[1], rect_bounds[3]):
            if 0 <= x < size[0] and 0 <= y < size[1]:
                img.putpixel((x, y), rect_color)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


class TestCreateMaskFromComparison:
    def test_identical_images_raises_error(self):
        """When images are identical, no edit areas should be detected."""
        img = create_solid_image((100, 100, 100))
        with pytest.raises(ValueError, match='Could not detect marked areas'):
            create_mask_from_comparison(img, img)

    def test_completely_different_images_creates_full_mask(self):
        """When images are completely different, entire mask should be transparent."""
        original = create_solid_image((0, 0, 0))
        marked = create_solid_image((255, 255, 255))

        mask = create_mask_from_comparison(original, marked)

        mask_img = Image.open(io.BytesIO(mask))
        assert mask_img.mode == 'RGBA'
        assert mask_img.size == (512, 512)

        # Check that most pixels are transparent (edit area)
        mask_arr = list(mask_img.getdata())
        transparent_count = sum(1 for pixel in mask_arr if pixel[3] == 0)
        assert transparent_count == 512 * 512

    def test_partial_marking_detected(self):
        """Partial markings on image should create partial mask."""
        # Create original with solid gray background
        original = create_solid_image((100, 100, 100), size=(512, 512))

        # Create marked with a red rectangle in center
        marked = create_image_with_rectangle(
            bg_color=(100, 100, 100),
            rect_color=(255, 0, 0),
            rect_bounds=(200, 200, 300, 300),
            size=(512, 512),
        )

        mask = create_mask_from_comparison(original, marked)
        mask_img = Image.open(io.BytesIO(mask))

        # Check center is transparent (edit area)
        center_alpha = mask_img.getpixel((250, 250))[3]
        assert center_alpha == 0

        # Check corner is opaque (keep area)
        corner_alpha = mask_img.getpixel((10, 10))[3]
        assert corner_alpha == 255

    def test_mask_is_512x512(self):
        """Mask should always be resized to 512x512."""
        # Create images of different sizes
        original = create_solid_image((100, 100, 100), size=(200, 300))
        marked = create_solid_image((255, 0, 0), size=(200, 300))

        mask = create_mask_from_comparison(original, marked)
        mask_img = Image.open(io.BytesIO(mask))

        assert mask_img.size == (512, 512)

    def test_threshold_affects_detection(self):
        """Higher threshold should require bigger color differences."""
        original = create_solid_image((100, 100, 100), size=(512, 512))
        # Slightly different color
        marked = create_solid_image((110, 110, 110), size=(512, 512))

        # With low threshold, should detect difference
        mask_low = create_mask_from_comparison(original, marked, threshold=10)
        mask_low_img = Image.open(io.BytesIO(mask_low))
        low_transparent = sum(1 for p in mask_low_img.getdata() if p[3] == 0)

        # With high threshold, should NOT detect difference (raises error)
        with pytest.raises(ValueError):
            create_mask_from_comparison(original, marked, threshold=50)

    def test_min_region_size_validation(self):
        """Should raise error if marked region is too small."""
        original = create_solid_image((100, 100, 100), size=(512, 512))
        # Create marked with tiny difference (single pixel)
        marked_img = Image.new('RGB', (512, 512), (100, 100, 100))
        marked_img.putpixel((256, 256), (255, 0, 0))
        buffer = io.BytesIO()
        marked_img.save(buffer, format='PNG')
        marked = buffer.getvalue()

        with pytest.raises(ValueError, match='Could not detect marked areas'):
            create_mask_from_comparison(original, marked, min_region_size=100)


class TestPrepareImageForDalle:
    def test_converts_to_rgba(self):
        """Should convert any image to RGBA."""
        # Create RGB image (no alpha)
        rgb_img = Image.new('RGB', (100, 100), (100, 100, 100))
        buffer = io.BytesIO()
        rgb_img.save(buffer, format='PNG')

        result = prepare_image_for_dalle(buffer.getvalue())
        result_img = Image.open(io.BytesIO(result))

        assert result_img.mode == 'RGBA'

    def test_resizes_to_512(self):
        """Should resize to 512x512."""
        large_img = Image.new('RGBA', (1000, 800), (100, 100, 100, 255))
        buffer = io.BytesIO()
        large_img.save(buffer, format='PNG')

        result = prepare_image_for_dalle(buffer.getvalue())
        result_img = Image.open(io.BytesIO(result))

        assert result_img.size == (512, 512)

    def test_handles_jpeg_input(self):
        """Should handle JPEG input and convert to PNG."""
        jpeg_img = Image.new('RGB', (100, 100), (100, 100, 100))
        buffer = io.BytesIO()
        jpeg_img.save(buffer, format='JPEG')

        result = prepare_image_for_dalle(buffer.getvalue())
        result_img = Image.open(io.BytesIO(result))

        assert result_img.mode == 'RGBA'
        assert result_img.size == (512, 512)

    def test_output_is_png(self):
        """Should output PNG format."""
        img = create_solid_image((100, 100, 100))

        result = prepare_image_for_dalle(img)

        # PNG files start with specific bytes
        assert result[:8] == b'\x89PNG\r\n\x1a\n'
