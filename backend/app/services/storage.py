import base64
import logging
import uuid
from urllib.parse import urlparse

import boto3
import httpx
from botocore.config import Config

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

USER_AGENT = "Umbaza/1.0 (educational lesson generator; contact@umbaza.ru)"

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _s3_configured() -> bool:
    return bool(settings.s3_access_key and settings.s3_secret_key and settings.s3_bucket)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".svg", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


async def download_and_upload_url(url: str, topic: str) -> str | None:
    """Download an image from URL and upload to S3. Returns public URL or None."""
    if not _s3_configured():
        return None

    if url.startswith("data:"):
        return await upload_image_to_s3(url, topic)

    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    except Exception as e:
        logger.warning(f"Failed to download image {url[:80]}: {e}")
        return None

    ext = CONTENT_TYPE_EXT.get(content_type) or _ext_from_url(url)
    filename = f"lessons/{uuid.uuid4()}{ext}"

    try:
        s3 = get_s3_client()
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=filename,
            Body=content,
            ContentType=content_type,
            CacheControl="max-age=31536000",
        )
        public_url = f"{settings.s3_endpoint_url}/{settings.s3_bucket}/{filename}"
        logger.info(f"Rehosted image to {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload image to S3: {e}")
        return None


async def rehost_images_to_s3(urls: list[str], topic: str) -> list[str]:
    """Download external images and upload to S3. Falls back to original URLs."""
    if not urls:
        return []

    if not settings.image_rehost_s3 or not _s3_configured():
        logger.info("S3 rehost skipped (disabled or not configured), using original URLs")
        return urls

    result: list[str] = []
    for url in urls:
        rehosted = await download_and_upload_url(url, topic)
        result.append(rehosted or url)

    return result


async def upload_image_to_s3(image_data: str, topic: str) -> str:
    """Upload base64 image data to S3 and return public URL."""
    try:
        s3 = get_s3_client()

        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(image_data)
        filename = f"lessons/{uuid.uuid4()}.png"

        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=filename,
            Body=image_bytes,
            ContentType="image/png",
            CacheControl="max-age=31536000",
        )

        public_url = f"{settings.s3_endpoint_url}/{settings.s3_bucket}/{filename}"
        logger.info(f"Uploaded image to {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Failed to upload image to S3: {e}")
        raise


async def upload_lesson_images(image_data_list: list[str], topic: str) -> list[str]:
    """Upload multiple base64 images and return their URLs."""
    urls = []
    for img in image_data_list:
        try:
            url = await upload_image_to_s3(img, topic)
            urls.append(url)
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            continue
    return urls
