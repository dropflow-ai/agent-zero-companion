"""Generate the application icon for Agent Zero Companion."""
from pathlib import Path


def create_icon():
    """Create the application icon and save to assets/."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not installed. Run: pip install Pillow")
        return

    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Create multiple sizes for cross-platform support
    sizes = [16, 32, 48, 64, 128, 256]

    images = []
    for size in sizes:
        img = _draw_icon(size)
        images.append(img)

    # Save PNG (primary)
    png_path = assets_dir / "icon.png"
    images[-1].save(str(png_path))  # 256x256
    print(f"Saved: {png_path}")

    # Save ICO (Windows)
    ico_path = assets_dir / "icon.ico"
    images[0].save(
        str(ico_path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Saved: {ico_path}")

    # Save ICNS (macOS) - requires icnsutil or manual conversion
    # For now, save a large PNG that can be converted
    icns_png_path = assets_dir / "icon_mac.png"
    images[-1].save(str(icns_png_path))
    print(f"Saved: {icns_png_path} (convert to .icns for macOS)")

    print("\nIcon generation complete!")


def _draw_icon(size: int) -> "Image":
    """Draw the Agent Zero Companion icon at the given size."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle - dark navy
    margin = max(1, size // 16)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(22, 33, 62, 255),  # #16213e
        outline=(74, 74, 138, 255),  # #4a4a8a
        width=max(1, size // 32),
    )

    # Lightning bolt - blue/purple
    cx = size // 2
    cy = size // 2
    s = size * 0.35  # Scale factor

    bolt_points = [
        (cx + s * 0.1, cy - s * 0.9),   # Top right
        (cx - s * 0.3, cy - s * 0.05),  # Middle left
        (cx + s * 0.05, cy - s * 0.05), # Middle right
        (cx - s * 0.1, cy + s * 0.9),   # Bottom left
        (cx + s * 0.3, cy + s * 0.05),  # Middle right
        (cx - s * 0.05, cy + s * 0.05), # Middle left
    ]

    draw.polygon(bolt_points, fill=(123, 140, 222, 255))  # #7b8cde

    # Add a subtle glow effect for larger sizes
    if size >= 64:
        glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        glow_draw.polygon(bolt_points, fill=(123, 140, 222, 60))

        # Expand glow slightly
        from PIL import ImageFilter
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=size // 16))
        img = Image.alpha_composite(img, glow_img)

        # Re-draw bolt on top
        draw = ImageDraw.Draw(img)
        draw.polygon(bolt_points, fill=(123, 140, 222, 255))

    return img


if __name__ == "__main__":
    create_icon()
