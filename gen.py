import enum
from pathlib import Path
import detect
from loguru import logger
from PIL import Image, ImageDraw, ImageFilter


class GenSquareType(enum.StrEnum):
    HEAD = "head"
    EYES = "eyes"
    FACES = "faces"
    CENSORS = "censors"
    NUDENET = "nudenet"
    MONGO = "mongo"
    OPAI = "opai"
    ARMPITS = "armpits"
    FEET = "feet"


detector = {
    GenSquareType.HEAD: detect.head,
    GenSquareType.EYES: detect.eyes,
    GenSquareType.FACES: detect.faces,
    GenSquareType.CENSORS: detect.censors,
    GenSquareType.NUDENET: detect.nudenet,
    GenSquareType.MONGO: detect.nudenet_mongo,
    GenSquareType.OPAI: detect.nudenet_opai,
    GenSquareType.ARMPITS: detect.nudenet_armpits,
    GenSquareType.FEET: detect.nudenet_feet,
}


def square(
    type: GenSquareType,
    img_path: Path,
    output_dir: Path,
    target_size: int = 512,
    padding_ratio: float = 0.3,
) -> list[Path] | None:
    """
    检测对象区域并生成正方形图片

    Args:
        image_path: 输入图片路径
        output_dir: 输出目录
        target_size: 目标正方形边长 (像素)
        padding_ratio: 对象周围的扩展比例 (0.3表示在对象基础上向外扩展30%)

    Returns:
        list[Path] | None: 返回生成的正方形图片路径列表，如果未检测到对象则返回 None
    """
    if detector.get(type) is None:
        logger.error(f"不支持的类型: {type}")
        return None
    results = detector[type](img_path)
    if not results:
        logger.error("未检测到任何对象")
        return None
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    result_paths: list[Path] = []
    for i, result in enumerate(results):
        x0, y0, x1, y1 = result[0]
        # 打开图片
        img = Image.open(img_path)
        img_width, img_height = img.size

        # 计算头部中心点和扩展后的正方形尺寸
        center_x = (x0 + x1) // 2
        center_y = (y0 + y1) // 2
        base_size = max(x1 - x0, y1 - y0)
        expanded_size = int(base_size * (1 + padding_ratio * 2))

        # 计算正方形裁剪区域的初始坐标
        half_size = expanded_size // 2
        crop_x0 = max(0, center_x - half_size)
        crop_y0 = max(0, center_y - half_size)
        crop_x1 = min(img_width, center_x + half_size)
        crop_y1 = min(img_height, center_y + half_size)

        # 调整为正方形并确保不超出边界
        square_size = min(crop_x1 - crop_x0, crop_y1 - crop_y0)

        new_crop_x0 = max(0, min(center_x - square_size // 2, img_width - square_size))
        new_crop_y0 = max(0, min(center_y - square_size // 2, img_height - square_size))
        new_crop_x1 = new_crop_x0 + square_size
        new_crop_y1 = new_crop_y0 + square_size

        # 裁剪、调整尺寸并保存
        square_img = img.crop((new_crop_x0, new_crop_y0, new_crop_x1, new_crop_y1))
        final_img = square_img.resize(
            (target_size, target_size), Image.Resampling.LANCZOS
        )
        output_path = output_dir / f"{img_path.stem}_{type}_{i}.png"
        final_img.save(output_path, format="PNG")
        logger.info(f"头像已保存到: {output_path}")
        result_paths.append(output_path)
    if not result_paths:
        logger.error("未生成任何头像图片")
        return None
    return result_paths


def mask(
    type: GenSquareType,
    img_path: Path,
    output_dir: Path,
    padding_ratio: float = 0.2,
    color: str = "red",
    width: int = 8,
) -> Path:
    """Mark an area in the image based on the detected object."""
    if detector.get(type) is None:
        logger.error(f"不支持的类型: {type}")
        return img_path
    results = detector[type](img_path)
    if not results:
        logger.error("未检测到任何对象")
        return img_path
    image = Image.open(img_path)
    draw = ImageDraw.Draw(image)
    img_width, img_height = image.size

    for (x0, y0, x1, y1), _, _ in results:
        box_width = x1 - x0
        box_height = y1 - y0
        pad_w = box_width * padding_ratio
        pad_h = box_height * padding_ratio

        nx0 = max(0, x0 - pad_w)
        ny0 = max(0, y0 - pad_h)
        nx1 = min(img_width, x1 + pad_w)
        ny1 = min(img_height, y1 + pad_h)

        draw.rectangle([(nx0, ny0), (nx1, ny1)], outline=color, width=width)
    output_path = output_dir / f"{img_path.stem}_{type}_marked.png"
    image.save(output_path, format="PNG")
    logger.info(f"标记后的图片已保存到: {output_path}")
    return output_path


def highlight(
    type: GenSquareType,
    img_path: Path,
    output_dir: Path,
    padding_ratio: float = 0.3,
    blur_radius: float = 15,
    with_mask: bool = False,
    mask_color: str = "red",
    mask_width: int = 8,
) -> Path:
    if detector.get(type) is None:
        logger.error(f"Unsupported type: {type}")
        return img_path

    results = detector[type](img_path)
    if not results:
        logger.error("No objects detected")
        return img_path
    image = Image.open(img_path).convert("RGB")
    blurred = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    img_width, img_height = image.size
    mask = Image.new("L", (img_width, img_height), 0)
    mask_draw = ImageDraw.Draw(mask)
    boxes = []
    for (x0, y0, x1, y1), label, score in results:
        box_w = x1 - x0
        box_h = y1 - y0
        pad_w = box_w * padding_ratio
        pad_h = box_h * padding_ratio

        nx0 = max(0, x0 - pad_w)
        ny0 = max(0, y0 - pad_h)
        nx1 = min(img_width, x1 + pad_w)
        ny1 = min(img_height, y1 + pad_h)

        mask_draw.rectangle([(nx0, ny0), (nx1, ny1)], fill=255)
        boxes.append((nx0, ny0, nx1, ny1))

    highlighted = Image.composite(image, blurred, mask)

    if with_mask and boxes:
        draw = ImageDraw.Draw(highlighted)
        for nx0, ny0, nx1, ny1 in boxes:
            draw.rectangle(
                [(nx0, ny0), (nx1, ny1)], outline=mask_color, width=mask_width
            )

    output_path = output_dir / f"{img_path.stem}_{type}_highlighted.png"
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    highlighted.save(output_path)
    return output_path
