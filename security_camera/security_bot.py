"""
Security and Surveillance Bot
==============================
Detects motion from the laptop camera and sends photos to Telegram.
Usage: python security_bot.py

Requirements:
    pip install opencv-python requests python-dotenv

Setup:
    1. Fill in bot_token and chat_id fields in config.ini
    2. pip install opencv-python requests
    3. python security_bot.py
"""

import cv2
import numpy as np
import requests
import configparser
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

def load_config(config_path="config.ini"):
    """Read config.ini and .env files, return settings."""
    # Load sensitive credentials from .env file
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id or "BURAYA" in bot_token:
        print("ERROR: Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file!")
        print("Read the README for details.")
        exit(1)

    # Read technical settings from config.ini
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    settings = {
        "bot_token": bot_token,
        "chat_id": chat_id,
        "threshold": config.getint("detection", "threshold"),
        "min_contour_area": config.getint("detection", "min_contour_area"),
        "cooldown": config.getint("detection", "cooldown"),
        "captures_dir": config.get("storage", "captures_dir"),
        "log_file": config.get("storage", "log_file"),
    }

    return settings


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def setup_logger(log_file):
    """Set up a logger that writes to both console and file."""
    logger = logging.getLogger("SecurityBot")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Write to file
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Write to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# ─────────────────────────────────────────────
# Telegram Sending
# ─────────────────────────────────────────────

def send_telegram_photo(bot_token, chat_id, photo_path, caption=""):
    """Send a photo using the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    try:
        with open(photo_path, "rb") as photo:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": photo},
                timeout=30,
            )

        if response.status_code == 200:
            return True
        else:
            return False

    except requests.exceptions.RequestException:
        return False


# ─────────────────────────────────────────────
# Motion Detection
# ─────────────────────────────────────────────

def detect_motion(prev_gray, curr_gray, threshold, min_contour_area):
    """
    Compute the difference between two grayscale frames.
    Returns (True, total_motion_area) if motion is detected.
    """
    # Absolute difference between two frames
    frame_diff = cv2.absdiff(prev_gray, curr_gray)

    # Apply threshold — white if diff > threshold, black otherwise
    _, thresh = cv2.threshold(frame_diff, threshold, 255, cv2.THRESH_BINARY)

    # Remove noise — eliminate small dots
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.dilate(thresh, kernel, iterations=2)
    thresh = cv2.erode(thresh, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter large contours
    total_area = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_contour_area:
            total_area += area

    motion_detected = total_area > 0
    return motion_detected, total_area


# ─────────────────────────────────────────────
# Main Loop
# ─────────────────────────────────────────────

def main():
    # Load settings
    settings = load_config()

    # Create directories
    captures_dir = Path(settings["captures_dir"])
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Set up logger
    logger = setup_logger(settings["log_file"])
    logger.info("=" * 50)
    logger.info("Security bot started")
    logger.info(f"Threshold: {settings['threshold']}, Min area: {settings['min_contour_area']}")
    logger.info(f"Cooldown: {settings['cooldown']} seconds")
    logger.info(f"Photos: {captures_dir.absolute()}")
    logger.info("=" * 50)

    # Open camera
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Could not open camera! Make sure the camera is connected.")
        return

    logger.info("Camera opened. Motion detection active.")
    logger.info("Press Ctrl+C to stop.")

    # Capture first frame
    ret, frame = cap.read()
    if not ret:
        logger.error("Could not read frame from camera!")
        cap.release()
        return

    # Focus on center of camera view (ROI)
    height, width = frame.shape[:2]
    roi_margin_x = int(width * 0.15)   # Trim 15% from left and right edges
    roi_margin_y = int(height * 0.10)  # Trim 10% from top and bottom

    logger.info(f"Camera resolution: {width}x{height}")
    logger.info(f"Monitored region: center ({width - 2*roi_margin_x}x{height - 2*roi_margin_y})")

    # Convert first frame to grayscale
    roi = frame[roi_margin_y:height-roi_margin_y, roi_margin_x:width-roi_margin_x]
    prev_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

    last_trigger_time = 0  # Last trigger timestamp
    frame_count = 0
    send_queue = []  # Failed-to-send photos

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Could not read frame, retrying...")
                time.sleep(0.5)
                continue

            frame_count += 1

            # Analyze every 3rd frame (for performance)
            if frame_count % 3 != 0:
                continue

            # Crop ROI
            roi = frame[roi_margin_y:height-roi_margin_y, roi_margin_x:width-roi_margin_x]

            # Grayscale + blur
            curr_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.GaussianBlur(curr_gray, (21, 21), 0)

            # Motion detection
            motion, area = detect_motion(
                prev_gray, curr_gray,
                settings["threshold"],
                settings["min_contour_area"]
            )

            # Update previous frame
            prev_gray = curr_gray

            if motion:
                now = time.time()
                elapsed = now - last_trigger_time

                if elapsed >= settings["cooldown"]:
                    last_trigger_time = now
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                    # Save photo (full frame, not ROI)
                    filename = f"motion_{timestamp}.jpg"
                    filepath = captures_dir / filename
                    cv2.imwrite(str(filepath), frame)

                    logger.info(
                        f"MOTION DETECTED! Area: {area} pixels | "
                        f"Saved: {filename}"
                    )

                    # Send to Telegram
                    caption = (
                        f"⚠️ Motion Detected!\n"
                        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"📐 Motion area: {area} pixels"
                    )

                    success = send_telegram_photo(
                        settings["bot_token"],
                        settings["chat_id"],
                        str(filepath),
                        caption
                    )

                    if success:
                        logger.info("Sent to Telegram ✓")
                        # Also send any pending photos from the queue
                        retry_queue(settings, logger, send_queue)
                    else:
                        logger.warning("Telegram send failed, added to queue")
                        send_queue.append((str(filepath), caption))

            # Short sleep to avoid hogging the CPU
            time.sleep(0.05)

    except KeyboardInterrupt:
        logger.info("Stopped by user (Ctrl+C)")
    finally:
        cap.release()
        logger.info(f"Total captured frames: {len(list(captures_dir.glob('*.jpg')))}")
        logger.info("Bot shut down.")


def retry_queue(settings, logger, queue):
    """Retry sending photos that failed to send."""
    if not queue:
        return

    remaining = []
    for filepath, caption in queue:
        if os.path.exists(filepath):
            success = send_telegram_photo(
                settings["bot_token"],
                settings["chat_id"],
                filepath,
                caption + "\n📌 (delayed send)"
            )
            if success:
                logger.info(f"Sent from queue: {os.path.basename(filepath)} ✓")
            else:
                remaining.append((filepath, caption))

    queue.clear()
    queue.extend(remaining)


if __name__ == "__main__":
    main()
